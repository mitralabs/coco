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
#include <HTTPClient.h>
#include <time.h>

#include "config.h"  // New configuration header
#include "secrets.h"
#include "Application.h" // Include Application class first to avoid duplicate definitions
#include "LogManager.h" // Include new LogManager
#include "TimeManager.h" // Include TimeManager module
#include "FileSystem.h" // Include FileSystem module
#include "PowerManager.h" // Include PowerManager module
#include "WifiManager.h" // Include new WifiManager module

/***********************************************
 *     GLOBAL VARIABLES AND DATA STRUCTURES    *
 ***********************************************/
// Application instance
Application* app = nullptr;

// Timer handle for button presses - will be stored in app during initialization
TimerHandle_t buttonTimer = NULL;

/**********************************
 *      FUNCTION PROTOTYPES       *
 **********************************/
void setup_from_timer();
void setup_from_external();
void setup_from_boot();

void recordAudio(void *parameter);
void audioFileTask(void *parameter);
bool addToUploadQueue(const String &filename);

String getNextUploadFile();
bool removeFirstFromUploadQueue();
void fileUploadTask(void *parameter);
bool uploadFileFromBuffer(uint8_t *buffer, size_t size, const String &filename);

// Removing the batteryMonitorTask prototype since it's now in PowerManager
void ErrorBlinkLED(int interval);
void stackMonitorTask(void *parameter);
void monitorStackUsage(TaskHandle_t taskHandle);

// Removing WiFi-related function prototypes since they're now in WifiManager
void backendReachabilityTask(void *parameter);
bool checkBackendReachability();


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
  if (app->isExternalWakeTriggered()) {
    // Check if the button is still pressed after BUTTON_PRESS_TIME.
    if (digitalRead(BUTTON_PIN) == LOW) {
      // Confirmed: valid wakeup
      app->setExternalWakeValid(1);
      app->setRecordingRequested(true);
      LogManager::log("Sustained button press confirmed; proceeding with boot.");
    } else {
      // Invalid wake: button released too soon.
      app->setExternalWakeValid(0);
      LogManager::log("Accidental wake detected.");
    }
    app->setExternalWakeTriggered(false);
  } else {
    // Normal operation: toggle recording state.
    if (digitalRead(BUTTON_PIN) == LOW) {
      // If we're currently recording, stopping will trigger deep sleep
      if (app->isRecordingRequested()) {
        app->setReadyForDeepSleep(true);
        LogManager::log("Recording stop requested; will enter deep sleep when safe");
      }
      app->setRecordingRequested(!app->isRecordingRequested());
      LogManager::log(app->isRecordingRequested() ? "Recording start requested" : "Recording stop requested");
    }
  }
  // Update the LED state.
  if (xSemaphoreTake(app->getLedMutex(), portMAX_DELAY) == pdPASS) {
    ledcWrite(LED_PIN, app->isRecordingRequested() ? 255 : 0);  // 255 is full brightness, 0 is off
    xSemaphoreGive(app->getLedMutex());
  }
}

/**********************************
 *       SETUP & LOOP             *
 **********************************/
