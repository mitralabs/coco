/**
 * @file TimeManager.h
 * @brief Time management system for the Coco firmware
 * 
 * This module handles time initialization, synchronization with NTP,
 * and persistent storage of time to maintain time across reboots and sleep.
 */

#ifndef TIME_MANAGER_H
#define TIME_MANAGER_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <freertos/task.h>
#include <SD.h>
#include <time.h>
#include "config.h"
#include "Application.h"

class TimeManager {
public:
    /**
     * Initialize the time management system
     * @param app Reference to the Application singleton
     * @return True if initialization succeeded, false otherwise
     */
    static bool init(Application* app);
    
    /**
     * Get current time as formatted string (no-parameter version for LogManager compatibility)
     * @return Formatted timestamp string with default format
     */
    static String getTimestamp();
    
    /**
     * Get current time as formatted string
     * @param format Format string (strftime format)
     * @return Formatted timestamp string
     */
    static String getTimestamp(const char* format);
    
    /**
     * Update time from NTP servers (requires WiFi connection)
     * @return True if time was successfully updated, false otherwise
     */
    static bool updateFromNTP();
    
    /**
     * Store current time to SD card
     * @return True if time was successfully stored, false otherwise
     */
    static bool storeCurrentTime();
    
    /**
     * Start the time persistence task
     * @return True if task creation succeeded, false otherwise
     */
    static bool startPersistenceTask();
    
    /**
     * Get current time as time_t
     * @return Current time as time_t
     */
    static time_t getCurrentTime();

private:
    // Private constructor - singleton pattern
    TimeManager() {}
    
    // Time persistence task function
    static void persistTimeTask(void *parameter);
    
    // Static state variables
    static Application* app;
    static time_t storedTime;
    static TaskHandle_t persistTimeTaskHandle;
    static bool initialized;
};

#endif // TIME_MANAGER_H
