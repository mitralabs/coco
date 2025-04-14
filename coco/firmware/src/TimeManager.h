/**
 * @file TimeManager.h
 * @brief Time management system for the Coco firmware
 * 
 * This module handles time initialization, synchronization with NTP,
 * and persistent storage of time to maintain time across reboots and sleep.
 * It provides functionality for timestamp formatting and time persistence.
 */

#ifndef TIME_MANAGER_H
#define TIME_MANAGER_H

// Standard libraries
#include <time.h>

// ESP libraries
#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <freertos/task.h>
#include <WiFi.h>

// Project files
#include "config.h"
#include "Application.h"

class TimeManager {
public:
    /**
     * @brief Initialize the time management system
     * @param app Reference to the Application singleton
     * @return True if initialization succeeded, false otherwise
     */
    static bool init(Application* app = nullptr);
    
    // Time retrieval and formatting
    
    /**
     * @brief Get current time as formatted string (no-parameter version for LogManager compatibility)
     * @return Formatted timestamp string with default format
     */
    static String getTimestamp();
    
    /**
     * @brief Get current time as formatted string
     * @param format Format string (strftime format)
     * @return Formatted timestamp string
     */
    static String getTimestamp(const char* format);
    
    /**
     * @brief Get current time as time_t
     * @return Current time as time_t
     */
    static time_t getCurrentTime();
    
    // Time synchronization
    
    /**
     * @brief Update time from NTP servers (requires WiFi connection)
     * @return True if time was successfully updated, false otherwise
     */
    static bool updateFromNTP();
    
    // Time persistence
    
    /**
     * @brief Store current time to SD card
     * @return True if time was successfully stored, false otherwise
     */
    static bool storeCurrentTime();
    
    /**
     * @brief Start the time persistence task
     * @return True if task creation succeeded, false otherwise
     */
    static bool startPersistenceTask();
    
    /**
     * @brief Get the persistence task handle
     * @return Handle to the persistence task
     */
    static TaskHandle_t getPersistenceTaskHandle() { return persistTimeTaskHandle; }

private:
    // Private constructor - singleton pattern
    TimeManager() = default;
    
    // Delete copy constructor and assignment operator
    TimeManager(const TimeManager&) = delete;
    TimeManager& operator=(const TimeManager&) = delete;
    
    /**
     * @brief Time persistence task function
     * @param parameter Task parameters (not used)
     */
    static void persistTimeTask(void *parameter);
    
    // Static state variables
    static Application* app;
    static time_t storedTime;
    static TaskHandle_t persistTimeTaskHandle;
    static bool initialized;
};

#endif // TIME_MANAGER_H
