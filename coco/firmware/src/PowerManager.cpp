#include "PowerManager.h"
#include "LogManager.h"
#include "TimeManager.h"

// Initialize static member variables
bool PowerManager::_initialized = false;
float PowerManager::_batteryVoltage = 0.0f;
int PowerManager::_batteryPercentage = 0;
esp_sleep_wakeup_cause_t PowerManager::_wakeupCause = ESP_SLEEP_WAKEUP_UNDEFINED;
TaskHandle_t PowerManager::_batteryMonitorTaskHandle = NULL;

// Constants definition
const float PowerManager::BATTERY_MIN_VOLTAGE = 3.3f;   // Minimum battery voltage (empty)
const float PowerManager::BATTERY_MAX_VOLTAGE = 4.2f;   // Maximum battery voltage (full)
const int PowerManager::BATTERY_ADC_PIN = BATTERY_PIN;  // ADC pin used for battery voltage reading (from config.h)
const float PowerManager::VOLTAGE_DIVIDER_RATIO = 2.0f; // Based on the voltage divider used in the hardware

bool PowerManager::init() {
    if (_initialized) {
        return true;
    }
    
    // Configure ADC for battery monitoring
    pinMode(BATTERY_ADC_PIN, INPUT);
    
    // Setting the ADC attenuation to allow for battery voltage range
    analogSetAttenuation(ADC_11db);
    
    // Check if we woke from deep sleep
    _wakeupCause = esp_sleep_get_wakeup_cause();
    
    // Initial battery reading
    updateBatteryStatus();
    
    LogManager::log("PowerManager initialized, battery: " + String(_batteryVoltage, 2) + "V (" + 
                    String(_batteryPercentage) + "%)");
    
    _initialized = true;
    return true;
}

float PowerManager::getBatteryVoltage() {
    if (!_initialized) {
        init();
    }
    updateBatteryStatus();
    return _batteryVoltage;
}

int PowerManager::getBatteryPercentage() {
    if (!_initialized) {
        init();
    }
    updateBatteryStatus();
    return _batteryPercentage;
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
    _batteryVoltage = ((float)averagedRawValue / 4095.0) * 3.3 * VOLTAGE_DIVIDER_RATIO;
    
    // Calculate battery percentage
    float percentage = ((_batteryVoltage - BATTERY_MIN_VOLTAGE) / 
                       (BATTERY_MAX_VOLTAGE - BATTERY_MIN_VOLTAGE)) * 100.0f;
    _batteryPercentage = constrain(percentage, 0, 100);
}

void PowerManager::enterDeepSleep(uint64_t sleepTimeMs) {
    LogManager::log("Entering deep sleep for " + String(sleepTimeMs / 1000000) + " seconds");
    
    // Configure time-based wakeup
    esp_sleep_enable_timer_wakeup(sleepTimeMs); // Convert to microseconds
    
    // Final log before sleep
    LogManager::log("Going to sleep now. Goodnight!");
    
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
    
    LogManager::log("Deep sleep wakeup sources configured: PIN " + String(wakeupPin) + 
                   " and timer for " + String(SLEEP_TIMEOUT_SEC) + " seconds");
}

bool PowerManager::wokeFromDeepSleep() {
    if (!_initialized) {
        init();
    }
    return _wakeupCause != ESP_SLEEP_WAKEUP_UNDEFINED;
}

esp_sleep_wakeup_cause_t PowerManager::getWakeupCause() {
    if (!_initialized) {
        init();
    }
    return _wakeupCause;
}

bool PowerManager::startBatteryMonitorTask() {
    if (!_initialized) {
        if (!init()) {
            LogManager::log("Failed to initialize PowerManager!");
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
        &_batteryMonitorTaskHandle,
        0  // Run on Core 0
    ) != pdPASS) {
        LogManager::log("Failed to create battery monitoring task!");
        return false;
    }
    
    LogManager::log("Battery monitoring task started");
    return true;
}

void PowerManager::batteryMonitorTask(void* parameter) {
    while (true) {
        float voltage = getBatteryVoltage();
        int percentage = getBatteryPercentage();
        
        LogManager::log("Battery: " + String(voltage, 2) + "V (" + String(percentage) + "%)");
        
        // Wait before next measurement
        vTaskDelay(pdMS_TO_TICKS(BATTERY_MONITOR_INTERVAL));
    }
}

TaskHandle_t PowerManager::getBatteryMonitorTaskHandle() {
    return _batteryMonitorTaskHandle;
}

void PowerManager::initDeepSleep() {
    // Configure wakeup sources
    configureWakeupSources(static_cast<gpio_num_t>(BUTTON_PIN));
    
    // Wait until there are no pending logs
    while (LogManager::hasPendingLogs()) {
        delay(10);
    }
    
    // Store current time before sleep (assuming TimeManager is available)
    if (TimeManager::storeCurrentTime) {
        TimeManager::storeCurrentTime();
    }
    
    // Enter deep sleep
    enterDeepSleep(SLEEP_TIMEOUT_SEC * 1000000ULL);
    // This function doesn't return
}
