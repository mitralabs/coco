/**
 * @file BackendClient.cpp
 * @brief Implementation of the BackendClient class
 *
 * This file contains the implementation of all BackendClient methods,
 * including background task functions for file uploads and backend
 * connectivity monitoring.
 */

#include <HTTPClient.h>
#include <WiFi.h>

#include "BackendClient.h"

// Initialize static variables
bool BackendClient::initialized = false;
TaskHandle_t BackendClient::uploadTaskHandle = nullptr;
TaskHandle_t BackendClient::reachabilityTaskHandle = nullptr;
Application* BackendClient::app = nullptr;
SemaphoreHandle_t BackendClient::uploadMutex = nullptr;
unsigned long BackendClient::nextBackendCheckTime = 0;
unsigned long BackendClient::currentBackendInterval = MIN_SCAN_INTERVAL;
uint8_t* BackendClient::uploadBuffer = nullptr;

bool BackendClient::init(Application* application) {
    // Check if already initialized
    if (initialized) {
        return true;
    }
    
    // Store application instance with fallback to singleton
    if (application == nullptr) {
        app = Application::getInstance();
    } else {
        app = application;
    }
    
    if (!app) {
        return false;  // This is still a safety check if getInstance() fails
    }
    
    // Initialize backend client properties
    uploadMutex = xSemaphoreCreateMutex();
    if (!uploadMutex) {
        app->log("BackendClient: Failed to create upload mutex");
        return false;
    }
    
    // Allocate fixed buffer in PSRAM
    uploadBuffer = (uint8_t*)heap_caps_malloc(UPLOAD_BUFFER_SIZE, MALLOC_CAP_SPIRAM);
    if (!uploadBuffer) {
        app->log("BackendClient: Failed to allocate PSRAM for upload buffer");
        return false;
    }
    app->log("BackendClient: Allocated " + String(UPLOAD_BUFFER_SIZE / 1024) + "KB PSRAM buffer for uploads");
    
    nextBackendCheckTime = 0;
    currentBackendInterval = MIN_SCAN_INTERVAL;
    
    app->log("BackendClient: Initialized");
    initialized = true;
    return true;
}

bool BackendClient::startUploadTask() {
    if (!initialized) {
        app->log("BackendClient: Not initialized, can't start upload task");
        return false;
    }
    
    // Create the file upload task
    BaseType_t result = xTaskCreatePinnedToCore(
        fileUploadTaskFunction,
        "FileUpload",
        4096,
        nullptr,
        1,
        &uploadTaskHandle,
        0 // Core 0
    );
    
    if (result != pdPASS) {
        app->log("BackendClient: Failed to create file upload task");
        return false;
    }
    
    app->log("BackendClient: File upload task started");
    return true;
}

bool BackendClient::startReachabilityTask() {
    if (!initialized) {
        app->log("BackendClient: Not initialized, can't start reachability task");
        return false;
    }
    
    // Create the backend reachability check task
    BaseType_t result = xTaskCreatePinnedToCore(
        backendReachabilityTaskFunction,
        "BackendCheck",
        4096,
        nullptr,
        1,
        &reachabilityTaskHandle,
        0 // Core 0
    );
    
    if (result != pdPASS) {
        app->log("BackendClient: Failed to create backend reachability task");
        return false;
    }
    
    app->log("BackendClient: Backend reachability task started");
    return true;
}

TaskHandle_t BackendClient::getUploadTaskHandle() {
    return uploadTaskHandle;
}

TaskHandle_t BackendClient::getReachabilityTaskHandle() {
    return reachabilityTaskHandle;
}

SemaphoreHandle_t BackendClient::getUploadMutex() {
    return uploadMutex;
}

void BackendClient::setNextBackendCheckTime(unsigned long time) {
    nextBackendCheckTime = time;
}

unsigned long BackendClient::getNextBackendCheckTime() {
    return nextBackendCheckTime;
}

void BackendClient::setCurrentBackendInterval(unsigned long interval) {
    currentBackendInterval = interval;
}

unsigned long BackendClient::getCurrentBackendInterval() {
    return currentBackendInterval;
}

bool BackendClient::isReachable() {
    return app ? app->isBackendReachable() : false;
}

