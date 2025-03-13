// Introducing improved WiFi Handling, Clean Up, File Transfer, and Stack Monitoring.
// This version currently doesn't use the DEEPSLEEP mode, but this will be implemented shortly.

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
#include <HTTPClient.h>
#include <time.h>

#include "secrets.h"

/**********************************
 *       MACRO DEFINITIONS        *
 **********************************/
#define LED_PIN 2
#define BUTTON_PIN GPIO_NUM_1
#define BATTERY_PIN 4

#define RECORD_TIME 10       // seconds
#define AUDIO_QUEUE_SIZE 10
#define SAMPLING_RATE 16000  // 16kHz is currently the best possible Sampling Rate. Optimizing Battery and Quality.

#define RECORDINGS_DIR "/recordings"  // Directory constant
#define UPLOAD_QUEUE_FILE "/upload_queue.txt"  // File that stores the upload queue
#define UPLOAD_QUEUE_TEMP "/upload_queue.tmp"  // Temporary file for upload queue
#define SD_SPEED 20000000  // Set frequency to 20 MHz, Maximum is probably around 25MHz default is 4MHz, the rational is that a higher speed translates to a shorter SD Card operation, which in turn translates to a lower power consumption. Note: Higher is with current SD card not possible.

#define LOG_QUEUE_SIZE 20

#define BUTTON_PRESS_TIME 1000  // Time in milliseconds to detect a button press
#define SLEEP_TIMEOUT_SEC 6000  // Deep sleep period in seconds // https://deepbluembedded.com/esp32-sleep-modes-power-consumption/

#define DEFAULT_TIME 1740049200     // Default time:  20. Februar 2025 12:00:00 GMT+01:00 // https://www.epochconverter.com
#define TIMEZONE "GMT" // "CEST-1CET,M3.2.0/2:00:00,M11.1.0/2:00:00" // "CET-1CEST,M3.5.0/2,M10.5.0/3" // Timezone for Central Europe with some additions. Read it online to change it.

#define BATTERY_MONITOR_INTERVAL 60000  // Interval in milliseconds to monitor the battery // 60000 = 60s
#define TIME_PERSIST_INTERVAL 60000  // Interval in milliseconds to persist the time // 60000 = 60s

#define MIN_SCAN_INTERVAL 5000 // microseconds initial scan interval
#define MAX_SCAN_INTERVAL 600000  // 10 minutes max scan interval

#define HTTP_TIMEOUT 10000  // microseconds timeout for HTTP requests
#define UPLOAD_CHECK_INTERVAL 2000 // Check every 2 seconds

#define LOG_FILE "/device.log"
#define TIME_FILE "/time.txt"

/***********************************************
 *     GLOBAL VARIABLES AND DATA STRUCTURES    *
 ***********************************************/
Preferences preferences;
I2SClass i2s;

File curr_file;
File recordings_root_dir;
File logFile;

int bootSession = 0;
int logFileIndex = 0;
int audioFileIndex = 0;

// LED PWM configuration parameters
int freq = 5000;     // PWM frequency in Hz
int resolution = 8;  // Resolution in bits (1-16)

time_t storedTime = 0;

unsigned long nextWifiScanTime = 0; // Next time to scan for networks
unsigned long currentScanInterval = MIN_SCAN_INTERVAL; // Current backoff interval
unsigned long nextBackendCheckTime = 0; // Next time to check backend availability
unsigned long currentBackendInterval = MIN_SCAN_INTERVAL; // Current backoff interval

enum AudioChunkType { START, MIDDLE, END };

struct AudioBuffer {
  uint8_t *buffer;
  size_t size;
  char timestamp[21];
  AudioChunkType type;
};

struct UploadBuffer {
  uint8_t *buffer;
  size_t size;
  String filename;
};

volatile bool isRecording = false;  // Flag to indicate recording state
volatile bool recordingRequested = false;  // Flag to indicate recording state
volatile bool WIFIconnected = false;  // Flag to indicate WiFi connection state
volatile bool backendReachable = false; // Flag indicating if backend is available
volatile bool wavFilesAvailable = false;
volatile bool uploadInProgress = false;

volatile bool externalWakeTriggered = false;
volatile bool readyForDeepSleep = false;
volatile int externalWakeValid = -1;  // -1: not determined, 0: invalid (accidental), 1: valid wake

