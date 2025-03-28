/**
 * @file LEDManager.cpp
 * @brief Implementation of LED management functionality
 */

#include "LEDManager.h"
#include "Application.h"
#include "config.h"

// Initialize static member variables
bool LEDManager::initialized = false;
LEDManager* LEDManager::instance = nullptr;
Application* LEDManager::app = nullptr;

LEDManager::LEDManager() {
    ledMutex = xSemaphoreCreateMutex();
    ledPin = LED_PIN;
    ledFrequency = LED_FREQUENCY;
    ledResolution = LED_RESOLUTION;
}

LEDManager* LEDManager::getInstance() {
    if (instance == nullptr) {
        instance = new LEDManager();
    }
    return instance;
}

bool LEDManager::init(Application* appInstance, int pin, int frequency, int resolution) {
    if (initialized) {
        return true;
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
        ledcWrite(ledPin, state ? 255 : 0);  // 255 is full brightness, 0 is off
        xSemaphoreGive(ledMutex);
    }
}

void LEDManager::setLEDBrightness(int brightness) {
    if (!initialized) {
        init();
    }
    
    if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdPASS) {
        ledcWrite(ledPin, brightness);
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
            ledcWrite(ledPin, led_state ? 255 : 20);
            xSemaphoreGive(ledMutex);
        }
        vTaskDelay(pdMS_TO_TICKS(interval));
    }
}

SemaphoreHandle_t LEDManager::getLEDMutex() {
    return ledMutex;
}