void setup() {
  Serial.begin(115200);
  setCpuFrequencyMhz(CPU_FREQ_MHZ);  

  // Initialize the application
  app = Application::getInstance();
  
  ledcAttach(LED_PIN, LED_FREQUENCY, LED_RESOLUTION);
  ledcWrite(LED_PIN, 0);  // LED off initially

  // Set up the button pin
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // Initialize the application before using any of its features
  if (!app->init()) {
    Serial.println("Failed to initialize application!");
    while(1) { delay(100); } // Halt
  }

  // Create and set timer
  buttonTimer = xTimerCreate("ButtonTimer", pdMS_TO_TICKS(BUTTON_PRESS_TIME), pdFALSE, NULL, buttonTimerCallback);
  
  // Initialize PowerManager
  if (!PowerManager::init()) {
    Serial.println("Failed to initialize PowerManager!");
    while(1) { delay(100); } // Halt
  }
  
  // Check wakeup cause using PowerManager
  esp_sleep_wakeup_cause_t wakeup_reason = PowerManager::getWakeupCause();

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
  // Initialize FileSystem for log operations
  FileSystem* fs = FileSystem::getInstance();
  if (!fs->init()) {
    Serial.println("Failed to initialize FileSystem!");
    while(1) { delay(100); } // Halt
  }
  
  // Write to log and enter deep sleep again.
  File logFile;
  if (fs->openFile(LOG_FILE, logFile, FILE_APPEND)) {
    logFile.println("Woke from deep sleep (timer).");
    logFile.println("Timer wake up routine not yet implemented. Going back to sleep.");
    logFile.flush();
    fs->closeFile(logFile);
  }
  PowerManager::initDeepSleep();
}

void setup_from_external() {
  // If the wake was external, we need to wait for the button press to confirm the wake.
  app->setExternalWakeTriggered(true);
  xTimerStart(buttonTimer, 0);

  // Wait until externalWakeValid is updated (avoid indefinite wait with a timeout)
  unsigned long startTime = millis();
  while (app->getExternalWakeValid() == -1 && (millis() - startTime < 2000)) {
    delay(10);  // Small pause allowing timer callback to run.
  }

  // If decision was valid, proceed with boot.
  if (app->getExternalWakeValid() == 1) {
    LogManager::log("Valid external wake, proceeding with boot.");
    setup_from_boot();
  } else {
    // Initialize FileSystem for log operations
    FileSystem* fs = FileSystem::getInstance();
    if (!fs->init()) {
      Serial.println("Failed to initialize FileSystem!");
      while(1) { delay(100); } // Halt
    }
    
    // Write to log and enter deep sleep again.
    File logFile;
    if (fs->openFile(LOG_FILE, logFile, FILE_APPEND)) {
      logFile.println("Invalid external wake, entering deep sleep again.");
      logFile.flush();
      fs->closeFile(logFile);
    }
    PowerManager::initDeepSleep();
  }
}