SemaphoreHandle_t ledMutex; // Global mutex for the LED
SemaphoreHandle_t sdMutex; // Add a global SD card access mutex
SemaphoreHandle_t uploadMutex = NULL;

QueueHandle_t audioQueue;    // For multiple audio buffers
QueueHandle_t logQueue;      // For log messages

TimerHandle_t buttonTimer = NULL; // Timer to check if the button was pressed for a specified time

TaskHandle_t recordAudioTaskHandle = NULL;
TaskHandle_t audioFileTaskHandle = NULL;
TaskHandle_t logFlushTaskHandle = NULL;
TaskHandle_t wifiConnectionTaskHandle = NULL;
TaskHandle_t batteryMonitorTaskHandle = NULL;
TaskHandle_t uploadTaskHandle = NULL;
TaskHandle_t persistTimeTaskHandle = NULL;
TaskHandle_t backendReachabilityTaskHandle = NULL;














/**********************************
 *      FUNCTION PROTOTYPES       *
 **********************************/
void setup_from_timer();
void setup_from_external();
void setup_from_boot();

void initRecordingMode();
void ensureRecordingDirectory();
void recordAudio(void *parameter);
void audioFileTask(void *parameter);
bool addToUploadQueue(const String &filename);

String getNextUploadFile();
bool removeFirstFromUploadQueue(const String &filename);
void fileUploadTask(void *parameter);
bool uploadFileFromBuffer(uint8_t *buffer, size_t size, const String &filename);

void initSD();
void ensureLogFile();
void log(const String &message);
void logFlushTask(void *parameter);

void batteryMonitorTask(void *parameter);
void ErrorBlinkLED(int interval);
void stackMonitorTask(void *parameter);
void monitorStackUsage(TaskHandle_t taskHandle);

void initDeepSleep();

void initTime();
void storeCurrentTime();
void persistTimeTask(void *parameter);
String getTimestamp();

void wifiConnectionTask(void *parameter);
void WiFiStationConnected(WiFiEvent_t event, WiFiEventInfo_t info);
void WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info);
//void WiFiStationDisconnected(WiFiEvent_t event, WiFiEventInfo_t info);
bool checkBackendReachability();
void backendReachabilityTask(void *parameter);


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
      // If we're currently recording, stopping will trigger deep sleep
      if (recordingRequested) {
        readyForDeepSleep = true;
        log("Recording stop requested; will enter deep sleep when safe");
      }
      recordingRequested = !recordingRequested;
      log(recordingRequested ? "Recording start requested" : "Recording stop requested");
    }
  }
  // Update the LED state.
  if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
    ledcWrite(LED_PIN, recordingRequested ? 255 : 0);  // 255 is full brightness, 20 is very low brightness
    xSemaphoreGive(ledMutex);
  }
}












/**********************************
 *       SETUP & LOOP             *
 **********************************/
void setup() {
  Serial.begin(115200);
  setCpuFrequencyMhz(80);  // 80 is lowest stable frequency for this routine.

  ledcAttach(LED_PIN, freq, resolution);
  ledcWrite(LED_PIN, 0);  // Set brightness (0-255 for 8-bit resolution) // Lower values = dimmer LED = less power consumption


  // Set up the button pin
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  ledMutex = xSemaphoreCreateMutex(); // Create the mutex
  sdMutex = xSemaphoreCreateMutex();   // Global mutex for SD card access

  logQueue = xQueueCreate(LOG_QUEUE_SIZE, sizeof(char*)); // Create a queue with space for log messages.
  if (logQueue == NULL) {
    logFile = SD.open("LOG_FILE", FILE_APPEND);
    if (logFile) {
      logFile.println("Failed to create log queue!");
      logFile.flush();
      logFile.close();
    }
    ErrorBlinkLED(100);
  }

  buttonTimer = xTimerCreate("ButtonTimer", pdMS_TO_TICKS(BUTTON_PRESS_TIME), pdFALSE, NULL, buttonTimerCallback); // Create a one-shot timer which triggers after the specified time
  
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();

  switch (wakeup_reason) {
    case ESP_SLEEP_WAKEUP_TIMER:
      setup_from_timer();
      break;
    case ESP_SLEEP_WAKEUP_EXT0:
      setup_from_external();
      break;      
    default:
      setup_from_boot();
      break;
  }
}

