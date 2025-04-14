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
#include <esp_task_wdt.h>

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
void handleWakeup();
void HandleInitError();

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
      
      // Indicate battery level when recording starts after external wake
      app->indicateBatteryLevel();
    } else {
      // Invalid wake: button released too soon.
      app->setExternalWakeValid(0);
      app->log("Accidental wake detected.");
    }
    app->setExternalWakeTriggered(false);
  } else {
    // Normal operation: toggle recording state.
    if (digitalRead(BUTTON_PIN) == LOW) {
      app->setRecordingRequested(!app->isRecordingRequested());
      
      // Indicate battery level only when starting recording (not when stopping)
      if (app->isRecordingRequested()) {
        app->log("Recording start requested");
        app->indicateBatteryLevel();
      } else {
        app->log("Recording stop requested");
      }
    }
  }
  // Update the LED state using the LED manager
  app->setLEDState(app->isRecordingRequested());
}


/**********************************
 *       SETUP & LOOP             *
 **********************************/
void setup() {
  Serial.begin(115200);
  setCpuFrequencyMhz(CPU_FREQ_MHZ);

  // Configure watchdog with proper struct configuration
  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = WATCHDOG_TIMEOUT * 1000,  // Convert seconds to milliseconds
    .idle_core_mask = (1 << 0),             // Watch idle task on CPU0
    .trigger_panic = true                   // Trigger panic handler on timeout
  };
  esp_task_wdt_init(&wdt_config);
  
  // Initialize the application
  app = Application::getInstance();
  
  // Set up the button pin
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  // Attach interrupt to the button pin
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);

  // Create and set timer
  buttonTimer = xTimerCreate("ButtonTimer", pdMS_TO_TICKS(BUTTON_PRESS_TIME), pdFALSE, NULL, buttonTimerCallback);

  // Handle different wake-up scenarios
  handleWakeup();

  // Initialize the application with all subsystems
  if (!app->init()) {
    Serial.println("Failed to initialize application!");
    HandleInitError(); // Use new error handler
    // This function won't return
  }

}

void loop() {
  // Empty loop as tasks are running on different cores
}

/**********************************
 *       UTILITY FUNCTIONS        *
 **********************************/

 void handleWakeup() {
  esp_sleep_wakeup_cause_t wakeup_reason = app->getWakeupCause();
  unsigned long startTime; // Moved the variable declaration outside the switch

  switch (wakeup_reason) {
    case ESP_SLEEP_WAKEUP_EXT0:
      // If the wake was external, we need to wait for the button press to confirm the wake.
      app->setExternalWakeTriggered(true);
      xTimerStart(buttonTimer, 0);

      // Wait until externalWakeValid is updated (avoid indefinite wait with a timeout)
      startTime = millis(); // Now just assigning value
      while (app->getExternalWakeValid() == -1 && (millis() - startTime < 2000)) {
        delay(10);  // Small pause allowing timer callback to run.
      }

      // If decision was invalid, system will enter deep sleep via DeepSleepTask
      if (app->getExternalWakeValid() != 1) {
        app->log("Invalid external wake, will enter deep sleep soon.");
      } else {
        app->log("Valid external wake, proceeding with normal operation.");
      }
      break;
      
    default:
      // Normal power-on boot
      app->log("Normal boot");
      break;
  }
}

void HandleInitError() {
  // Check if the device was woken by button press using ESP API directly
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  
  if (wakeup_reason == ESP_SLEEP_WAKEUP_EXT0) {
    // Device was woken by button press - blink for 10 seconds to notify user
    Serial.println("Init error after button wake - blinking for 10 seconds");
    
    // Setup LED directly without using App
    ledcAttach(LED_PIN, LED_FREQUENCY, LED_RESOLUTION);
    
    // Fast blinking for 10 seconds
    unsigned long startTime = millis();
    bool ledState = true;
    
    while (millis() - startTime < 5000) {
      ledState = !ledState;
      ledcWrite(LED_PIN, ledState ? 255 : 0);
      delay(100); // 100ms interval
    }
    
    // Turn off LED
    ledcWrite(LED_PIN, 0);
  }
  
  // Log the error before deep sleep
  Serial.println("Init error - entering deep sleep");
  
  // Configure external wakeup on button pin
  esp_sleep_enable_ext0_wakeup(static_cast<gpio_num_t>(BUTTON_PIN), 0); // 0 = LOW trigger level
  
  // Configure timer wakeup as a backup
  esp_sleep_enable_timer_wakeup(SLEEP_TIMEOUT_SEC * 1000000ULL); // in microseconds
  
  // Brief delay to allow serial output
  delay(100);
  
  // Enter deep sleep
  esp_deep_sleep_start();

  // Code should not reach here
  while(1) { delay(100); }
}
