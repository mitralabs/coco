/**
 * @file TimeManager.cpp
 * @brief Implementation of the TimeManager class
 */

#include "TimeManager.h"
#include "LogManager.h" // Include LogManager for consistent logging
#include <WiFi.h> // Include WiFi library for connectivity checks

// Initialize static members
Application* TimeManager::app = NULL;
time_t TimeManager::storedTime = 0;
TaskHandle_t TimeManager::persistTimeTaskHandle = NULL;
bool TimeManager::initialized = false;

bool TimeManager::init(Application* application) {
    // Store application instance
    app = application;
    
    // Set timezone
    setenv("TZ", TIMEZONE, 1);
    tzset();
    
    struct timeval tv;
    time_t currentRtcTime = time(NULL);
    time_t persistedTime = 0;
    
    // Check if time file exists on SD card
    SemaphoreHandle_t sdMutex = app->getSDMutex();
    if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
        if (SD.exists(TIME_FILE)) {
            File timeFile = SD.open(TIME_FILE, FILE_READ);
            if (timeFile) {
                String timeStr = timeFile.readStringUntil('\n');
                timeFile.close();
                persistedTime = (time_t)timeStr.toInt();
                LogManager::log("Read persisted time from SD card: " + String(persistedTime));
            }
        }
        xSemaphoreGive(sdMutex);
    } else {
        LogManager::log("Failed to take SD mutex for time initialization");
        return false;
    }

    // Determine which time source to use
    if (persistedTime == 0) {
        // No persisted time: use default time
        tv.tv_sec = DEFAULT_TIME;
        tv.tv_usec = 0;
        settimeofday(&tv, NULL);
        storedTime = DEFAULT_TIME;
        LogManager::log("Default time set: " + String(storedTime));
    } else {
        // Check if RTC has a valid updated time
        if (currentRtcTime > persistedTime) {
            storedTime = currentRtcTime;
            LogManager::log("System time updated from RTC: " + String(storedTime));
        } else {
            storedTime = persistedTime;
            LogManager::log("System time updated from persisted time: " + String(storedTime));
        }
        tv.tv_sec = storedTime;
        tv.tv_usec = 0;
        settimeofday(&tv, NULL);
    }
    
    // Store time immediately to SD card to ensure consistency
    storeCurrentTime();
    
    initialized = true;
    return true;
}

// Implementation of the no-parameter overload for compatibility with LogManager
String TimeManager::getTimestamp() {
    return getTimestamp("%y-%m-%d_%H-%M-%S");
}

String TimeManager::getTimestamp(const char* format) {
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
        char buffer[64];
        strftime(buffer, sizeof(buffer), format, &timeinfo);
        return String(buffer);
    }
    return "unknown";
}

bool TimeManager::updateFromNTP() {
    if (WiFi.status() != WL_CONNECTED) {
        LogManager::log("Cannot update time: WiFi not connected");
        return false;
    }
    
    LogManager::log("Updating time from NTP servers...");
    configTime(0, 0, "pool.ntp.org", "time.google.com", "time.nist.gov");
    struct tm timeinfo;

    if (getLocalTime(&timeinfo)) {
        storedTime = mktime(&timeinfo);
        LogManager::log("Current time obtained from NTP.");
        storeCurrentTime();
        return true;
    } else {
        LogManager::log("Failed to obtain time from NTP.");
        return false;
    }
}

bool TimeManager::storeCurrentTime() {
    if (!initialized) {
        Serial.println("TimeManager not properly initialized for storing time!");
        return false;
    }
    
    if (!app) {
        Serial.println("TimeManager app reference is null!");
        return false;
    }
    
    time_t current = time(NULL);
    storedTime = current;
    
    // Store time to SD card
    SemaphoreHandle_t sdMutex = app->getSDMutex();
    if (xSemaphoreTake(sdMutex, portMAX_DELAY) == pdPASS) {
        File timeFile = SD.open(TIME_FILE, FILE_WRITE);
        if (timeFile) {
            timeFile.println(String(current));
            timeFile.close();
            // Use Serial instead of LogManager to avoid circular dependency issues early in boot
            if (initialized)
                LogManager::log("Stored current time to SD card: " + String(current));
            else
                Serial.println("Stored current time to SD card: " + String(current));
            xSemaphoreGive(sdMutex);
            return true;
        } else {
            if (initialized)
                LogManager::log("Failed to open time file for writing");
            else
                Serial.println("Failed to open time file for writing");
            xSemaphoreGive(sdMutex);
            return false;
        }
    } else {
        if (initialized)
            LogManager::log("Failed to take SD mutex for time storage");
        else
            Serial.println("Failed to take SD mutex for time storage");
        return false;
    }
}

bool TimeManager::startPersistenceTask() {
    if (!initialized || !app) {
        LogManager::log("TimeManager not initialized!");
        return false;
    }
    
    // Start time persistence task
    if (xTaskCreatePinnedToCore(
        persistTimeTask,
        "Persist Time",
        4096,
        NULL,
        1,
        &persistTimeTaskHandle,
        0  // Run on Core 0
    ) != pdPASS) {
        LogManager::log("Failed to create time persistence task!");
        return false;
    }
    
    return true;
}

void TimeManager::persistTimeTask(void *parameter) {
    while (true) {
        storeCurrentTime();
        vTaskDelay(pdMS_TO_TICKS(TIME_PERSIST_INTERVAL));
    }
}

time_t TimeManager::getCurrentTime() {
    return time(NULL);
}
