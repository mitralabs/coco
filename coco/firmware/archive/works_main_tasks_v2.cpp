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

/**********************************
 *       MACRO DEFINITIONS        *
 **********************************/
#define LED_PIN 2
#define BUTTON_PIN GPIO_NUM_3  // Define the button pin

#define RECORD_TIME 10       // seconds
#define AUDIO_QUEUE_SIZE 10
#define SAMPLING_RATE 16000  // 16kHz is currently the best possible Sampling Rate. Optimizing Battery and Quality.

#define BASE_DELAY 2000  // Delay between http Requests, if one failed.

#define RECORDINGS_DIR "/recordings"  // Directory constant
#define SD_SPEED 20000000  // Set frequency to 20 MHz, Maximum is probably around 25MHz default is 4MHz, the rational is that a higher speed translates to a shorter SD Card operation, which in turn translates to a lower power consumption. Note: Higher is with current SD card not possible.

#define LOG_QUEUE_SIZE 20

#define BUTTON_PRESS_TIME 1000  // Time in milliseconds to consider a button press

/**********************************
 *       GLOBAL VARIABLES         *
 **********************************/
Preferences preferences;
I2SClass i2s;

File curr_file;
File recordings_root_dir;
File logFile;

int fileIndex = 0;
int recordingSession = 0;

/**********************************
 *        DATA STRUCTURES         *
 **********************************/
struct AudioBuffer {
  uint8_t *buffer;
  size_t size;
};

volatile bool isRecording = false;  // Flag to indicate recording state

SemaphoreHandle_t ledMutex; // Global mutex for the LED
QueueHandle_t audioQueue;    // For multiple audio buffers
QueueHandle_t logQueue;      // For log messages

TimerHandle_t buttonTimer = NULL; // Timer to check if the button was pressed for a specified time

/**********************************
 *      FUNCTION PROTOTYPES       *
 **********************************/
void initSD();
void initRecordingMode();
void recordLoop(void *parameter);
void saveToSD(void *parameter);
void log(const String &message);
void ensureRecordingDirectory();
void ensureLogFile();
void ErrorBlinkLED(int interval);

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
  // Check if the button is still pressed (assuming INPUT_PULLUP, so LOW means pressed)
  if (digitalRead(BUTTON_PIN) == LOW) {
    isRecording = !isRecording;  // Toggle recording state
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
      digitalWrite(LED_PIN, isRecording ? HIGH : LOW);
      xSemaphoreGive(ledMutex);
    }
    log(isRecording ? "Recording started (via timer)" : "Recording stopped (via timer)");
  }
}

/**********************************
 *       SETUP & LOOP             *
 **********************************/
void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  // Shortly flash LED to indicate wake up
  digitalWrite(LED_PIN, HIGH);
  delay(100);
  digitalWrite(LED_PIN, LOW);


  pinMode(BUTTON_PIN, INPUT_PULLUP);  // Set up the button pin
  buttonTimer = xTimerCreate("ButtonTimer", pdMS_TO_TICKS(BUTTON_PRESS_TIME), pdFALSE, NULL, buttonTimerCallback); // Create a one-shot timer which triggers after the specified time
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);  // Attach interrupt to the button pin

  ledMutex = xSemaphoreCreateMutex(); // Create the mutex

  logQueue = xQueueCreate(LOG_QUEUE_SIZE, sizeof(char*)); // Create a queue with space for log messages.
  audioQueue = xQueueCreate(AUDIO_QUEUE_SIZE , sizeof(AudioBuffer)); // Create a queue with space for AudioBuffer items.

  initRecordingMode();
  xTaskCreatePinnedToCore(recordLoop, "Record Loop", 4096, NULL, 1, NULL, 1); // Name, Stack size, Priority, Task handle, Core

  initSD();
  ensureRecordingDirectory();
  ensureLogFile();
  
  xTaskCreatePinnedToCore(saveToSD, "Save to SD", 4096, NULL, 1, NULL, 0);
}

void loop() {
  // Empty loop as tasks are running on different cores
}

/**********************************
 *         TASK FUNCTIONS         *
 **********************************/
void recordLoop(void *parameter) {
  while (true) {
    if (isRecording) {
      AudioBuffer audio;
      // Record into a local buffer.
      audio.buffer = i2s.recordWAV(RECORD_TIME, &audio.size);
      
      // Enqueue the audio buffer, waiting if needed.
      if (xQueueSend(audioQueue, &audio, portMAX_DELAY) != pdPASS) {
        log("Failed to enqueue audio buffer!");
        free(audio.buffer);
      }
    }
    
    // Delay to yield to other tasks.
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void saveToSD(void *parameter) {
  AudioBuffer audio;
  while (true) {
    // Flush any pending log messages.
    char *pendingLog;
    while (xQueueReceive(logQueue, &pendingLog, 0) == pdTRUE) {
      File logFile = SD.open("/device.log", FILE_APPEND);
      if (logFile) {
        logFile.println(pendingLog);
        logFile.flush();
        logFile.close();
      } else {
        Serial.println("Failed to open log file for log flush!");
        free(pendingLog);
        break;
      }
      free(pendingLog);
    }
    
    // Process audio buffers.
    if (xQueueReceive(audioQueue, &audio, portMAX_DELAY) == pdTRUE) {
      String fileName = String(RECORDINGS_DIR) + "/audio_" +
                        String(recordingSession) + "_" + String(fileIndex) + ".wav";

      File curr_file = SD.open(fileName, FILE_WRITE);
      if (!curr_file) {
        log("Failed to open file for writing: " + fileName);
        free(audio.buffer);
        continue;
      }

      if (curr_file.write(audio.buffer, audio.size) != audio.size) {
        log("Failed to write audio data to file: " + fileName);
      } else {
        log("Audio recorded and saved: " + fileName);
      }

      curr_file.close();
      free(audio.buffer);
      fileIndex++;
    }
    
    // Delay to yield to the scheduler.
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

/**********************************
 *       UTILITY FUNCTIONS        *
 **********************************/
void log(const String &message) {
  // Generate a timestamp and create the log message.
  String timestamp = String(millis());
  String logMessage = timestamp + ": " + message;
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
  isRecording = false;

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

/**********************************
 *         INITIALIZATION         *
 **********************************/
void initSD() {
  if (!SD.begin(21, SPI, SD_SPEED)) {
    Serial.println("Failed to mount SD Card!");
    ErrorBlinkLED(100);
  }
  Serial.println("SD card initialized.");
}

void initRecordingMode() {
  
    log("ADjusting CPU Frequency");
    setCpuFrequencyMhz(80);  // 80 is lowest stable frequency for recording.
  
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
  
    preferences.begin("audio", false);
    recordingSession = preferences.getInt("session", 0);
    log("Recording Session: " + String(recordingSession));
    fileIndex = 1;  // Set the Fileindex to 1. Will be increased within the
                    // recording loop.
    preferences.putInt("session", recordingSession + 1);
    preferences.end();
  }