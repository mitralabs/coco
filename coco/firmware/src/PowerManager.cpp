/**
 * @file PowerManager.cpp
 * @brief Implementation of power management functionality
 */

#include "PowerManager.h"

// Initialize static member variables
bool PowerManager::initialized = false;
float PowerManager::batteryVoltage = 0.0f;
int PowerManager::batteryPercentage = 0;
esp_sleep_wakeup_cause_t PowerManager::wakeupCause = ESP_SLEEP_WAKEUP_UNDEFINED;
TaskHandle_t PowerManager::batteryMonitorTaskHandle = NULL;
Application* PowerManager::app = nullptr;

// Constants definition
const float PowerManager::BATTERY_MIN_VOLTAGE = 3.3f;   // Minimum battery voltage (empty)
const float PowerManager::BATTERY_MAX_VOLTAGE = 4.2f;   // Maximum battery voltage (full)
const int PowerManager::BATTERY_ADC_PIN = BATTERY_PIN;  // ADC pin used for battery voltage reading (from config.h)
const float PowerManager::VOLTAGE_DIVIDER_RATIO = 2.0f; // Based on the voltage divider used in the hardware

bool PowerManager::init(Application* appInstance) {
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
    
    // Configure ADC for battery monitoring
    pinMode(BATTERY_ADC_PIN, INPUT);
    
    // Setting the ADC attenuation to allow for battery voltage range
    analogSetAttenuation(ADC_11db);
    
    // Check if we woke from deep sleep
    wakeupCause = esp_sleep_get_wakeup_cause();
    
    // Initial battery reading
    updateBatteryStatus();
    
    if (app) {
        app->log("PowerManager initialized, battery: " + String(batteryVoltage, 2) + "V (" + 
                    String(batteryPercentage) + "%)");
    }
    
    initialized = true;
    return true;
}

float PowerManager::getBatteryVoltage() {
    if (!initialized) {
        init();
    }
    // Only update battery status when needed
    updateBatteryStatus();
    return batteryVoltage;
}

int PowerManager::getBatteryPercentage() {
    if (!initialized) {
        init();
    }
    // Only update battery status when needed
    updateBatteryStatus();
    return batteryPercentage;
}

void PowerManager::updateBatteryStatus() {
    // Take multiple readings for more stable results
    const int numReadings = 10;
    long total = 0;
    
    for (int i = 0; i < numReadings; i++) {
        total += analogRead(BATTERY_ADC_PIN);
        delay(5); // Brief delay between readings
    }
    
    int averagedRawValue = total / numReadings;
    
    // Convert ADC value to voltage
    // For a 12-bit ADC with a 3.3V reference and voltage divider
    batteryVoltage = ((float)averagedRawValue / 4095.0) * 3.3 * VOLTAGE_DIVIDER_RATIO;
    
    // Calculate battery percentage
    float percentage = ((batteryVoltage - BATTERY_MIN_VOLTAGE) / 
                       (BATTERY_MAX_VOLTAGE - BATTERY_MIN_VOLTAGE)) * 100.0f;
    batteryPercentage = constrain(percentage, 0, 100);
}

void PowerManager::enterDeepSleep(uint64_t sleepTimeMs) {
    if (app) {
        app->log("Entering deep sleep for " + String(sleepTimeMs / 1000000) + " seconds");
    }
    
    // Configure time-based wakeup
    esp_sleep_enable_timer_wakeup(sleepTimeMs); // Convert to microseconds
    
    // Final log before sleep
    if (app) {
        app->log("Going to sleep now. Goodnight!");
    }
    
    // Small delay to allow logs to be written
    delay(100);
    
    // Enter deep sleep
    esp_deep_sleep_start();
}

void PowerManager::configureWakeupSources(gpio_num_t wakeupPin) {
    // Configure external wakeup on button pin
    esp_sleep_enable_ext0_wakeup(wakeupPin, 0); // 0 = LOW trigger level
    
    // Configure timer wakeup as a backup
    esp_sleep_enable_timer_wakeup(SLEEP_TIMEOUT_SEC * 1000000ULL); // in microseconds
    
    if (app) {
        app->log("Deep sleep wakeup sources configured: PIN " + String(wakeupPin) + 
                   " and timer for " + String(SLEEP_TIMEOUT_SEC) + " seconds");
    }
}

bool PowerManager::wokeFromDeepSleep() {
    if (!initialized) {
        init();
    }
    return wakeupCause != ESP_SLEEP_WAKEUP_UNDEFINED;
}

esp_sleep_wakeup_cause_t PowerManager::getWakeupCause() {
    if (!initialized) {
        init();
    }
    return wakeupCause;
}

bool PowerManager::startBatteryMonitorTask() {
    if (!initialized) {
        if (!init()) {
            if (app) {
                app->log("Failed to initialize PowerManager!");
            }
            return false;
        }
    }
    
    // Create battery monitoring task
    if (xTaskCreatePinnedToCore(
        batteryMonitorTask,
        "BatteryMonitor",
        4096,
        NULL,
        1,
        &batteryMonitorTaskHandle,
        0  // Run on Core 0
    ) != pdPASS) {
        if (app) {
            app->log("Failed to create battery monitoring task!");
        }
        return false;
    }
    
    if (app) {
        app->log("Battery monitoring task started");
    }
    return true;
}

void PowerManager::batteryMonitorTask(void* parameter) {
    while (true) {
        float voltage = getBatteryVoltage();
        int percentage = getBatteryPercentage();
        
        if (app) {
            app->log("Battery: " + String(voltage, 2) + "V (" + String(percentage) + "%)");
        }
        
        // Wait before next measurement
        vTaskDelay(pdMS_TO_TICKS(BATTERY_MONITOR_INTERVAL));
    }
}

TaskHandle_t PowerManager::getBatteryMonitorTaskHandle() {
    return batteryMonitorTaskHandle;
}

void PowerManager::initDeepSleep() {
    // Configure wakeup sources
    configureWakeupSources(static_cast<gpio_num_t>(BUTTON_PIN));
    
    // Wait until there are no pending logs
    if (app) {
        while (app->hasPendingLogs()) {
            delay(10);
        }
        
        // Store current time through Application wrapper
        app->storeCurrentTime();
    }

    // Enter deep sleep
    enterDeepSleep(SLEEP_TIMEOUT_SEC * 1000000ULL);
    // This function doesn't return
}