void setup_from_timer() {
  // Write to log and enter deep sleep again.
  logFile = SD.open("LOG_FILE", FILE_APPEND);
  if (logFile) {
    logFile.println("Woke from deep sleep (timer).");
    logFile.println("Timer wake up routine not yet implemented. Going back to sleep.");
    logFile.flush();
    logFile.close();
  }
  initDeepSleep();
}

void setup_from_external() {
  // If the wake was external, we need to wait for the button press to confirm the wake.
  externalWakeTriggered = true;
  xTimerStart(buttonTimer, 0);

  // Wait until externalWakeValid is updated (avoid indefinite wait with a timeout)
  unsigned long startTime = millis();
  while (externalWakeValid == -1 && (millis() - startTime < 2000)) {
    delay(10);  // Small pause allowing timer callback to run.
  }

  // If decision was valid, proceed with boot.
  if (externalWakeValid == 1) {
    log("Valid external wake, proceeding with boot.");
    setup_from_boot();
  } else {
    // Write to log and enter deep sleep again.
    logFile = SD.open("LOG_FILE", FILE_APPEND);
    if (logFile) {
      logFile.println("Invalid external wake, entering deep sleep again.");
      logFile.flush();
      logFile.close();
    }
    initDeepSleep();
  }
}

void setup_from_boot() {
  
  // Initialize recording session (stored in preferences)
  preferences.begin("boot", false);
  bootSession = preferences.getInt("bootSession", 0);
  bootSession++;  // increment for a new boot
  preferences.putInt("bootSession", bootSession);
  preferences.end();
  log("\n\n\n======= Boot session: " + String(bootSession) + "=======");

  audioFileIndex = 0;  // Reset audio file index on boot
  logFileIndex = 0;    // Reset log file index on boot

  initTime();
  
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);  // Attach interrupt to the button pin

  audioQueue = xQueueCreate(AUDIO_QUEUE_SIZE , sizeof(AudioBuffer)); // Create a queue with space for AudioBuffer items.
  if(audioQueue == NULL) {
    log("Failed to create audio queue!");
    ErrorBlinkLED(100);
  }

  initSD();
  initRecordingMode();
  
  // Tasks on Core 1
  // Name, Stack size, Priority, Task handle, Core
  if(xTaskCreatePinnedToCore(recordAudio, "Record Loop", 4096, NULL, 1, &recordAudioTaskHandle, 1) != pdPASS ) {
    log("Failed to create recordAudio task!");
    ErrorBlinkLED(100);
  }

  // Tasks on Core 0
  if(xTaskCreatePinnedToCore(persistTimeTask, "Persist Time", 4096, NULL, 1, &persistTimeTaskHandle, 0) != pdPASS ) {
    log("Failed to create persistTime task!");
    ErrorBlinkLED(100);
  }
  
  if(xTaskCreatePinnedToCore(audioFileTask, "Audio File Save", 4096, NULL, 4, &audioFileTaskHandle, 0) != pdPASS ) {
    log("Failed to create audioFile task!");
    ErrorBlinkLED(100);
  }
  if(xTaskCreatePinnedToCore(logFlushTask, "Log Flush", 4096, NULL, 1,  &logFlushTaskHandle, 0) != pdPASS ) {
    log("Failed to create logFlush task!");
    ErrorBlinkLED(100);
  }

  if(xTaskCreatePinnedToCore(wifiConnectionTask, "WiFi Connection", 4096, NULL, 1, &wifiConnectionTaskHandle, 0) != pdPASS ) {
    log("Failed to create wifiConnection task!");
    ErrorBlinkLED(100);
  }

  if(xTaskCreatePinnedToCore(backendReachabilityTask, "Backend Check", 4096, NULL, 1, &backendReachabilityTaskHandle, 0) != pdPASS ) {
    log("Failed to create backendReachabilityTask!");
    ErrorBlinkLED(100);
  }

  if(xTaskCreatePinnedToCore(batteryMonitorTask, "Battery Monitor", 4096, NULL, 1, &batteryMonitorTaskHandle, 0) != pdPASS ) {
    log("Failed to create batteryMonitor task!");
    ErrorBlinkLED(100);
  }
  
  // This task can be used to monitor the stack usage. It can be commented / uncommented as needed.
  if(xTaskCreatePinnedToCore(stackMonitorTask, "Stack Monitor", 4096, NULL, 1, NULL, 0) != pdPASS ) {
    log("Failed to create stackMonitor task!");
    ErrorBlinkLED(100);
  }
}

