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
#include "AudioManager.h" // Add this include
#include "BackendClient.h" // Include BackendClient module

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

// Removing these function prototypes since they're now in BackendClient
// bool addToUploadQueue(const String &filename);
// String getNextUploadFile();
// bool removeFirstFromUploadQueue();
// void fileUploadTask(void *parameter);
// bool uploadFileFromBuffer(uint8_t *buffer, size_t size, const String &filename);

// Removing the batteryMonitorTask prototype since it's now in PowerManager
void ErrorBlinkLED(int interval);
void stackMonitorTask(void *parameter);
void monitorStackUsage(TaskHandle_t taskHandle);

// Removing backend-related function prototypes since they're now in BackendClient
// void backendReachabilityTask(void *parameter);
// bool checkBackendReachability();


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
  // Replace direct file operations with addToFile()
  fs->addToFile(LOG_FILE, "Woke from deep sleep (timer).\nTimer wake up routine not yet implemented. Going back to sleep.\n");
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
    
    // Replace direct file operations with addToFile()
    fs->addToFile(LOG_FILE, "Invalid external wake, entering deep sleep again.\n");
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
  
  // Initialize AudioManager - let AudioManager fully handle audio initialization
  if (!AudioManager::init(app)) {
    LogManager::log("Failed to initialize AudioManager!");
    ErrorBlinkLED(100);
  }
  
  // Initialize BackendClient
  if (!BackendClient::init(app)) {
    LogManager::log("Failed to initialize BackendClient!");
    ErrorBlinkLED(100);
  }
  
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);  // Attach interrupt to the button pin

  // Initialize recording mode (this now delegates audio init to AudioManager)
  if (!app->initRecordingMode()) {
    LogManager::log("Failed to initialize recording mode!");
    ErrorBlinkLED(100);
  }
  
  // Start the audio recording task using AudioManager
  if (!AudioManager::startRecordingTask()) {
    LogManager::log("Failed to create recordAudio task!");
    ErrorBlinkLED(100);
  }
  app->setRecordAudioTaskHandle(AudioManager::getRecordAudioTaskHandle());

  // Start the audio file task using AudioManager
  if (!AudioManager::startAudioFileTask()) {
    LogManager::log("Failed to create audioFile task!");
    ErrorBlinkLED(100);
  }
  app->setAudioFileTaskHandle(AudioManager::getAudioFileTaskHandle());

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
  
  // Start the file upload task using BackendClient
  if (!BackendClient::startUploadTask()) {
    LogManager::log("Failed to start file upload task!");
    ErrorBlinkLED(100);
  }
  
  // Start the backend reachability task using BackendClient
  if (!BackendClient::startReachabilityTask()) {
    LogManager::log("Failed to start backend reachability task!");
    ErrorBlinkLED(100);
  }
  
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