void setup_from_boot() {
  // Initialize FileSystem first as other modules depend on it
  FileSystem* fs = FileSystem::getInstance();
  if (!fs->init()) {
    Serial.println("Failed to initialize FileSystem!");
    ErrorBlinkLED(100);
  }
  
  // Initialize TimeManager after FileSystem is initialized
  if (!TimeManager::init(app)) {
    Serial.println("Failed to initialize TimeManager!");
    ErrorBlinkLED(100);
  }
  
  // Initialize LogManager after TimeManager is initialized
  if (!LogManager::init(app)) {
    Serial.println("Failed to initialize LogManager!");
    ErrorBlinkLED(100);
  }
  
  // Set the boot session for log messages
  LogManager::setBootSession(app->getBootSession());
  
  // Now that TimeManager is initialized, set it as the timestamp provider
  LogManager::setTimestampProvider(TimeManager::getTimestamp);
  
  LogManager::log("\n\n\n======= Boot session: " + String(app->getBootSession()) + "=======");
  
  // Start the log task
  if (!LogManager::startLogTask()) {
    LogManager::log("Failed to start log task!");
    ErrorBlinkLED(100);
  }
  
  app->setAudioFileIndex(0);  // Reset audio file index on boot
  
  // Start the time persistence task after TimeManager is fully initialized
  if (!TimeManager::startPersistenceTask()) {
    LogManager::log("Failed to start time persistence task!");
    ErrorBlinkLED(100);
  }
  
  // Initialize WifiManager
  if (!WifiManager::init(app)) {
    LogManager::log("Failed to initialize WifiManager!");
    ErrorBlinkLED(100);
  }
  
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);  // Attach interrupt to the button pin

  // Initialize recording mode through app
  if (!app->initRecordingMode()) {
    LogManager::log("Failed to initialize recording mode!");
    ErrorBlinkLED(100);
  }
  
  // Tasks on Core 1
  // Name, Stack size, Priority, Task handle, Core
  TaskHandle_t recordAudioTaskHandle = NULL;
  if(xTaskCreatePinnedToCore(recordAudio, "Record Loop", 4096, NULL, 1, &recordAudioTaskHandle, 1) != pdPASS ) {
    LogManager::log("Failed to create recordAudio task!");
    ErrorBlinkLED(100);
  }
  app->setRecordAudioTaskHandle(recordAudioTaskHandle);

  // Tasks on Core 0
  TaskHandle_t audioFileTaskHandle = NULL;
  if(xTaskCreatePinnedToCore(audioFileTask, "Audio File Save", 4096, NULL, 4, &audioFileTaskHandle, 0) != pdPASS ) {
    LogManager::log("Failed to create audioFile task!");
    ErrorBlinkLED(100);
  }
  app->setAudioFileTaskHandle(audioFileTaskHandle);

  // Start WiFi connection task using WifiManager
  if (!WifiManager::startConnectionTask()) {
    LogManager::log("Failed to start WiFi connection task!");
    ErrorBlinkLED(100);
  }

  // Use PowerManager to start battery monitor task
  if (!PowerManager::startBatteryMonitorTask()) {
    LogManager::log("Failed to start battery monitor task!");
    ErrorBlinkLED(100);
  }
  
  // Store the task handle in the app for stack monitoring
  app->setBatteryMonitorTaskHandle(PowerManager::getBatteryMonitorTaskHandle());
  
  // This task can be used to monitor the stack usage. It can be commented / uncommented as needed.
  // if(xTaskCreatePinnedToCore(stackMonitorTask, "Stack Monitor", 4096, NULL, 1, NULL, 0) != pdPASS ) {
  //   LogManager::log("Failed to create stackMonitor task!");
  //   ErrorBlinkLED(100);
  // }
}

void loop() {
  // Empty loop as tasks are running on different cores
}

/**********************************
 *         RECORDING FUNCTIONS    *
 **********************************/