void BackendClient::uploadFile(const String& filename) {
    // This is a simplified interface using Application wrapper
    app->addToUploadQueue(filename);
}

bool BackendClient::isBatteryOkForUpload() {
    if (!app) return false;
    
    float batteryVoltage = app->getBatteryVoltage();
    bool isOk = batteryVoltage >= BATTERY_UPLOAD_THRESHOLD;
    
    if (!isOk) {
        app->log("Battery voltage too low for upload: " + String(batteryVoltage) + "V (threshold: " + 
                String(BATTERY_UPLOAD_THRESHOLD) + "V)");
    }
    
    return isOk;
}

bool BackendClient::canUploadFiles() {
    if (!app) return false;
    
    // Check all conditions required for file upload
    bool wifiConnected = app->isWifiConnected();
    bool backendReachable = app->isBackendReachable();
    bool filesInQueue = app->hasWavFilesAvailable();
    bool batteryOk = isBatteryOkForUpload();
    
    bool canUpload = wifiConnected && backendReachable && filesInQueue && batteryOk;
    
    if (!canUpload) {
        app->log("Upload conditions not met: WiFi=" + String(wifiConnected ? "yes" : "no") + 
                ", Backend=" + String(backendReachable ? "yes" : "no") + 
                ", Files=" + String(filesInQueue ? "yes" : "no") + 
                ", Battery=" + String(batteryOk ? "ok" : "low"));
    }
    
    return canUpload;
}

void BackendClient::fileUploadTaskFunction(void* parameter) {
    // Check if uploadBuffer was properly allocated in PSRAM
    if (!uploadBuffer) {
        app->log("ERROR: Upload buffer was not allocated in PSRAM. Terminating upload task.");
        vTaskDelete(nullptr);
        return;
    }

    while (true) {
        // Check if all conditions for upload are met
        if (canUploadFiles()) {
            // Check if we're already uploading
            if (xSemaphoreTake(uploadMutex, 0) == pdTRUE) {
                app->setUploadInProgress(true);
                
                // Get the next file to upload from queue
                String nextFile = app->getNextUploadFile();
                
                if (nextFile.length() > 0) {
                    app->log("Processing next file from queue: " + nextFile);
                    
                    // Read file into fixed PSRAM buffer
                    size_t fileSize = 0;
                    
                    if (app->readFileToFixedBuffer(nextFile, uploadBuffer, UPLOAD_BUFFER_SIZE, fileSize)) {
                        // Upload the file from fixed buffer
                        app->log("Uploading file from fixed buffer: " + nextFile + " (" + String(fileSize) + " bytes)");
                        bool uploadSuccess = uploadFileFromBuffer(fileSize, nextFile);
                        
                        // If upload was successful, delete the file and remove from queue
                        if (uploadSuccess) {
                            app->log("Upload successful, deleting file");
                            
                            if (app->deleteFile(nextFile)) {
                                app->log("File deleted: " + nextFile);
                            } else {
                                app->log("Failed to delete file: " + nextFile);
                            }
                            
                            // Remove from queue
                            app->removeFirstFromUploadQueue();
                        } else {
                            app->log("Upload failed for: " + nextFile);
                        }
                    } else {
                        app->log("Failed to read file into buffer: " + nextFile);
                    }
                } else {
                    // No files in queue
                    app->setWavFilesAvailable(false);
                    app->log("No files in upload queue");
                }
                
                app->setUploadInProgress(false);
                xSemaphoreGive(uploadMutex);
            }
        }
        
        vTaskDelay(pdMS_TO_TICKS(UPLOAD_CHECK_INTERVAL));
    }
}

