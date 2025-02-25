// Introducing time stamping and seperate tasks for the audio recording and log saving.

/**********************************
 *           INCLUDES             *
 **********************************/
#include <Arduino.h>
#include <ESP_I2S.h>
#include <FS.h>
#include <Preferences.h>
#include <SD.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <WiFi.h>
#include <time.h>

#include "secrets.h"

/**********************************
 *       MACRO DEFINITIONS        *
 **********************************/
#define LED_PIN 2
#define BUTTON_PIN GPIO_NUM_3
#define BATTERY_PIN 6

#define RECORD_TIME 10       // seconds
#define AUDIO_QUEUE_SIZE 10
#define SAMPLING_RATE 16000  // 16kHz is currently the best possible Sampling Rate. Optimizing Battery and Quality.

#define RECORDINGS_DIR "/recordings"  // Directory constant
#define SD_SPEED 20000000  // Set frequency to 20 MHz, Maximum is probably around 25MHz default is 4MHz, the rational is that a higher speed translates to a shorter SD Card operation, which in turn translates to a lower power consumption. Note: Higher is with current SD card not possible.

#define LOG_QUEUE_SIZE 20

#define BUTTON_PRESS_TIME 1000  // Time in milliseconds to detect a button press
#define SLEEP_TIMEOUT_SEC 60        // Deep sleep period is 60s

#define DEFAULT_TIME 1740049200     // Default time:  20. Februar 2025 12:00:00 GMT+01:00 // https://www.epochconverter.com
#define TIMEZONE "GMT" // "CEST-1CET,M3.2.0/2:00:00,M11.1.0/2:00:00" // "CET-1CEST,M3.5.0/2,M10.5.0/3" // Timezone for Central Europe with some additions. Read it online to change it.


#define BATTERY_MONITOR_INTERVAL 60000  // Interval in milliseconds to monitor the battery // 60000 = 1 minute
#define TIME_PERSIST_INTERVAL 60000  // Interval in milliseconds to persist the time // 60000 = 60s

/**********************************
 *       GLOBAL VARIABLES         *
 **********************************/
Preferences preferences;
I2SClass i2s;

File curr_file;
File recordings_root_dir;
File logFile;

int bootSession = 0;
int logFileIndex = 0;
int audioFileIndex = 0;

time_t storedTime = 0;

/**********************************
 *        DATA STRUCTURES         *
 **********************************/
enum AudioChunkType { START, MIDDLE, END };

struct AudioBuffer {
  uint8_t *buffer;
  size_t size;
  char timestamp[21];
  AudioChunkType type;
};

volatile bool isRecording = false;  // Flag to indicate recording state
volatile bool recordingRequested = false;  // Flag to indicate recording state
volatile bool WIFIconnected = false;  // Flag to indicate WiFi connection state

volatile bool externalWakeTriggered = false;
volatile int externalWakeValid = -1;  // -1: not determined, 0: invalid (accidental), 1: valid wake

SemaphoreHandle_t ledMutex; // Global mutex for the LED
SemaphoreHandle_t sdMutex; // Add a global SD card access mutex

QueueHandle_t audioQueue;    // For multiple audio buffers
QueueHandle_t logQueue;      // For log messages

TimerHandle_t buttonTimer = NULL; // Timer to check if the button was pressed for a specified time

/**********************************
 *      FUNCTION PROTOTYPES       *
 **********************************/
void setup_from_timer();
void setup_from_external();
void setup_from_boot();

void recordAudio(void *parameter);
void audioFileTask(void *parameter);
void logFlushTask(void *parameter);

void batteryMonitorTask(void *parameter);
void persistTimeTask(void *parameter);
void updateTimeTask(void *parameter);
void wifiConnectionTask(void *parameter);

void log(const String &message);
void ensureRecordingDirectory();
void ensureLogFile();
void ErrorBlinkLED(int interval);
void storeCurrentTime();
String getTimestamp();

void initSD();
void initRecordingMode();
void initDeepSleep();
void initTime();

/**********************************
 *     INTERRUPT & CALLBACKS      *
 **********************************/
