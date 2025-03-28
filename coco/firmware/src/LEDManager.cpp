/**
 * @file LEDManager.cpp
 * @brief Implementation of LED management functionality
 */

#include "LEDManager.h"
#include "Application.h"
#include "config.h"

// Initialize static member variables
bool LEDManager::initialized = false;
Application* LEDManager::app = nullptr;
SemaphoreHandle_t LEDManager::ledMutex = nullptr;
int LEDManager::ledPin = LED_PIN;
int LEDManager::ledFrequency = LED_FREQUENCY;
int LEDManager::ledResolution = LED_RESOLUTION;
int LEDManager::brightness = 255;  // Default to full brightness

bool LEDManager::init(Application* appInstance, int pin, int frequency, int resolution) {
    if (initialized) {
        return true;
    }
    
    // Create mutex if not already created
    if (ledMutex == nullptr) {
        ledMutex = xSemaphoreCreateMutex();
    }
    
    // Store Application instance if provided
    if (appInstance != nullptr) {
        app = appInstance;
    } else if (app == nullptr) {
        // If not provided and not previously set, get the singleton instance
        app = Application::getInstance();
    }
    
    // Override default values if provided
    if (pin >= 0) ledPin = pin;
    if (frequency >= 0) ledFrequency = frequency;
    if (resolution >= 0) ledResolution = resolution;
    
    // Initialize LED
    ledcAttach(ledPin, ledFrequency, ledResolution);
    ledcWrite(ledPin, 0);  // LED off initially
    
    if (app) {
        app->log("LEDManager initialized");
    }
    
    initialized = true;
    return true;
}

void LEDManager::setLEDState(bool state) {
    if (!initialized) {
        init();
    }
    
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
        ledcWrite(ledPin, state ? brightness : 0);  // Use stored brightness when turning on
        xSemaphoreGive(ledMutex);
    }
}

void LEDManager::setLEDBrightness(int newBrightness) {
    if (!initialized) {
        init();
    }
    
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
        brightness = newBrightness;  // Store the brightness value
        
        // If recording is active, update the LED with new brightness immediately
        if (app->isRecordingRequested()) {
            ledcWrite(ledPin, brightness);
        }
        
        xSemaphoreGive(ledMutex);
    }
}

void LEDManager::errorBlinkLED(int interval) {
    if (!initialized) {
        init();
    }
    
    bool led_state = HIGH;
    while (true) {
        if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
            led_state = !led_state;
            ledcWrite(ledPin, led_state ? brightness : 20);  // Use stored brightness for ON state
            xSemaphoreGive(ledMutex);
        }
        vTaskDelay(pdMS_TO_TICKS(interval));
    }
}

bool LEDManager::timedErrorBlinkLED(int interval, unsigned long duration) {
    if (!initialized) {
        init();
    }
    
    bool led_state = HIGH;
    unsigned long startTime = millis();
    bool infinite = (duration == 0);
    
    while (infinite || (millis() - startTime < duration)) {
        if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
            led_state = !led_state;
            ledcWrite(ledPin, led_state ? brightness : 20);  // Use stored brightness for ON state
            xSemaphoreGive(ledMutex);
        }
        
        // Short delay to allow other tasks to run
        vTaskDelay(pdMS_TO_TICKS(interval));
    }
    
    // Turn off LED at the end
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
        ledcWrite(ledPin, 0);  // LED off
        xSemaphoreGive(ledMutex);
    }
    
    return true;
}

void LEDManager::indicateBatteryLevel(int batteryLevel, int blinkDuration, int pauseDuration) {
    if (!initialized) {
        init();
    }
    
    // Constrain battery level to 1-4 for safety
    batteryLevel = constrain(batteryLevel, 1, 4);
    
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
        // Store the current LED state
        bool originalState = ledcRead(ledPin) > 0;
        
        // Blink the LED the specified number of times
        for (int i = 0; i < batteryLevel; i++) {
            // Turn on LED
            ledcWrite(ledPin, brightness);
            delay(blinkDuration);
            
            // Turn off LED
            ledcWrite(ledPin, 0);
            
            // Only pause between blinks, not after the last one
            if (i < batteryLevel - 1) {
                delay(pauseDuration);
            }
        }
        
        // Restore original LED state after a pause
        delay(pauseDuration * 2);
        ledcWrite(ledPin, originalState ? brightness : 0);
        
        xSemaphoreGive(ledMutex);
    }
}

SemaphoreHandle_t LEDManager::getLEDMutex() {
    return ledMutex;
}
