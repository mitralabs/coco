#include "BackendClient.h"
#include "config.h"
#include "LogManager.h"
#include "FileSystem.h"
#include "WifiManager.h"
#include "secrets.h"

// Initialize static variables
bool BackendClient::initialized = false;
TaskHandle_t BackendClient::uploadTaskHandle = nullptr;
TaskHandle_t BackendClient::reachabilityTaskHandle = nullptr;
Application* BackendClient::app = nullptr;
SemaphoreHandle_t BackendClient::uploadMutex = nullptr;
unsigned long BackendClient::nextBackendCheckTime = 0;
unsigned long BackendClient::currentBackendInterval = MIN_SCAN_INTERVAL;

bool BackendClient::init(Application* application) {
    // Check if already initialized
    if (initialized) {
        return true;
    }
    
    // Store application instance
    app = application;
    
    if (!app) {
        LogManager::log("BackendClient: Application instance is null");
        return false;
    }
    
    // Initialize backend client properties
    uploadMutex = xSemaphoreCreateMutex();
    if (!uploadMutex) {
        LogManager::log("BackendClient: Failed to create upload mutex");
        return false;
    }
    
    nextBackendCheckTime = 0;
    currentBackendInterval = MIN_SCAN_INTERVAL;
    
    LogManager::log("BackendClient: Initialized");
    initialized = true;
    return true;
}

bool BackendClient::startUploadTask() {
    if (!initialized) {
        LogManager::log("BackendClient: Not initialized, can't start upload task");
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
        LogManager::log("BackendClient: Failed to create file upload task");
        return false;
    }
    
    LogManager::log("BackendClient: File upload task started");
    return true;
}

bool BackendClient::startReachabilityTask() {
    if (!initialized) {
        LogManager::log("BackendClient: Not initialized, can't start reachability task");
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
        LogManager::log("BackendClient: Failed to create backend reachability task");
        return false;
    }
    
    LogManager::log("BackendClient: Backend reachability task started");
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
    // This is a simplified interface that could be expanded in the future
    // Currently, the upload is handled via the queue in FileSystem
    FileSystem* fs = FileSystem::getInstance();
    if (fs) {
        fs->addToUploadQueue(filename);
    }
}

// Moved from main.cpp
void BackendClient::fileUploadTaskFunction(void* parameter) {
    FileSystem* fs = FileSystem::getInstance();
    
    while (true) {
        // Only proceed if WiFi is connected
        if (app->isWifiConnected() && app->isBackendReachable()) {
            // Check if we're already uploading
            if (xSemaphoreTake(uploadMutex, 0) == pdTRUE) {
                app->setUploadInProgress(true);
                
                // Get the next file to upload from queue
                String nextFile = fs->getNextUploadFile();
                
                if (nextFile.length() > 0) {
                    LogManager::log("Processing next file from queue: " + nextFile);
                    
                    // Try to take SD card mutex
                    SemaphoreHandle_t sdMutex = fs->getSDMutex();
                    if (xSemaphoreTake(sdMutex, pdMS_TO_TICKS(5000)) == pdTRUE) {
                        UploadBuffer uploadBuffer = {NULL, 0, ""};
                        
                        if (SD.exists(nextFile)) {
                            // Use direct SD operations here as we're handling binary data and already have the mutex
                            File file = SD.open(nextFile);
                            if (file) {
                                uploadBuffer.filename = nextFile;
                                uploadBuffer.size = file.size();
                                
                                // Allocate memory for the file content
                                uploadBuffer.buffer = (uint8_t*)malloc(uploadBuffer.size);
                                if (uploadBuffer.buffer) {
                                    // Read the entire file into RAM
                                    size_t bytesRead = file.read(uploadBuffer.buffer, uploadBuffer.size);
                                    if (bytesRead != uploadBuffer.size) {
                                        LogManager::log("Error reading file into buffer");
                                        free(uploadBuffer.buffer);
                                        uploadBuffer.buffer = NULL;
                                    }
                                } else {
                                    LogManager::log("Failed to allocate memory for file upload");
                                }
                                
                                file.close();
                            }
                        }
                        
                        // Release SD mutex before uploading
                        xSemaphoreGive(sdMutex);
                        
                        if (uploadBuffer.buffer) {
                            // Upload the file from RAM
                            LogManager::log("Uploading file from buffer: " + uploadBuffer.filename);
                            bool uploadSuccess = uploadFileFromBuffer(uploadBuffer.buffer, uploadBuffer.size, uploadBuffer.filename);
                            
                            // If upload was successful, delete the file and remove from queue
                            if (uploadSuccess) {
                                LogManager::log("Upload successful, deleting file");
                                
                                // Use deleteFile() instead of direct SD operations
                                if (fs->deleteFile(uploadBuffer.filename)) {
                                    LogManager::log("File deleted: " + uploadBuffer.filename);
                                } else {
                                    LogManager::log("Failed to delete file: " + uploadBuffer.filename);
                                }
                                
                                // Remove from queue
                                fs->removeFirstFromUploadQueue();
                            } else {
                                LogManager::log("Upload failed for: " + uploadBuffer.filename);
                            }
                            
                            // Free the buffer memory
                            free(uploadBuffer.buffer);
                        }
                    } else {
                        LogManager::log("Could not get SD card mutex for file upload");
                    }
                } else {
                    // No files in queue
                    app->setWavFilesAvailable(false);
                    LogManager::log("No files in upload queue");
                }
                
                app->setUploadInProgress(false);
                xSemaphoreGive(uploadMutex);
            }
        }
        
        vTaskDelay(pdMS_TO_TICKS(UPLOAD_CHECK_INTERVAL));
    }
}