void IRAM_ATTR handleButtonPress() {
  BaseType_t xHigherPriorityTaskWoken = pdFALSE;
  // Start the timer if it is not already active.
  if (xTimerIsTimerActive(buttonTimer) == pdFALSE) {
    xTimerStartFromISR(buttonTimer, &xHigherPriorityTaskWoken);
  }
  portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

void buttonTimerCallback(TimerHandle_t xTimer) {
  // If this callback is triggered after an external wake
  if (externalWakeTriggered) {
    // Check if the button is still pressed after BUTTON_PRESS_TIME.
    if (digitalRead(BUTTON_PIN) == LOW) {
      // Confirmed: valid wakeup
      externalWakeValid = 1;
      recordingRequested = true;
      log("Sustained button press confirmed; proceeding with boot.");
    } else {
      // Invalid wake: button released too soon.
      externalWakeValid = 0;
      log("Accidental wake detected.");
    }
    externalWakeTriggered = false;
  } else {
    // Normal operation: toggle recording state.
    if (digitalRead(BUTTON_PIN) == LOW) {
      recordingRequested = !recordingRequested;
      log(recordingRequested ? "Recording start requested" : "Recording stop requested");
    }
  }
  // Update the LED state.
  if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
    digitalWrite(LED_PIN, recordingRequested ? HIGH : LOW);
    xSemaphoreGive(ledMutex);
  }
}


/**********************************
 *       SETUP & LOOP             *
 **********************************/
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);  // Set up the button pin

  ledMutex = xSemaphoreCreateMutex(); // Create the mutex
  sdMutex = xSemaphoreCreateMutex();   // Global mutex for SD card access

  logQueue = xQueueCreate(LOG_QUEUE_SIZE, sizeof(char*)); // Create a queue with space for log messages.

  buttonTimer = xTimerCreate("ButtonTimer", pdMS_TO_TICKS(BUTTON_PRESS_TIME), pdFALSE, NULL, buttonTimerCallback); // Create a one-shot timer which triggers after the specified time
  
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();

  switch (wakeup_reason) {
    case ESP_SLEEP_WAKEUP_TIMER:
      log("Woke from deep sleep (timer).");
      setup_from_timer();
      break;
    case ESP_SLEEP_WAKEUP_EXT0:
      log("Woke from deep sleep (external trigger).");
      // Set flag so that buttonTimerCallback distinguishes this case.
      externalWakeTriggered = true;
      xTimerStart(buttonTimer, 0);
      setup_from_external();
      break;      
    default:
      log("Normal boot or unknown wakeup cause.");
      setup_from_boot();
      break;
  }
}

void setup_from_timer() {
  log("Timer wake up not yet implemented. Proceeding with normal boot.");
  setup_from_boot();
}

void setup_from_external() {
  // If the wake was external, we need to wait for the button press to confirm the wake.
  if (externalWakeTriggered) {
    // Wait until externalWakeValid is updated (avoid indefinite wait with a timeout if needed)
    while (externalWakeValid == -1) {
      delay(10);  // Small pause allowing timer callback to run.
    }
    // If decision was valid, proceed with boot.
    if (externalWakeValid == 1) {
      log("Valid external wake, proceeding with boot.");
      setup_from_boot();
    } else {
      // Write to log and enter deep sleep again.
      logFile = SD.open("/device.log", FILE_APPEND);
      if (logFile) {
        logFile.println("Invalid external wake, entering deep sleep again.");
        logFile.flush();
        logFile.close();
      }
      initDeepSleep();
    }
  }
}

void setup_from_boot() {
  setCpuFrequencyMhz(80);  // 80 is lowest stable frequency for recording.

  // Initialize recording session (stored in preferences)
  preferences.begin("boot", false);
  bootSession = preferences.getInt("bootSession", 0);
  bootSession++;  // increment for a new boot
  preferences.putInt("bootSession", bootSession);
  preferences.end();

  log("======= Boot session: " + String(bootSession) + "=======");

  audioFileIndex = 0;  // Reset audio file index on boot
  logFileIndex = 0;    // Reset log file index on boot

  
  initTime();
  
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);  // Attach interrupt to the button pin

  audioQueue = xQueueCreate(AUDIO_QUEUE_SIZE , sizeof(AudioBuffer)); // Create a queue with space for AudioBuffer items.

  initRecordingMode();
  xTaskCreatePinnedToCore(recordAudio, "Record Loop", 8192, NULL, 1, NULL, 1); // Name, Stack size, Priority, Task handle, Core

  initSD();
  ensureRecordingDirectory();
  ensureLogFile();

  xTaskCreatePinnedToCore(persistTimeTask, "Persist Time", 2048, NULL, 1, NULL, 0);
  // xTaskCreatePinnedToCore(updateTimeTask, "Update NTP", 4096, NULL, 1, NULL, 0);
  
  xTaskCreatePinnedToCore(audioFileTask, "Audio File Save", 8192, NULL, 2, NULL, 0);  
  xTaskCreatePinnedToCore(logFlushTask, "Log Flush", 4096, NULL, 1, NULL, 0);  

  xTaskCreatePinnedToCore(wifiConnectionTask, "WiFi Connection", 4096, NULL, 1, NULL, 0);
  xTaskCreatePinnedToCore(batteryMonitorTask, "Battery Monitor", 2048, NULL, 1, NULL, 0);

}

