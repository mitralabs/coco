/**
 * @file LogManager.cpp
 * @brief Implementation of the LogManager class
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

// Allow early logging before full initialization
bool LogManager::init(Application* application) {
    // Store application reference
    app = application;
    
    // Set initialized flag early for basic logging
    initialized = true;
    
    // Use the queue created by the Application
    logQueue = app->getLogQueue();
    if (logQueue == NULL) {
        Serial.println("Log queue not available!");
        return false;
    }
    
    // Ensure log file exists
    File logFile;
    if (app->openFile(LOG_FILE, logFile, FILE_WRITE)) {
        if (logFile.size() == 0) {
            logFile.println("=== Device Log Started ===");
        }
        app->closeFile(logFile);
    } else {
        Serial.println("Failed to access log file!");
        return false;
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
            // Open log file for append
            File logFile;
            if (app->openFile(LOG_FILE, logFile, FILE_APPEND)) {
                char *pendingLog;
                while (xQueueReceive(logQueue, &pendingLog, 0) == pdTRUE) {
                    logFile.println(pendingLog);
                    free(pendingLog);
                }
                logFile.flush();
                app->closeFile(logFile);
            } else {
                Serial.println("Failed to open log file for batch flush!");
                // Free the memory for all pending messages since we couldn't write them
                char *pendingLog;
                while (xQueueReceive(logQueue, &pendingLog, 0) == pdTRUE) {
                    free(pendingLog);
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
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
