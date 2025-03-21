/**
 * @file LogManager.cpp
 * @brief Implementation of the LogManager class
 */

#include "LogManager.h"

// Initialize static members
QueueHandle_t LogManager::logQueue = NULL;
SemaphoreHandle_t LogManager::sdMutex = NULL;
int LogManager::bootSession = 0;
int LogManager::logIndex = 0;
TaskHandle_t LogManager::logTaskHandle = NULL;
bool LogManager::initialized = false;
String (*LogManager::getTimestampFunc)() = NULL;

bool LogManager::init(SemaphoreHandle_t sdCardMutex) {
    // Store SD card mutex
    sdMutex = sdCardMutex;
    
    // Create log queue
    logQueue = xQueueCreate(LOG_QUEUE_SIZE, sizeof(char*));
    if (logQueue == NULL) {
        Serial.println("Failed to create log queue!");
        return false;
    }
    
    // Ensure log file exists
    if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
        if (!SD.exists(LOG_FILE)) {
            File file = SD.open(LOG_FILE, FILE_WRITE);
            if (file) {
                file.println("=== Device Log Started ===");
                file.flush();
                file.close();
            } else {
                xSemaphoreGive(sdMutex);
                return false;
            }
        }
        xSemaphoreGive(sdMutex);
    } else {
        return false;
    }
    
    // Reset log index
    logIndex = 0;
    
    // Set initialization flag
    initialized = true;
    
    return true;
}

void LogManager::log(const String &message) {
    if (!initialized) {
        Serial.println("LogManager not initialized!");
        return;
    }
    
    // Get timestamp using the provided function
    String timestamp = getTimestampFunc ? getTimestampFunc() : "unknown";
    
    String logMessage = String(bootSession) + "_" + String(logIndex) + "_" + timestamp + ": " + message;
    logIndex++;
    
    // Print to Serial for debugging
    Serial.println(logMessage);
    
    // Allocate a copy on the heap
    char *msgCopy = strdup(logMessage.c_str());
    if (xQueueSend(logQueue, &msgCopy, portMAX_DELAY) != pdPASS) {
        Serial.println("Failed to enqueue log message!");
        free(msgCopy);
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
            if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
                File logFile = SD.open(LOG_FILE, FILE_APPEND);
                if (logFile) {
                    char *pendingLog;
                    while (xQueueReceive(logQueue, &pendingLog, 0) == pdTRUE) {
                        logFile.println(pendingLog);
                        free(pendingLog);
                    }
                    logFile.flush();
                    logFile.close();
                } else {
                    Serial.println("Failed to open log file for batch flush!");
                    char *pendingLog;
                    while (xQueueReceive(logQueue, &pendingLog, 0) == pdTRUE) {
                        free(pendingLog);
                    }
                }
                xSemaphoreGive(sdMutex);
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
