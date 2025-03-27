/**********************************
 *           INCLUDES             *
 **********************************/
#include <Arduino.h>
#include <Preferences.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <time.h>

#include "config.h"  // Keep configuration header
#include "secrets.h" // Keep secrets
#include "Application.h" // Only include Application header

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

void ErrorBlinkLED(int interval);
void stackMonitorTask(void *parameter);
void monitorStackUsage(TaskHandle_t taskHandle);



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
      app->log("Sustained button press confirmed; proceeding with boot.");
    } else {
      // Invalid wake: button released too soon.
      app->setExternalWakeValid(0);
      app->log("Accidental wake detected.");
    }
    app->setExternalWakeTriggered(false);
  } else {
    // Normal operation: toggle recording state.
    if (digitalRead(BUTTON_PIN) == LOW) {
      // If we're currently recording, stopping will trigger deep sleep
      if (app->isRecordingRequested()) {
        app->setReadyForDeepSleep(true);
        app->log("Recording stop requested; will enter deep sleep when safe");
      }
      app->setRecordingRequested(!app->isRecordingRequested());
      app->log(app->isRecordingRequested() ? "Recording start requested" : "Recording stop requested");
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
  
  // Check wakeup cause using Application's wrapper for PowerManager
  esp_sleep_wakeup_cause_t wakeup_reason = app->getWakeupCause();

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
  app->log("Woke from deep sleep (timer).\nTimer wake up routine not yet implemented. Going back to sleep.");
  app->initDeepSleep();
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
    app->log("Valid external wake, proceeding with boot.");
    setup_from_boot();
  } else {
    app->log("Invalid external wake, entering deep sleep again.");
    app->initDeepSleep();
  }
}

void setup_from_boot() {
  app->log("\n\n\n======= Boot session: " + String(app->getBootSession()) + "=======");
  
  app->setAudioFileIndex(0);  // Reset audio file index on boot
  
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);  // Attach interrupt to the button pin

  // Initialize recording mode
  if (!app->initRecordingMode()) {
    app->log("Failed to initialize recording mode!");
    ErrorBlinkLED(100);
  }
  
  // Use stack monitor task as needed
  // if(xTaskCreatePinnedToCore(stackMonitorTask, "Stack Monitor", 4096, NULL, 1, NULL, 0) != pdPASS ) {
  //   app->log("Failed to create stackMonitor task!");
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
    monitorStackUsage(app->getBatteryMonitorTaskHandle());
    monitorStackUsage(app->getUploadTaskHandle());
    monitorStackUsage(app->getReachabilityTaskHandle());
    vTaskDelay(pdMS_TO_TICKS(10000)); // Check every 10 seconds
  }
}

void monitorStackUsage(TaskHandle_t taskHandle) {
  if (taskHandle == NULL) {
    app->log("Task handle is null");
    return;
  }
  UBaseType_t highWaterMark = uxTaskGetStackHighWaterMark(taskHandle);
  app->log("Task " + String(pcTaskGetName(taskHandle)) + " high water mark: " + String(highWaterMark));
}
