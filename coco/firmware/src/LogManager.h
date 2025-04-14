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

#include "config.h"
#include "Application.h"

class LogManager {
public:
    /**
     * @brief Initialize the log management system
     * @param app Pointer to the Application singleton
     * @return True if initialization succeeded, false otherwise
     */
    static bool init(Application* app = nullptr);
    
    /**
     * @brief Log a message to the log file
     * 
     * The message will be enqueued and written asynchronously
     * @param message The message to log
     */
    static void log(const String &message);
    
    /**
     * @brief Check if there are pending logs in the queue
     * @return True if there are logs waiting to be written, false otherwise
     */
    static bool hasPendingLogs();
    
    // Session management
    /**
     * @brief Set the current boot session number
     * @param session The boot session number
     */
    static void setBootSession(int session);
    
    /**
     * @brief Set a function to provide timestamps for log entries
     * @param timestampFunc Function pointer that returns a timestamp string
     */
    static void setTimestampProvider(String (*timestampFunc)());
    
    // Task management
    /**
     * @brief Start the log flush task
     * @return True if task creation succeeded, false otherwise
     */
    static bool startLogTask();
    
    /**
     * @brief Get the log task handle
     * @return TaskHandle_t for the log flush task
     */
    static TaskHandle_t getLogTaskHandle() { return logTaskHandle; }

private:
    // Singleton pattern implementation
    LogManager() = default;
    LogManager(const LogManager&) = delete;
    LogManager& operator=(const LogManager&) = delete;
    
    /**
     * @brief Log flush task function
     * @param parameter Task parameter (unused)
     */
    static void logFlushTask(void *parameter);
    
    // Static state variables
    static Application* app;           // Reference to the Application singleton
    static QueueHandle_t logQueue;     // Queue managed by LogManager
    static int bootSession;            // Current boot session number
    static int logIndex;               // Index for log entries
    static TaskHandle_t logTaskHandle; // Task handle for the log flush task
    static bool initialized;           // Initialization flag
    static String (*getTimestampFunc)(); // Function pointer for timestamp provider
};

#endif // LOG_MANAGER_H
