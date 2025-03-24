#ifndef POWER_MANAGER_H
#define POWER_MANAGER_H

#include <Arduino.h>
#include "config.h"

class PowerManager {
public:
    // Initialize the power manager
    static bool init();
    
    // Battery monitoring
    static float getBatteryVoltage();
    static int getBatteryPercentage();
    
    // Deep sleep functions
    static void enterDeepSleep(uint64_t sleepTimeMs = SLEEP_TIMEOUT_SEC * 1000000ULL);
    static void configureWakeupSources(gpio_num_t wakeupPin = static_cast<gpio_num_t>(BUTTON_PIN));
    static bool wokeFromDeepSleep();
    static esp_sleep_wakeup_cause_t getWakeupCause();
    
    // Battery monitoring task
    static bool startBatteryMonitorTask();
    static void batteryMonitorTask(void* parameter);
    static TaskHandle_t getBatteryMonitorTaskHandle();
    
    // Deep sleep initialization
    static void initDeepSleep();

private:
    // Private static variables for state
    static bool _initialized;
    static float _batteryVoltage;
    static int _batteryPercentage;
    static esp_sleep_wakeup_cause_t _wakeupCause;
    static TaskHandle_t _batteryMonitorTaskHandle;
    
    // Battery monitoring configuration
    static const float BATTERY_MIN_VOLTAGE;
    static const float BATTERY_MAX_VOLTAGE;
    static const int BATTERY_ADC_PIN;
    static const float VOLTAGE_DIVIDER_RATIO;
    
    // Private methods
    static void updateBatteryStatus();
};

#endif // POWER_MANAGER_H
