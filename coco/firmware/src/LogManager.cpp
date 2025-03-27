/**
 * @file LogManager.cpp
 * @brief Implementation of the LogManager class
 * 
 * This file contains the implementation of the log management system,
 * including the asynchronous log writing mechanism.
 */

#include "LogManager.h"

// Initialize static members
Application* LogManager::app = nullptr;
QueueHandle_t LogManager::logQueue = NULL;
int LogManager::bootSession = 0;
int LogManager::logIndex = 0;
TaskHandle_t LogManager::logTaskHandle = NULL;
bool LogManager::initialized = false;
String (*LogManager::getTimestampFunc)() = NULL;

bool LogManager::init(Application* application) {
    // Store application reference
    app = application;
    
    // Create our own log queue
    logQueue = xQueueCreate(LOG_QUEUE_SIZE, sizeof(char*));
    if (logQueue == NULL) {
        Serial.println("Failed to create log queue!");
        return false;
    }
    
    // Set initialized flag early for basic logging
    initialized = true;
    
    // Read current log file using Application wrapper
    String currentLogContent = app->readFile(LOG_FILE);
    if (currentLogContent.isEmpty()) {
        // Create initial log file if it doesn't exist or is empty
        if (!app->overwriteFile(LOG_FILE, "=== Device Log Started ===\n")) {
            Serial.println("Failed to initialize log file!");
            return false;
        }
    }
    
    // Reset log index
    logIndex = 0;
    
    return true;
}

void LogManager::log(const String &message) {
    // Always print to Serial regardless of initialization state
    if (!initialized || !app) {
        String simpleMessage = "Not initialized: " + message;
        Serial.println(simpleMessage);
        return;
    }
    
    // Get timestamp using the provided function - use a fallback if not set
    String timestamp = getTimestampFunc ? getTimestampFunc() : "unknown";
    
    String logMessage = String(bootSession) + "_" + String(logIndex) + "_" + timestamp + ": " + message;
    logIndex++;
    
    // Print to Serial for debugging
    Serial.println(logMessage);
    
    // If queue is available, use it
    if (logQueue != NULL) {
        // Allocate a copy on the heap
        char *msgCopy = strdup(logMessage.c_str());
        if (xQueueSend(logQueue, &msgCopy, portMAX_DELAY) != pdPASS) {
            Serial.println("Failed to enqueue log message!");
            free(msgCopy);
        }
    }
}

bool LogManager::hasPendingLogs() {
    if (!initialized) {
        return false;
    }
    return uxQueueMessagesWaiting(logQueue) > 0;
}

void LogManager::setBootSession(int session) {
    bootSession = session;
}

void LogManager::setTimestampProvider(String (*timestampFunc)()) {
    getTimestampFunc = timestampFunc;
}

bool LogManager::startLogTask() {
    if (!initialized) {
        Serial.println("LogManager not initialized!");
        return false;
    }
    
    // Start log flush task
    if (xTaskCreatePinnedToCore(
        logFlushTask,
        "LogFlush",
        4096,
        NULL,
        1,
        &logTaskHandle,
        0  // Run on Core 0
    ) != pdPASS) {
        Serial.println("Failed to create log flush task!");
        return false;
    }
    
    return true;
}

void LogManager::logFlushTask(void *parameter) {
    while (true) {
        if (uxQueueMessagesWaiting(logQueue) > 0) {
            // Collect all pending messages
            String pendingLogs = "";
            char *pendingLog;
            
            // Dequeue all messages into a string
            while (xQueueReceive(logQueue, &pendingLog, 0) == pdTRUE) {
                pendingLogs += String(pendingLog) + "\n";
                free(pendingLog);
            }
            
            // Append collected logs to the log file using Application wrapper
            if (!pendingLogs.isEmpty()) {
                if (!app->addToFile(LOG_FILE, pendingLogs)) {
                    Serial.println("Failed to write logs to file!");
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}