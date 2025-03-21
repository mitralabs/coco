/**
 * @file LogManager.h
 * @brief Logging infrastructure for the Coco firmware
 * 
 * This module provides a centralized logging system with queue-based
 * asynchronous file writing to avoid blocking operations.
 */

#ifndef LOG_MANAGER_H
#define LOG_MANAGER_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <freertos/task.h>
#include <SD.h>
#include "config.h"

class LogManager {
public:
    /**
     * Initialize the logging system
     * @param sdCardMutex Mutex for SD card access
     * @return True if initialization succeeded, false otherwise
     */
    static bool init(SemaphoreHandle_t sdCardMutex);
    
    /**
     * Log a message
     * @param message The message to log
     */
    static void log(const String &message);
    
    /**
     * Start the log flush task
     * @return True if task creation succeeded, false otherwise
     */
    static bool startLogTask();
    
    /**
     * Check if there are pending log messages
     * @return True if there are messages in the queue, false otherwise
     */
    static bool hasPendingLogs();
    
    /**
     * Set the boot session ID
     * @param session The boot session ID
     */
    static void setBootSession(int session);
    
    /**
     * Set the timestamp function
     * @param timestampFunc Function that returns timestamps as Strings
     */
    static void setTimestampProvider(String (*timestampFunc)());

private:
    // Private constructor - singleton pattern
    LogManager() {}
    
    // Log flush task function
    static void logFlushTask(void *parameter);
    
    // Static state variables
    static QueueHandle_t logQueue;
    static SemaphoreHandle_t sdMutex;
    static int bootSession;
    static int logIndex;
    static TaskHandle_t logTaskHandle;
    static bool initialized;
    static String (*getTimestampFunc)();
};

#endif // LOG_MANAGER_H
