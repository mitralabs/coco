/**
 * @file TimeManager.cpp
 * @brief Implementation of the TimeManager class
 * 
 * Provides implementation for time initialization, synchronization,
 * formatting, and persistence functions.
 */

#include "TimeManager.h"

// Initialize static members
Application* TimeManager::app = nullptr;
time_t TimeManager::storedTime = 0;
TaskHandle_t TimeManager::persistTimeTaskHandle = nullptr;
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
    
    // Check if time file exists and read it using Application wrapper
    String timeStr = app->readFile(TIME_FILE);
    
    if (!timeStr.isEmpty()) {
        // Extract the first line (in case there are multiple lines)
        int newlinePos = timeStr.indexOf('\n');
        if (newlinePos != -1) {
            timeStr = timeStr.substring(0, newlinePos);
        }
        persistedTime = (time_t)timeStr.toInt();
        app->log("Read persisted time from SD card: " + String(persistedTime));
    }

    // Determine which time source to use
    if (persistedTime == 0) {
        // No persisted time: use default time
        tv.tv_sec = DEFAULT_TIME;
        tv.tv_usec = 0;
        settimeofday(&tv, NULL);
        storedTime = DEFAULT_TIME;
        app->log("Default time set: " + String(storedTime));
    } else {
        // Check if RTC has a valid updated time
        if (currentRtcTime > persistedTime) {
            storedTime = currentRtcTime;
            app->log("System time updated from RTC: " + String(storedTime));
        } else {
            storedTime = persistedTime;
            app->log("System time updated from persisted time: " + String(storedTime));
        }
        tv.tv_sec = storedTime;
        tv.tv_usec = 0;
        settimeofday(&tv, NULL);
    }
        
    initialized = true;

    // Store time immediately to SD card to ensure consistency
    storeCurrentTime();
    return true;
}

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

time_t TimeManager::getCurrentTime() {
    return time(NULL);
}

bool TimeManager::updateFromNTP() {
    if (WiFi.status() != WL_CONNECTED) {
        app->log("Cannot update time: WiFi not connected");
        return false;
    }
    
    app->log("Updating time from NTP servers...");
    configTime(0, 0, "pool.ntp.org", "time.google.com", "time.nist.gov");
    struct tm timeinfo;

    if (getLocalTime(&timeinfo)) {
        storedTime = mktime(&timeinfo);
        app->log("Current time obtained from NTP.");
        storeCurrentTime();
        return true;
    } else {
        app->log("Failed to obtain time from NTP.");
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
    
    // Store time to SD card using Application wrapper
    if (app->overwriteFile(TIME_FILE, String(current) + "\n")) {
        // Use Serial instead of LogManager to avoid circular dependency issues early in boot
        if (initialized)
            app->log("Stored current time to SD card: " + String(current));
        else
            Serial.println("Stored current time to SD card: " + String(current));
        return true;
    } else {
        if (initialized)
            app->log("Failed to write time file");
        else
            Serial.println("Failed to write time file");
        return false;
    }
}

bool TimeManager::startPersistenceTask() {
    if (!initialized || !app) {
        app->log("TimeManager not initialized!");
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
        app->log("Failed to create time persistence task!");
        return false;
    }
    
    return true;
}

void TimeManager::persistTimeTask(void *parameter) {
    TickType_t lastPersistTime = xTaskGetTickCount();
    
    while (true) {
        // Store current time
        bool success = storeCurrentTime();
        
        if (success) {
            // If successful, wait for the normal interval
            vTaskDelay(pdMS_TO_TICKS(TIME_PERSIST_INTERVAL));
        } else {
            // If failed, try again sooner but add a small delay to avoid tight loop
            vTaskDelay(pdMS_TO_TICKS(5000)); // Try again in 5 seconds
            app->log("Retrying time persistence after failure");
        }
    }
}