void recordAudio(void *parameter) {
  static bool wasRecording = false;
  static unsigned long lastRecordStart = 0;
  
  while (true) {
    bool currentlyRequested = app->isRecordingRequested();
    
    if (currentlyRequested) {
      lastRecordStart = millis(); // Track when recording started
      AudioBuffer audio;

      // Use TimeManager for timestamp
      String ts = TimeManager::getTimestamp();
      snprintf(audio.timestamp, sizeof(audio.timestamp), "%s", ts.c_str());
      
      // Use "start" marker for the first chunk, then MIDDLE afterwards.
      if (!wasRecording) {
        wasRecording = true;
        audio.type = START;
        LogManager::log("Started audio recording");
      } else {
        audio.type = MIDDLE;
      }
      
      audio.buffer = app->getI2S()->recordWAV(RECORD_TIME, &audio.size);
      
      if (audio.buffer == NULL || audio.size == 0) {
        LogManager::log("Failed to record audio: buffer is empty");
        free(audio.buffer); // Just in case
        vTaskDelay(pdMS_TO_TICKS(10));
        continue;
      }
      
      if (xQueueSend(app->getAudioQueue(), &audio, pdMS_TO_TICKS(1000)) != pdPASS) {
        LogManager::log("Failed to enqueue audio buffer!");
        free(audio.buffer);
      }
    } else {
      // If we were recording but recording is now off, record a final chunk with "end" marker.
      if (wasRecording) {
        AudioBuffer audio;
        String ts = TimeManager::getTimestamp();
        snprintf(audio.timestamp, sizeof(audio.timestamp), "%s", ts.c_str());
        audio.type = END;
        audio.buffer = app->getI2S()->recordWAV(RECORD_TIME, &audio.size);
        
        if (audio.buffer == NULL || audio.size == 0) {
          LogManager::log("Failed to record final audio: buffer is empty");
          wasRecording = false;
          free(audio.buffer); // Just in case
          continue;
        }
        
        if (xQueueSend(app->getAudioQueue(), &audio, pdMS_TO_TICKS(1000)) != pdPASS) {
          LogManager::log("Failed to enqueue final audio buffer!");
          free(audio.buffer);
        }
        wasRecording = false;
        LogManager::log("Ended audio recording");
      }
    }
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void audioFileTask(void *parameter) {
  AudioBuffer audio;
  FileSystem* fs = FileSystem::getInstance();
  
  while (true) {
    QueueHandle_t audioQueue = app->getAudioQueue();
    while (xQueueReceive(audioQueue, &audio, pdMS_TO_TICKS(10)) == pdTRUE) {
      String prefix = "_";
      if (audio.type == START)
        prefix += "start";
      else if (audio.type == END)
        prefix += "end";
      else if (audio.type == MIDDLE)
        prefix += "middle";
        
      String fileName = String(RECORDINGS_DIR) + "/" +
                        String(app->getBootSession()) + "_" +
                        String(app->getAudioFileIndex()) + "_" +
                        String(audio.timestamp) +
                        prefix + ".wav";
      app->setAudioFileIndex(app->getAudioFileIndex() + 1);

      File curr_file;
      if (fs->openFile(fileName, curr_file, FILE_WRITE)) {
        if (curr_file.write(audio.buffer, audio.size) != audio.size) {
          LogManager::log("Failed to write audio data to file: " + fileName);
        } else {
          LogManager::log("Audio recorded and saved: " + fileName);
          app->setWavFilesAvailable(true);

          // Add to upload queue while we have the mutex
          if (fs->addToUploadQueue(fileName)) {
            LogManager::log("Added to upload queue: " + fileName);
          } else {
            LogManager::log("Failed to add to upload queue: " + fileName);
          }
        }
        fs->closeFile(curr_file);
      } else {
        LogManager::log("Failed to open file for writing: " + fileName);
      }
      free(audio.buffer);
    }

    // Check if we should enter deep sleep
    if (app->isReadyForDeepSleep() && 
        !app->isRecordingRequested() && 
        !app->isRecordingActive() &&
        uxQueueMessagesWaiting(app->getAudioQueue()) == 0) {
    
      // Make sure log queue is also empty before sleep
      if (!LogManager::hasPendingLogs()) {
        LogManager::log("Recording stopped and all data processed. Entering deep sleep.");
        vTaskDelay(pdMS_TO_TICKS(500)); // Short delay to allow log to be written
        PowerManager::initDeepSleep();
      }
    }

    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void fileUploadTask(void *parameter) {
  FileSystem* fs = FileSystem::getInstance();
  
  while (true) {
    // Only proceed if WiFi is connected
    if (app->isWifiConnected() && app->isBackendReachable()) {
      // Check if we're already uploading
      SemaphoreHandle_t uploadMutex = app->getUploadMutex();
      if (xSemaphoreTake(uploadMutex, 0) == pdTRUE) {
        app->setUploadInProgress(true);
        
        // Get the next file to upload from queue
        String nextFile = fs->getNextUploadFile();
        
        if (nextFile.length() > 0) {
          LogManager::log("Processing next file from queue: " + nextFile);
          
          // Try to take SD card mutex
          SemaphoreHandle_t sdMutex = fs->getSDMutex();
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
                    LogManager::log("Error reading file into buffer");
                    free(uploadBuffer.buffer);
                    uploadBuffer.buffer = NULL;
                  }
                } else {
                  LogManager::log("Failed to allocate memory for file upload");
                }
                
                file.close();
              }
            }
            
            // Release SD mutex before uploading
            xSemaphoreGive(sdMutex);
            
            if (uploadBuffer.buffer) {
              // Upload the file from RAM
              LogManager::log("Uploading file from buffer: " + uploadBuffer.filename);
              bool uploadSuccess = uploadFileFromBuffer(uploadBuffer.buffer, uploadBuffer.size, uploadBuffer.filename);
              
              // If upload was successful, delete the file and remove from queue
              if (uploadSuccess) {
                LogManager::log("Upload successful, deleting file");
                
                // Take SD mutex again just for deletion
                if (xSemaphoreTake(sdMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
                  if (SD.remove(uploadBuffer.filename)) {
                    LogManager::log("File deleted: " + uploadBuffer.filename);
                  } else {
                    LogManager::log("Failed to delete file: " + uploadBuffer.filename);
                  }
                  xSemaphoreGive(sdMutex);
                }
                
                // Remove from queue
                fs->removeFirstFromUploadQueue();
              } else {
                LogManager::log("Upload failed for: " + uploadBuffer.filename);
              }
              
              // Free the buffer memory
              free(uploadBuffer.buffer);
            }
          } else {
            LogManager::log("Could not get SD card mutex for file upload");
          }
        } else {
          // No files in queue
          app->setWavFilesAvailable(false);
          LogManager::log("No files in upload queue");
        }
        
        app->setUploadInProgress(false);
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
  
  SemaphoreHandle_t httpMutex = app->getHttpMutex();
  if (xSemaphoreTake(httpMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
    LogManager::log("Could not get HTTP mutex for file upload");
    return false;
  }
  
  // Extract just the filename without the path for the request
  String bareFilename = filename.substring(filename.lastIndexOf('/') + 1);
  
  // Initialize HTTP client
  HTTPClient client;

  // Check WiFi connection before proceeding
  if (WiFi.status() != WL_CONNECTED) {
    LogManager::log("WiFi not connected, aborting upload");
    xSemaphoreGive(httpMutex);
    return false;
  }
  
  // Add timeout settings
  client.setTimeout(HTTP_TIMEOUT);

  client.begin(API_ENDPOINT);
  client.addHeader("Content-Type", "audio/wav");
  client.addHeader("X-API-Key", API_KEY);  // Add the API key as a custom header
  client.addHeader("Content-Disposition",
                   "form-data; name=\"file\"; filename=\"" +
                       String(bareFilename) + "\"");

  // Send the request with the file data from buffer
  int httpResponseCode = client.sendRequest("POST", buffer, size);
  
  if (httpResponseCode > 0) {
    LogManager::log("HTTP Response code: " + String(httpResponseCode));
    String response = client.getString();
    LogManager::log("Server response: " + response);
    client.end();
    bool success = (httpResponseCode == HTTP_CODE_OK || httpResponseCode == HTTP_CODE_CREATED);
    if (!success) {
      // If we get an HTTP error response, mark backend as unavailable
      app->setBackendReachable(false);
      app->setNextBackendCheckTime(millis()); // Trigger an immediate recheck
    }
    xSemaphoreGive(httpMutex);
    return success;
  } else {
    LogManager::log("Error on HTTP request: " + String(client.errorToString(httpResponseCode).c_str()));
    client.end();
    // Network error, mark backend as unavailable
    app->setBackendReachable(false);
    app->setNextBackendCheckTime(millis()); // Trigger an immediate recheck
    xSemaphoreGive(httpMutex);
    return false;
  }
}

/**********************************
 *       UTILITY FUNCTIONS        *
 **********************************/

void ErrorBlinkLED(int interval) {
  // stop recording as well
  app->setRecordingRequested(false);

  bool led_state = HIGH;
  while (true) {
    SemaphoreHandle_t ledMutex = app->getLedMutex();
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
      led_state = !led_state;
      ledcWrite(LED_PIN, led_state ? 255 : 20);
      xSemaphoreGive(ledMutex);
    }
    vTaskDelay(pdMS_TO_TICKS(interval));
  }
}

void stackMonitorTask(void *parameter) {
  while (true) {
    monitorStackUsage(app->getRecordAudioTaskHandle());
    monitorStackUsage(app->getAudioFileTaskHandle());
    monitorStackUsage(app->getWifiConnectionTaskHandle());
    monitorStackUsage(PowerManager::getBatteryMonitorTaskHandle()); // Use the getter instead of directly accessing private member
    monitorStackUsage(app->getUploadTaskHandle());
    monitorStackUsage(app->getBackendReachabilityTaskHandle());
    vTaskDelay(pdMS_TO_TICKS(10000)); // Check every 10 seconds
  }
}

void monitorStackUsage(TaskHandle_t taskHandle) {
  if (taskHandle == NULL) {
    LogManager::log("Task handle is null");
    return;
  }
  UBaseType_t highWaterMark = uxTaskGetStackHighWaterMark(taskHandle);
  LogManager::log("Task " + String(pcTaskGetName(taskHandle)) + " high water mark: " + String(highWaterMark));
}

/**********************************
 *    BACKEND REACHABILITY CHECK  *
 **********************************/
bool checkBackendReachability() {
  if (!WifiManager::isConnected()) {
    return false;
  }
  
  SemaphoreHandle_t httpMutex = app->getHttpMutex();
  if (xSemaphoreTake(httpMutex, pdMS_TO_TICKS(2000)) != pdTRUE) {
    LogManager::log("HTTP mutex busy, skipping backend check");
    return app->isBackendReachable();  // Return current state
  }
  
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT);
  http.begin(TEST_ENDPOINT);

  http.addHeader("X-API-Key", API_KEY);  // Add the API key as a custom header

  int httpResponseCode = http.GET();
  LogManager::log("Backend check response: " + String(httpResponseCode));
  
  http.end();
  xSemaphoreGive(httpMutex);
  return httpResponseCode == 200;
}

void backendReachabilityTask(void *parameter) {
  const unsigned long RECHECK_INTERVAL = 600000; // Recheck every 10 minutes even when connected
  unsigned long lastSuccessfulCheck = 0;
  
  while (true) {
    unsigned long currentTime = millis();
    bool shouldCheck = false;
    
    // Only check backend if WiFi is connected
    if (WifiManager::isConnected()) {
      // Check if:
      // 1. Backend status is unknown (not reachable) OR
      // 2. It's time for a periodic recheck when connected
      if (!app->isBackendReachable() || 
          (app->isBackendReachable() && (currentTime - lastSuccessfulCheck >= RECHECK_INTERVAL))) {
        
        // Check if it's time according to our backoff strategy
        if (currentTime >= app->getNextBackendCheckTime()) {
          shouldCheck = true;
        }
      }
      
      if (shouldCheck) {
        LogManager::log("Checking backend reachability...");
        
        if (checkBackendReachability()) {
          LogManager::log("Backend is reachable");
          app->setBackendReachable(true);
          // Reset backoff on success
          app->setCurrentBackendInterval(MIN_SCAN_INTERVAL);
          // Record successful check time
          lastSuccessfulCheck = currentTime;
        } else {
          LogManager::log("Backend is not reachable");
          app->setBackendReachable(false);
          
          // Apply exponential backoff for next check
          unsigned long currentInterval = app->getCurrentBackendInterval();
          unsigned long newInterval = std::min(currentInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
          app->setCurrentBackendInterval(newInterval);
          LogManager::log("Next backend check in " + String(newInterval / 1000) + " seconds");
        }
        
        app->setNextBackendCheckTime(currentTime + app->getCurrentBackendInterval());
      }
    } else {
      // Reset status if WiFi disconnects
      app->setBackendReachable(false);
    }
    
    vTaskDelay(pdMS_TO_TICKS(5000)); // Task yield interval
  }
}