void loop() {
  // Empty loop as tasks are running on different cores
}











/**********************************
 *         RECORDING FUNCTIONS    *
 **********************************/
void initRecordingMode() {
  log("Initializing PDM Microphone...");
  i2s.setPinsPdmRx(42, 41);
  if (!i2s.begin(I2S_MODE_PDM_RX, SAMPLING_RATE, I2S_DATA_BIT_WIDTH_16BIT,
                 I2S_SLOT_MODE_MONO)) {
    log("Failed to initialize I2S!");
    ErrorBlinkLED(100);
  }
  log("Mic initialized.");
  ensureRecordingDirectory();
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
          wavFilesAvailable = true;

          // Add to upload queue while we have the mutex
          if (addToUploadQueue(fileName)) {
            log("Added to upload queue: " + fileName);
          } else {
            log("Failed to add to upload queue: " + fileName);
          }
        }
        curr_file.close();
        xSemaphoreGive(sdMutex);
      }
      free(audio.buffer);
    }

    // Check if we should enter deep sleep
    if (readyForDeepSleep && 
      !recordingRequested && 
      !isRecording &&
      uxQueueMessagesWaiting(audioQueue) == 0) {
    
      // Make sure log queue is also empty before sleep
      if (uxQueueMessagesWaiting(logQueue) == 0) {
        log("Recording stopped and all data processed. Entering deep sleep.");
        vTaskDelay(pdMS_TO_TICKS(500)); // Short delay to allow log to be written
        initDeepSleep();
      }
    }

    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

bool addToUploadQueue(const String &filename) {
  // We assume the SD mutex is already taken by the calling function
  File queueFile = SD.open(UPLOAD_QUEUE_FILE, FILE_APPEND);
  if (!queueFile) {
    log("Failed to open upload queue file for writing");
    return false;
  }
  
  queueFile.println(filename);
  queueFile.close();
  return true;
}








/**********************************
 *         FILE UPLOAD            *
 **********************************/