bool BackendClient::uploadFileFromBuffer(uint8_t* buffer, size_t size, const String& filename) {
    if (!buffer || size == 0) {
        return false;
    }
    
    SemaphoreHandle_t httpMutex = app->getHttpMutex();
    if (xSemaphoreTake(httpMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
        LogManager::log("Could not get HTTP mutex for file upload");
        return false;
    }
    
    // Extract just the filename without the path for the request
    String bareFilename = filename.substring(filename.lastIndexOf('/') + 1);
    
    // Check WiFi connection before proceeding
    if (WiFi.status() != WL_CONNECTED) {
        LogManager::log("WiFi not connected, aborting upload");
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
    int httpResponseCode = client.sendRequest("POST", buffer, size);
    
    if (httpResponseCode > 0) {
        LogManager::log("HTTP Response code: " + String(httpResponseCode));
        String response = client.getString();
        LogManager::log("Server response: " + response);
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
        LogManager::log("Error on HTTP request: " + String(client.errorToString(httpResponseCode).c_str()));
        client.end();
        // Network error, mark backend as unavailable
        app->setBackendReachable(false);
        setNextBackendCheckTime(millis()); // Trigger an immediate recheck
        xSemaphoreGive(httpMutex);
        return false;
    }
}

bool BackendClient::checkBackendReachability() {
    if (!WifiManager::isConnected()) {
        return false;
    }
    
    SemaphoreHandle_t httpMutex = app->getHttpMutex();
    if (xSemaphoreTake(httpMutex, pdMS_TO_TICKS(2000)) != pdTRUE) {
        LogManager::log("HTTP mutex busy, skipping backend check");
        return app->isBackendReachable();  // Return current state
    }
    
    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT);
    http.begin(TEST_ENDPOINT);

    http.addHeader("X-API-Key", API_KEY);  // Add the API key as a custom header

    int httpResponseCode = http.GET();
    LogManager::log("Backend check response: " + String(httpResponseCode));
    
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
        if (WifiManager::isConnected()) {
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
                LogManager::log("Checking backend reachability...");
                
                if (checkBackendReachability()) {
                    LogManager::log("Backend is reachable");
                    app->setBackendReachable(true);
                    // Reset backoff on success
                    setCurrentBackendInterval(MIN_SCAN_INTERVAL);
                    // Record successful check time
                    lastSuccessfulCheck = currentTime;
                } else {
                    LogManager::log("Backend is not reachable");
                    app->setBackendReachable(false);
                    
                    // Apply exponential backoff for next check
                    unsigned long currentInterval = getCurrentBackendInterval();
                    unsigned long newInterval = std::min(currentInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
                    setCurrentBackendInterval(newInterval);
                    LogManager::log("Next backend check in " + String(newInterval / 1000) + " seconds");
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