void loop() {
  // Empty loop as tasks are running on different cores
}

/**********************************
 *         TASK FUNCTIONS         *
 **********************************/
void recordAudio(void *parameter) {
  static bool wasRecording = false;
  while (true) {
    if (recordingRequested) {
      isRecording = true;
      AudioBuffer audio;

      String ts = getTimestamp();
      snprintf(audio.timestamp, sizeof(audio.timestamp), "%s", ts.c_str());
      
      // Use "start" marker for the first chunk, then MIDDLE afterwards.
      if (!wasRecording) {
        wasRecording = true;
        audio.type = START;
      } else {
        audio.type = MIDDLE;
      }
      
      audio.buffer = i2s.recordWAV(RECORD_TIME, &audio.size);
      if (xQueueSend(audioQueue, &audio, pdMS_TO_TICKS(1000)) != pdPASS) {
        log("Failed to enqueue audio buffer!");
        free(audio.buffer);
      }
    } else {
      // If we were recording but recording is now off, record a final chunk with "end" marker.
      if (wasRecording) {
        AudioBuffer audio;
        String ts = getTimestamp();
        snprintf(audio.timestamp, sizeof(audio.timestamp), "%s", ts.c_str());
        audio.type = END;
        audio.buffer = i2s.recordWAV(RECORD_TIME, &audio.size);
        if (xQueueSend(audioQueue, &audio, pdMS_TO_TICKS(1000)) != pdPASS) {
          log("Failed to enqueue final audio buffer!");
          free(audio.buffer);
        }
        wasRecording = false;
      }
      isRecording = false;
    }
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}


void audioFileTask(void *parameter) {
  AudioBuffer audio;
  while (true) {
    while (xQueueReceive(audioQueue, &audio, pdMS_TO_TICKS(10)) == pdTRUE) {
      String prefix = "_";
      if (audio.type == START)
        prefix += "start";
      else if (audio.type == END)
        prefix += "end";
      else if (audio.type == MIDDLE)
        prefix += "middle";
        
      String fileName = String(RECORDINGS_DIR) + "/" +
                        String(bootSession) + "_" +
                        String(audioFileIndex) + "_" +
                        String(audio.timestamp) +
                        prefix + ".wav";
      audioFileIndex++;

      log("Constructed file name: " + fileName);  // Debug log for file name

      if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
        File curr_file = SD.open(fileName, FILE_WRITE);
        if (!curr_file) {
          log("Failed to open file for writing: " + fileName);
          xSemaphoreGive(sdMutex);
          free(audio.buffer);
          continue;
        }
        if (curr_file.write(audio.buffer, audio.size) != audio.size) {
          log("Failed to write audio data to file: " + fileName);
        } else {
          log("Audio recorded and saved: " + fileName);
        }
        curr_file.close();
        xSemaphoreGive(sdMutex);
      }
      free(audio.buffer);
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void logFlushTask(void *parameter) {
  while (true) {
    if (uxQueueMessagesWaiting(logQueue) > 0) {
      if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
        File logFile = SD.open("/device.log", FILE_APPEND);
        if (logFile) {
          char *pendingLog;
          while (xQueueReceive(logQueue, &pendingLog, 0) == pdTRUE) {
            logFile.println(pendingLog);
            free(pendingLog);
          }
          logFile.flush();
          logFile.close();
        } else {
          Serial.println("Failed to open log file for batch flush!");
          char *pendingLog;
          while (xQueueReceive(logQueue, &pendingLog, 0) == pdTRUE) {
            free(pendingLog);
          }
        }
        xSemaphoreGive(sdMutex);
      }
    }

    // Check if recording has stopped and both queues are empty.
    if (!isRecording && 
        (uxQueueMessagesWaiting(audioQueue) == 0) && 
        (uxQueueMessagesWaiting(logQueue) == 0)) {
      // Write directly to log file, since the queue won't be processed anymore
      logFile = SD.open("/device.log", FILE_APPEND);
      if (logFile) {
        logFile.println("Recording stopped and queues emptied. Entering deep sleep.");
        logFile.flush();
        logFile.close();
      }
      initDeepSleep();
      Serial.println("This will never be printed");
    }

    vTaskDelay(pdMS_TO_TICKS(10));
  }
}


void batteryMonitorTask(void *parameter) {
  // (Board-specific ADC setup might be required before using analogRead.)
  pinMode(BATTERY_PIN, INPUT);
  // Set the ADC attenuation to 11dB so that the full-scale voltage is ~3.3V.
  analogSetAttenuation(ADC_11db);
  const int sampleCount = 10;  // Number of ADC samples for averaging

  // Remove the latter. Currently the board is badly soldered and voltage measurement is not possible.
  vTaskDelete(NULL);

  while (true) {
    long total = 0;
    for (int i = 0; i < sampleCount; i++) {
      total += analogRead(BATTERY_PIN);
      vTaskDelay(pdMS_TO_TICKS(5));  // Brief delay between readings to stabilize ADC
    }
    int averagedRawValue = total / sampleCount;
    // log average raw value
    log("Battery raw value: " + String(averagedRawValue));

    // Convert averaged raw value to voltage.
    // For a 12-bit ADC with a 3.3V reference and a voltage divider with 2x 10k resistors:
    float voltage = ((float)averagedRawValue / 4095.0) * 3.3 * 2;
    log("Battery voltage: " + String(voltage, 3) + "V");

    // Wait for 10 seconds before next measurement.
    vTaskDelay(pdMS_TO_TICKS(BATTERY_MONITOR_INTERVAL));
  }
  Serial.println("This will never be printed");
}

void persistTimeTask(void *parameter) {
  while (true) {
      storeCurrentTime();
      vTaskDelay(pdMS_TO_TICKS(TIME_PERSIST_INTERVAL));
  }
}

void updateTimeTask(void *parameter) {
  // Set a flag to indicate that the time has been updated.
  bool timeUpdated = false;
  while (true) {
      if (WiFi.status() == WL_CONNECTED) {
          configTime(0, 0, "pool.ntp.org", "time.google.com", "time.nist.gov");
          struct tm timeinfo;
          if (getLocalTime(&timeinfo)) {
              storedTime = mktime(&timeinfo);
              log("Current time obtained: " + String(timeinfo.tm_hour) + ":" +
                  String(timeinfo.tm_min) + ":" + String(timeinfo.tm_sec));
              // Persist the new time.
              preferences.begin("time", false);
              preferences.putLong("storedTime", storedTime);
              preferences.end();
              timeUpdated = true;
          } else {
              log("Failed to obtain time");
          }
      } else {
          log("Failed to connect to WiFi.");
      }

    // On success update every 60 minutes, otherwise retry sooner.
    vTaskDelay(pdMS_TO_TICKS(timeUpdated ? 3600000 : 10000));
  }
}

void wifiConnectionTask(void *parameter) {
  while (true) {
      if (WiFi.status() != WL_CONNECTED) {
          log("WiFi not connected. Attempting to connect...");
          WiFi.begin(SSID, PASSWORD);
          unsigned long startAttemptTime = millis();
          // Try for up to 5 seconds.
          while (WiFi.status() != WL_CONNECTED && (millis() - startAttemptTime) < 5000) {
              vTaskDelay(pdMS_TO_TICKS(500));  
          }
          if (WiFi.status() == WL_CONNECTED) {
              log("WiFi connected: " + WiFi.localIP().toString());
              // Update time from NTP servers.
              configTime(0, 0, "pool.ntp.org", "time.google.com", "time.nist.gov");
              //WIFIconnected = true;
          } else {
              log("WiFi connection timed out.");
              WiFi.disconnect();
          }
      }
      vTaskDelay(pdMS_TO_TICKS(10000));  // Check every 10 seconds.
      // vTaskDelay(pdMS_TO_TICKS(WIFIconnected ? 3600000 : 10000));
  }
}

/**********************************
 *       UTILITY FUNCTIONS        *
 **********************************/
void log(const String &message) {
  String timestamp = getTimestamp();
  String logMessage = String(bootSession) + "_" + String(logFileIndex) + "_" + timestamp + ": " + message;
  Serial.println(logMessage);

  // Allocate a copy on the heap.
  char *msgCopy = strdup(logMessage.c_str());
  if (xQueueSend(logQueue, &msgCopy, portMAX_DELAY) != pdPASS) {
    Serial.println("Failed to enqueue log message!");
    free(msgCopy);
  }
}

void ensureRecordingDirectory() {
  if (!SD.exists(RECORDINGS_DIR)) {
    if (SD.mkdir(RECORDINGS_DIR)) {
      log("Recordings directory created");
    } else {
      log("Failed to create recordings directory!");
    }
  }
}

void ensureLogFile() {
  if (!SD.exists("/device.log")) {
    File logFile = SD.open("/device.log", FILE_WRITE);
    if (logFile) {
      logFile.println("=== Device Log Started ===");
      logFile.flush();
      logFile.close();
    }
  }
}

void ErrorBlinkLED(int interval) {
  // stop recording as well
  recordingRequested = false;

  bool led_state = HIGH;
  while (true) {
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
      led_state = !led_state;
      digitalWrite(LED_PIN, led_state);
      xSemaphoreGive(ledMutex);
    }
    vTaskDelay(pdMS_TO_TICKS(interval));
  }
  Serial.println("This will never be printed");
}

void storeCurrentTime() {
  time_t current = time(NULL);
  preferences.begin("time", false);
  preferences.putLong("storedTime", current);
  preferences.end();
  log("Stored current time: " + String(current));
}

// Add a helper function to return a formatted timestamp:
String getTimestamp() {
  struct tm timeinfo;
  if(getLocalTime(&timeinfo)) {
    char buffer[20];
    strftime(buffer, sizeof(buffer), "%y-%m-%d_%H-%M-%S", &timeinfo);
    // Serial.println("Timestamp from getTimeStamp(): " + String(buffer));
    return String(buffer);
  }
  return "unknown";
}

/**********************************
 *         INITIALIZATION         *
 **********************************/
void initSD() {
  if (!SD.begin(21, SPI, SD_SPEED)) {
    Serial.println("Failed to mount SD Card!");
    ErrorBlinkLED(100);
  }
  log("SD card initialized.");
}

void initRecordingMode() {
    
    log("Initializing PDM Microphone...");
    i2s.setPinsPdmRx(42, 41);
  
    // The transmission mode is PDM_MONO_MODE, which means that PDM (pulse
    // density modulation) mono mode is used for transmission
    if (!i2s.begin(I2S_MODE_PDM_RX, SAMPLING_RATE, I2S_DATA_BIT_WIDTH_16BIT,
                   I2S_SLOT_MODE_MONO)) {
      log("Failed to initialize I2S!");
      ErrorBlinkLED(100);
    }
    log("Mic initialized.");
  }

void initDeepSleep() {
  // Prepare wakeup sources:
  // Use EXT0 wakeup on BUTTON_PIN: trigger when the pin reads LOW.
  esp_sleep_enable_ext0_wakeup(static_cast<gpio_num_t>(BUTTON_PIN), 0);
  // Timer wakeup after SLEEP_TIMEOUT_SEC seconds
  esp_sleep_enable_timer_wakeup(SLEEP_TIMEOUT_SEC * 1000000ULL);

  // Persist current time before sleep.
  storeCurrentTime();

  // Enter deep sleep.
  esp_deep_sleep_start();
}


void initTime() {
  preferences.begin("time", false);
  long persistedTime = preferences.getLong("storedTime", 0);
  
  // Set timezone.
  setenv("TZ", TIMEZONE, 1);
  tzset();
  
  struct timeval tv;
  time_t currentRtcTime = time(NULL);

  if (persistedTime == 0) {
    // No persisted time: use default time.
    tv.tv_sec = DEFAULT_TIME;
    tv.tv_usec = 0;
    settimeofday(&tv, NULL);
    storedTime = DEFAULT_TIME;
    preferences.putLong("storedTime", storedTime);
    log("Default time set: " + String(storedTime));
  } else {
    // Check if RTC has a valid updated time.
    if (currentRtcTime > persistedTime) {
        storedTime = currentRtcTime;
        log("System time updated from RTC: " + String(storedTime));
    } else {
        storedTime = persistedTime;
        log("System time updated from persisted time: " + String(storedTime));
    }
    tv.tv_sec = storedTime;
    tv.tv_usec = 0;
    settimeofday(&tv, NULL);
}
  preferences.end();
}