bool BackendClient::uploadFileFromBuffer(size_t size, const String& filename) {
    if (size == 0 || !uploadBuffer) {
        return false;
    }
    
    SemaphoreHandle_t httpMutex = app->getHttpMutex();
    if (xSemaphoreTake(httpMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
        app->log("Could not get HTTP mutex for file upload");
        return false;
    }
    
    // Extract just the filename without the path for the request
    String bareFilename = filename.substring(filename.lastIndexOf('/') + 1);
    
    // Check WiFi connection before proceeding
    if (!app->isWifiConnected()) {
        app->log("WiFi not connected, aborting upload");
        xSemaphoreGive(httpMutex);
        return false;
    }
    
    // Add timeout settings
    HTTPClient client;
    client.setTimeout(HTTP_TIMEOUT);

    client.begin(API_ENDPOINT);
    client.addHeader("Content-Type", "audio/wav");
    client.addHeader("X-API-Key", API_KEY);  // Add the API key as a custom header
    client.addHeader("Content-Disposition",
                    "form-data; name=\"file\"; filename=\"" +
                        String(bareFilename) + "\"");

    // Send the request with the file data from buffer
    int httpResponseCode = client.sendRequest("POST", uploadBuffer, size);
    
    if (httpResponseCode > 0) {
        app->log("HTTP Response code: " + String(httpResponseCode));
        String response = client.getString();
        app->log("Server response: " + response);
        client.end();
        bool success = (httpResponseCode == HTTP_CODE_OK || httpResponseCode == HTTP_CODE_CREATED);
        if (!success) {
            // If we get an HTTP error response, mark backend as unavailable
            app->setBackendReachable(false);
            setNextBackendCheckTime(millis()); // Trigger an immediate recheck
        }
        xSemaphoreGive(httpMutex);
        return success;
    } else {
        app->log("Error on HTTP request: " + String(client.errorToString(httpResponseCode).c_str()));
        client.end();
        // Network error, mark backend as unavailable
        app->setBackendReachable(false);
        setNextBackendCheckTime(millis()); // Trigger an immediate recheck
        xSemaphoreGive(httpMutex);
        return false;
    }
}

bool BackendClient::checkBackendReachability() {
    if (!app->isWifiConnected()) {
        return false;
    }
    
    SemaphoreHandle_t httpMutex = app->getHttpMutex();
    if (xSemaphoreTake(httpMutex, pdMS_TO_TICKS(2000)) != pdTRUE) {
        app->log("HTTP mutex busy, skipping backend check");
        return app->isBackendReachable();  // Return current state
    }
    
    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT);
    http.begin(TEST_ENDPOINT);

    http.addHeader("X-API-Key", API_KEY);  // Add the API key as a custom header

    int httpResponseCode = http.GET();
    app->log("Backend check response: " + String(httpResponseCode));
    
    http.end();
    xSemaphoreGive(httpMutex);
    return httpResponseCode == 200;
}

void BackendClient::backendReachabilityTaskFunction(void* parameter) {
    const unsigned long RECHECK_INTERVAL = 600000; // Recheck every 10 minutes even when connected
    unsigned long lastSuccessfulCheck = 0;
    
    while (true) {
        unsigned long currentTime = millis();
        bool shouldCheck = false;
        
        // Only check backend if WiFi is connected
        if (app->isWifiConnected()) {
            // Check if:
            // 1. Backend status is unknown (not reachable) OR
            // 2. It's time for a periodic recheck when connected
            if (!app->isBackendReachable() || 
                (app->isBackendReachable() && (currentTime - lastSuccessfulCheck >= RECHECK_INTERVAL))) {
                
                // Check if it's time according to our backoff strategy
                if (currentTime >= getNextBackendCheckTime()) {
                    shouldCheck = true;
                }
            }
            
            if (shouldCheck) {
                app->log("Checking backend reachability...");
                
                if (checkBackendReachability()) {
                    app->log("Backend is reachable");
                    app->setBackendReachable(true);
                    // Reset backoff on success
                    setCurrentBackendInterval(MIN_SCAN_INTERVAL);
                    // Record successful check time
                    lastSuccessfulCheck = currentTime;
                } else {
                    app->log("Backend is not reachable");
                    app->setBackendReachable(false);
                    
                    // Apply exponential backoff for next check
                    unsigned long currentInterval = getCurrentBackendInterval();
                    unsigned long newInterval = std::min(currentInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
                    setCurrentBackendInterval(newInterval);
                    app->log("Next backend check in " + String(newInterval / 1000) + " seconds");
                }
                
                setNextBackendCheckTime(currentTime + getCurrentBackendInterval());
            }
        } else {
            // Reset status if WiFi disconnects
            app->setBackendReachable(false);
        }
        
        vTaskDelay(pdMS_TO_TICKS(5000)); // Task yield interval
    }
}
