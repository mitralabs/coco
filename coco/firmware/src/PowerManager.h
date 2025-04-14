/**
 * @file PowerManager.h
 * @brief Manages power-related functionality including battery monitoring and deep sleep
 *
 * This class handles battery voltage measurements, deep sleep modes, and wakeup sources.
 * It implements a singleton pattern and provides methods for monitoring battery levels
 * and controlling ESP32 sleep modes.
 */

#ifndef POWER_MANAGER_H
#define POWER_MANAGER_H

#include <Arduino.h>
#include "config.h"
#include "Application.h"

class PowerManager {
public:
    /**
     * @brief Get the singleton instance of PowerManager
     * @return PowerManager& Reference to the singleton instance
     */
    static PowerManager& getInstance() {
        static PowerManager instance;
        return instance;
    }
    
    // Delete copy constructor and assignment operator
    PowerManager(const PowerManager&) = delete;
    PowerManager& operator=(const PowerManager&) = delete;
    
    /**
     * @brief Initialize the power manager
     * @param app Pointer to Application instance (optional)
     * @return bool True if initialization successful
     */
    static bool init(Application* app = nullptr);
    
    // Battery monitoring
    /**
     * @brief Get the current battery voltage
     * @return float Battery voltage in volts
     */
    static float getBatteryVoltage();
    
    /**
     * @brief Get the current battery percentage
     * @return int Battery percentage (0-100)
     */
    static int getBatteryPercentage();
    
    // Deep sleep functions
    /**
     * @brief Enter deep sleep mode
     */
    static void enterDeepSleep();
    
    /**
     * @brief Configure wakeup sources for deep sleep
     * @param wakeupPin GPIO pin that can wake the device
     */
    static void configureWakeupSources(gpio_num_t wakeupPin = static_cast<gpio_num_t>(BUTTON_PIN));
    
    /**
     * @brief Check if device woke from deep sleep
     * @return bool True if device woke from deep sleep
     */
    static bool wokeFromDeepSleep();
    
    /**
     * @brief Get the cause of wakeup from deep sleep
     * @return esp_sleep_wakeup_cause_t Wakeup cause enum
     */
    static esp_sleep_wakeup_cause_t getWakeupCause();
    
    // Battery monitoring task
    /**
     * @brief Start the battery monitoring task
     * @return bool True if task started successfully
     */
    static bool startBatteryMonitorTask();
    
    /**
     * @brief Battery monitoring task function
     * @param parameter Task parameters (not used)
     */
    static void batteryMonitorTask(void* parameter);
    
    /**
     * @brief Get the handle to the battery monitor task
     * @return TaskHandle_t Task handle or NULL if not running
     */
    static TaskHandle_t getBatteryMonitorTaskHandle();
    
    /**
     * @brief Get the battery level category (1-4)
     * @return int Battery level category where:
     *         4: 75-100%
     *         3: 50-75%
     *         2: 25-50%
     *         1: 0-25%
     */
    static int getBatteryLevelCategory();
    
    /**
     * @brief Initialize and enter deep sleep mode
     */
    static void initDeepSleep();

private:
    // Private constructor for singleton pattern
    PowerManager() = default;
    
    // Private static variables for state
    static bool initialized;
    static float batteryVoltage;
    static int batteryPercentage;
    static esp_sleep_wakeup_cause_t wakeupCause;
    static TaskHandle_t batteryMonitorTaskHandle;
    static Application* app;
    
    // Battery monitoring configuration
    static const int BATTERY_ADC_PIN;
    
    /**
     * @brief Update the battery voltage and percentage values
     */
    static void updateBatteryStatus();
};

#endif // POWER_MANAGER_H