String getNextUploadFile() {
  String nextFile = "";
  
  if (xSemaphoreTake(sdMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
    if (SD.exists(UPLOAD_QUEUE_FILE)) {
      File queueFile = SD.open(UPLOAD_QUEUE_FILE, FILE_READ);
      if (queueFile) {
        if (queueFile.available()) {
          nextFile = queueFile.readStringUntil('\n');
          nextFile.trim(); // Remove any newline characters
        }
        queueFile.close();
      }
    }
    xSemaphoreGive(sdMutex);
  }
  
  return nextFile;
}

bool removeFirstFromUploadQueue() {
  if (xSemaphoreTake(sdMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
    if (!SD.exists(UPLOAD_QUEUE_FILE)) {
      xSemaphoreGive(sdMutex);
      return false;
    }
    
    File queueFile = SD.open(UPLOAD_QUEUE_FILE, FILE_READ);
    if (!queueFile) {
      xSemaphoreGive(sdMutex);
      return false;
    }
    
    // Create a temporary file
    File tempFile = SD.open(UPLOAD_QUEUE_TEMP, FILE_WRITE);
    if (!tempFile) {
      queueFile.close();
      xSemaphoreGive(sdMutex);
      return false;
    }
    
    // Skip the first line and copy the rest
    bool firstLine = true;
    String line;
    
    while (queueFile.available()) {
      line = queueFile.readStringUntil('\n');
      
      if (firstLine) {
        firstLine = false;
        // Skip the first line (we're removing it)
        continue;
      }
      
      tempFile.println(line);
    }
    
    queueFile.close();
    tempFile.close();
    
    // Replace original file with temp file
    SD.remove(UPLOAD_QUEUE_FILE);
    SD.rename(UPLOAD_QUEUE_TEMP, UPLOAD_QUEUE_FILE);
    
    xSemaphoreGive(sdMutex);
    return true;
  }
  
  return false;
}


void fileUploadTask(void *parameter) {
  // Initialize upload mutex if needed
  if (uploadMutex == NULL) {
    uploadMutex = xSemaphoreCreateMutex();
  }
  
  while (true) {
    // Only proceed if WiFi is connected
    if (WIFIconnected && backendReachable) {
      // Check if we're already uploading
      if (xSemaphoreTake(uploadMutex, 0) == pdTRUE) {
        uploadInProgress = true;
        
        // Get the next file to upload from queue
        String nextFile = getNextUploadFile();
        
        if (nextFile.length() > 0) {
          log("Processing next file from queue: " + nextFile);
          
          // Try to take SD card mutex
          if (xSemaphoreTake(sdMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
            UploadBuffer uploadBuffer = {NULL, 0, ""};
            
            if (SD.exists(nextFile)) {
              File file = SD.open(nextFile);
              if (file) {
                uploadBuffer.filename = nextFile;
                uploadBuffer.size = file.size();
                
                // Allocate memory for the file content
                uploadBuffer.buffer = (uint8_t*)malloc(uploadBuffer.size);
                if (uploadBuffer.buffer) {
                  // Read the entire file into RAM
                  size_t bytesRead = file.read(uploadBuffer.buffer, uploadBuffer.size);
                  if (bytesRead != uploadBuffer.size) {
                    log("Error reading file into buffer");
                    free(uploadBuffer.buffer);
                    uploadBuffer.buffer = NULL;
                  }
                } else {
                  log("Failed to allocate memory for file upload");
                }
                
                file.close();
              }
            }
            
            // Release SD mutex before uploading
            xSemaphoreGive(sdMutex);
            
            if (uploadBuffer.buffer) {
              // Upload the file from RAM
              log("Uploading file from buffer: " + uploadBuffer.filename);
              bool uploadSuccess = uploadFileFromBuffer(uploadBuffer.buffer, uploadBuffer.size, uploadBuffer.filename);
              
              // If upload was successful, delete the file and remove from queue
              if (uploadSuccess) {
                log("Upload successful, deleting file");
                
                // Take SD mutex again just for deletion
                if (xSemaphoreTake(sdMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
                  if (SD.remove(uploadBuffer.filename)) {
                    log("File deleted: " + uploadBuffer.filename);
                  } else {
                    log("Failed to delete file: " + uploadBuffer.filename);
                  }
                  xSemaphoreGive(sdMutex);
                }
                
                // Remove from queue
                removeFirstFromUploadQueue();
              } else {
                log("Upload failed for: " + uploadBuffer.filename);
              }
              
              // Free the buffer memory
              free(uploadBuffer.buffer);
            }
          } else {
            log("Could not get SD card mutex for file upload");
          }
        } else {
          // No files in queue
          wavFilesAvailable = false;
          log("No files in upload queue");
        }
        
        uploadInProgress = false;
        xSemaphoreGive(uploadMutex);
      }
    }
    
    vTaskDelay(pdMS_TO_TICKS(UPLOAD_CHECK_INTERVAL));
  }
}

bool uploadFileFromBuffer(uint8_t *buffer, size_t size, const String &filename) {
  if (!buffer || size == 0) {
    return false;
  }
  
  // Extract just the filename without the path for the request
  String bareFilename = filename.substring(filename.lastIndexOf('/') + 1);
  
  // Initialize HTTP client
  HTTPClient client;

  // Check WiFi connection before proceeding
  if (WiFi.status() != WL_CONNECTED) {
    log("WiFi not connected, aborting upload");
    return false;
  }
  
  // Add timeout settings
  client.setTimeout(HTTP_TIMEOUT);

  client.begin(API_ENDPOINT);
  client.addHeader("Content-Type", "audio/wav");
  client.addHeader("X-API-Key",
                   API_KEY);  // Add the API key as a custom header
  client.addHeader("Content-Disposition",
                   "form-data; name=\"file\"; filename=\"" +
                       String(bareFilename) + "\"");

  // Send the request with the file data from buffer
  int httpResponseCode = client.sendRequest("POST",buffer, size);
  
  if (httpResponseCode > 0) {
    log("HTTP Response code: " + String(httpResponseCode));
    String response = client.getString();
    log("Server response: " + response);
    client.end();
    return (httpResponseCode == HTTP_CODE_OK || httpResponseCode == HTTP_CODE_CREATED);
  } else {
    log("Error on HTTP request: " + String(client.errorToString(httpResponseCode).c_str()));
    client.end();
    return false;
  }
}


/**********************************
 *         LOG FILE MANAGEMENT    *
 **********************************/
void initSD() {
  if (!SD.begin(21, SPI, SD_SPEED)) {
    Serial.println("Failed to mount SD Card!");
    ErrorBlinkLED(100);
  }
  log("SD card initialized.");
  ensureLogFile();
}

void ensureLogFile() {
  if (!SD.exists("LOG_FILE")) {
    File logFile = SD.open("LOG_FILE", FILE_WRITE);
    if (logFile) {
      logFile.println("=== Device Log Started ===");
      logFile.flush();
      logFile.close();
    }
  }
}

void log(const String &message) {
  String timestamp = getTimestamp();
  String logMessage = String(bootSession) + "_" + String(logFileIndex) + "_" + timestamp + ": " + message;
  logFileIndex++;
  Serial.println(logMessage);

  // Allocate a copy on the heap.
  char *msgCopy = strdup(logMessage.c_str());
  if (xQueueSend(logQueue, &msgCopy, portMAX_DELAY) != pdPASS) {
    Serial.println("Failed to enqueue log message!");
    free(msgCopy);
  }
}

void logFlushTask(void *parameter) {
  while (true) {
    if (uxQueueMessagesWaiting(logQueue) > 0) {
      if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
        File logFile = SD.open("LOG_FILE", FILE_APPEND);
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
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}












/**********************************
 *       UTILITY FUNCTIONS        *
 **********************************/

 void batteryMonitorTask(void *parameter) {
  // (Board-specific ADC setup might be required before using analogRead.)
  pinMode(BATTERY_PIN, INPUT);
  // Set the ADC attenuation to 11dB so that the full-scale voltage is ~3.3V.
  analogSetAttenuation(ADC_11db);
  const int sampleCount = 10;  // Number of ADC samples for averaging

  // Remove the latter. Currently the board is badly soldered and voltage measurement is not possible.
  // vTaskDelete(NULL);

  while (true) {
    long total = 0;
    for (int i = 0; i < sampleCount; i++) {
      total += analogRead(BATTERY_PIN);
      vTaskDelay(pdMS_TO_TICKS(5));  // Brief delay between readings to stabilize ADC
    }
    int averagedRawValue = total / sampleCount;
    // log average raw value
    // log("Battery raw value: " + String(averagedRawValue));

    // Convert averaged raw value to voltage.
    // For a 12-bit ADC with a 3.3V reference and a voltage divider with 2x 10k resistors:
    float voltage = ((float)averagedRawValue / 4095.0) * 3.3 * 2;
    log("Battery voltage: " + String(voltage, 3) + "V");

    // Wait for 10 seconds before next measurement.
    vTaskDelay(pdMS_TO_TICKS(BATTERY_MONITOR_INTERVAL));
  }
  Serial.println("This will never be printed");
}

void ErrorBlinkLED(int interval) {
  // stop recording as well
  recordingRequested = false;

  bool led_state = HIGH;
  while (true) {
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
      led_state = !led_state;
      // digitalWrite(LED_PIN, led_state);
      ledcWrite(LED_PIN, led_state ? 255 : 20);
      xSemaphoreGive(ledMutex);
    }
    vTaskDelay(pdMS_TO_TICKS(interval));
  }
  Serial.println("This will never be printed");
}

void stackMonitorTask(void *parameter) {
  while (true) {
    monitorStackUsage(recordAudioTaskHandle);
    monitorStackUsage(audioFileTaskHandle);
    monitorStackUsage(logFlushTaskHandle);
    monitorStackUsage(wifiConnectionTaskHandle);
    // monitorStackUsage(batteryMonitorTaskHandle); //get's currently deleted, since it's not used. can be added back if needed.
    monitorStackUsage(uploadTaskHandle);
    monitorStackUsage(persistTimeTaskHandle);
    monitorStackUsage(backendReachabilityTaskHandle);
    vTaskDelay(pdMS_TO_TICKS(10000)); // Check every 10 seconds
  }
}

void monitorStackUsage(TaskHandle_t taskHandle) {
  if (taskHandle == NULL) {
    log("Task handle is null");
    return;
  }
  UBaseType_t highWaterMark = uxTaskGetStackHighWaterMark(taskHandle);
  log("Task " + String(pcTaskGetName(taskHandle)) + " high water mark: " + String(highWaterMark));
}










/**********************************
 *         DEEP SLEEP             *
 **********************************/

void initDeepSleep() {
  // Prepare wakeup sources: 
  esp_sleep_enable_ext0_wakeup(static_cast<gpio_num_t>(BUTTON_PIN), 0); // Use EXT0 wakeup on BUTTON_PIN: trigger when the pin reads LOW.
  esp_sleep_enable_timer_wakeup(SLEEP_TIMEOUT_SEC * 1000000ULL); // Timer wakeup after SLEEP_TIMEOUT_SEC seconds

  storeCurrentTime(); // Persist current time before sleep.  
  esp_deep_sleep_start(); // Enter deep sleep.
}












/**********************************
 *         TIME MANAGEMENT    *
 **********************************/

 void initTime() {
  // Set timezone
  setenv("TZ", TIMEZONE, 1);
  tzset();
  
  struct timeval tv;
  time_t currentRtcTime = time(NULL);
  time_t persistedTime = 0;
  
  // Check if time file exists on SD card
  if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
    if (SD.exists(TIME_FILE)) {
      File timeFile = SD.open(TIME_FILE, FILE_READ);
      if (timeFile) {
        String timeStr = timeFile.readStringUntil('\n');
        timeFile.close();
        persistedTime = (time_t)timeStr.toInt();
        log("Read persisted time from SD card: " + String(persistedTime));
      }
    }
    xSemaphoreGive(sdMutex);
  }

  // Determine which time source to use
  if (persistedTime == 0) {
    // No persisted time: use default time
    tv.tv_sec = DEFAULT_TIME;
    tv.tv_usec = 0;
    settimeofday(&tv, NULL);
    storedTime = DEFAULT_TIME;
    log("Default time set: " + String(storedTime));
  } else {
    // Check if RTC has a valid updated time
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
  
  // Store time immediately to SD card to ensure consistency
  storeCurrentTime();
}

bool updateTimeFromNTP() {
  if (WiFi.status() != WL_CONNECTED) {
    log("Cannot update time: WiFi not connected");
    return false;
  }
  
  log("Updating time from NTP servers...");
  configTime(0, 0, "pool.ntp.org", "time.google.com", "time.nist.gov");
  struct tm timeinfo;

  if (getLocalTime(&timeinfo)) {
    storedTime = mktime(&timeinfo);
    log("Current time obtained.");
    storeCurrentTime();
    return true;
  } else {
    log("Failed to obtain time.");
    return false;
  }
}

void persistTimeTask(void *parameter) {
  while (true) {
      storeCurrentTime();
      vTaskDelay(pdMS_TO_TICKS(TIME_PERSIST_INTERVAL));
  }
}

void storeCurrentTime() {
  time_t current = time(NULL);
  storedTime = current;
  
  // Store time to SD card
  if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
    File timeFile = SD.open(TIME_FILE, FILE_WRITE);
    if (timeFile) {
      timeFile.println(String(current));
      timeFile.close();
      log("Stored current time to SD card: " + String(current));
    } else {
      log("Failed to open time file for writing");
    }
    xSemaphoreGive(sdMutex);
  } else {
    log("Failed to take SD mutex for time storage");
  }
}

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
 *         WIFI MANAGEMENT    *
 **********************************/

void wifiConnectionTask(void *parameter) {
  // Register event handlers during task initialization
  WiFi.onEvent(WiFiStationConnected, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_CONNECTED);
  WiFi.onEvent(WiFiGotIP, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_GOT_IP);
  // WiFi.onEvent(WiFiStationDisconnected, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  
  // Initial configuration
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(false);  // We'll handle reconnection ourselves
  
  while (true) {
    unsigned long currentTime = millis();
    
    // If we're not connected and it's time to scan
    if (!WIFIconnected && currentTime >= nextWifiScanTime) {
      log("Scanning for WiFi networks...");
      
      // Start network scan
      int networksFound = WiFi.scanNetworks();
      bool ssidFound = false;
      
      if (networksFound > 0) {
        log("Found " + String(networksFound) + " networks");
        
        // Check if our SSID is in the list
        for (int i = 0; i < networksFound; i++) {
          String scannedSSID = WiFi.SSID(i);
          if (scannedSSID == String(SS_ID)) {
            ssidFound = true;
            log("Target network '" + String(SS_ID) + "' found with signal strength: " + 
                String(WiFi.RSSI(i)) + " dBm");
            break;
          }
        }
        WiFi.scanDelete(); // Clean up scan results
        
        // If our SSID was found and we haven't exceeded max attempts, try to connect
        if (ssidFound) {
          log("Attempting to connect to: " + String(SS_ID));
          WiFi.begin(SS_ID, PASSWORD);
        } else {
          log("Target network not found in scan");
          
          // Apply exponential backoff for next scan
          currentScanInterval = std::min(currentScanInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
          nextWifiScanTime = currentTime + currentScanInterval;
          log("Next scan in " + String(currentScanInterval / 1000) + " seconds");
        }
      } else {
        log("No networks found");
        // Apply exponential backoff for next scan
        currentScanInterval = std::min(currentScanInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
        nextWifiScanTime = currentTime + currentScanInterval;
      }
    }
    
    // If connected, reset backoff parameters
    if (WIFIconnected) {
      currentScanInterval = MIN_SCAN_INTERVAL;
    }
    vTaskDelay(pdMS_TO_TICKS(1000)); // Check again after a delay
  }
}

void WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info) {
  log("WiFi connected with IP: " + WiFi.localIP().toString());
  currentScanInterval = MIN_SCAN_INTERVAL;
  WIFIconnected = true;
  
  // Reset backend check parameters
  nextBackendCheckTime = 0; // Check immediately
  currentBackendInterval = MIN_SCAN_INTERVAL;

  // Update time as soon as we get an IP address
  if (updateTimeFromNTP()) {
    log("Time synchronized with NTP successfully");
  } else {
    // Schedule a retry in 30 seconds
    if(xTaskCreatePinnedToCore(
      [](void* parameter) {
      vTaskDelay(pdMS_TO_TICKS(30000)); // 30 seconds delay
      updateTimeFromNTP();
      vTaskDelete(NULL);
      },
      "NTPRetry", 4096, NULL, 1, NULL, 0
    ) != pdPASS) {
      log("Failed to create NTP retry task");
    }
  }

  // Start file upload task when WiFi is connected
  if (uploadTaskHandle == NULL) {
    // Create task on Core 0
    if(xTaskCreatePinnedToCore(
      fileUploadTask,
      "FileUpload",
      4096,     // Stack size for HTTP operations
      NULL,
      2,        // Low priority
      &uploadTaskHandle,
      0         // Run on Core 0
    ) != pdPASS) {
      log("Failed to create file upload task");
    }
  }
}

void WiFiStationConnected(WiFiEvent_t event, WiFiEventInfo_t info) {
  log("Connected to WiFi access point");
}

/*
void WiFiStationDisconnected(WiFiEvent_t event, WiFiEventInfo_t info) {
  WIFIconnected = false;
  log("Disconnected from WiFi. Reason: " + String(info.wifi_sta_disconnected.reason));
  nextWifiScanTime = 0; // Force a scan on next wifiConnectionTask iteration
}*/

/**********************************
 *     BACKEND REACHABILITY       *
 **********************************/

 bool checkBackendReachability() {
  if (!WIFIconnected) {
    return false;
  }
  
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT);
  http.begin(TEST_ENDPOINT);

  http.addHeader("X-API-Key",
    API_KEY);  // Add the API key as a custom header

  int httpResponseCode = http.GET();
  log("Backend check response: " + String(httpResponseCode));
  
  http.end();
  return httpResponseCode == 200;
}

void backendReachabilityTask(void *parameter) {
  while (true) {
    unsigned long currentTime = millis();
    
    // Only check backend if WiFi is connected and it's time to check
    if (WIFIconnected && currentTime >= nextBackendCheckTime) {
      log("Checking backend reachability...");
      
      if (checkBackendReachability()) {
        log("Backend is reachable");
        backendReachable = true;
        // Reset backoff on success
        currentBackendInterval = MIN_SCAN_INTERVAL;
      } else {
        log("Backend is not reachable");
        backendReachable = false;
        
        // Apply exponential backoff for next check
        currentBackendInterval = std::min(currentBackendInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
        log("Next backend check in " + String(currentBackendInterval / 1000) + " seconds");
      }
      
      nextBackendCheckTime = currentTime + currentBackendInterval;
    }
    
    vTaskDelay(pdMS_TO_TICKS(5000)); // Check every 5 seconds
  }
}