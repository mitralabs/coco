/**
 * @file LogManager.h
 * @brief Log management system for the Coco firmware
 * 
 * This module handles structured logging, with queue-based asynchronous writes
 * to maintain system performance while ensuring logs are properly stored.
 */

#ifndef LOG_MANAGER_H
#define LOG_MANAGER_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <SD.h>
#include "config.h"
#include "Application.h"


class LogManager {
public:
    /**
     * Initialize the log management system
     * @param app Pointer to the Application singleton
     * @return True if initialization succeeded, false otherwise
     */
    static bool init(Application* app);
    
    /**
     * Log a message to the log file
     * The message will be enqueued and written asynchronously
     * @param message The message to log
     */
    static void log(const String &message);
    
    /**
     * Start the log flush task
     * @return True if task creation succeeded, false otherwise
     */
    static bool startLogTask();
    
    /**
     * Check if there are pending logs in the queue
     * @return True if there are logs waiting to be written, false otherwise
     */
    static bool hasPendingLogs();
    
    /**
     * Set the current boot session number
     * @param session The boot session number
     */
    static void setBootSession(int session);
    
    /**
     * Set a function to provide timestamps for log entries
     * @param timestampFunc Function pointer that returns a timestamp string
     */
    static void setTimestampProvider(String (*timestampFunc)());

private:
    // Private constructor - singleton pattern
    LogManager() {}
    
    // Log flush task function
    static void logFlushTask(void *parameter);
    
    // Static state variables
    static Application* app;        // Reference to the Application singleton
    static QueueHandle_t logQueue;  // Queue managed by LogManager
    static int bootSession;         // Current boot session number
    static int logIndex;            // Index for log entries
    static TaskHandle_t logTaskHandle;  // Task handle for the log flush task
    static bool initialized;        // Initialization flag
    static String (*getTimestampFunc)(); // Function pointer for timestamp provider
};

#endif // LOG_MANAGER_H
