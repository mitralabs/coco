#ifndef BACKEND_CLIENT_H
#define BACKEND_CLIENT_H

#include <Arduino.h>
#include <HTTPClient.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "Application.h"

class BackendClient {
private:
    // Private static state
    static bool initialized;
    static TaskHandle_t uploadTaskHandle;
    static TaskHandle_t reachabilityTaskHandle;
    static Application* app;
    static SemaphoreHandle_t uploadMutex;
    static unsigned long nextBackendCheckTime;
    static unsigned long currentBackendInterval;
    
    // Private constructor (singleton pattern enforcement)
    BackendClient() = default;
    
    // Internal helper functions
    static void fileUploadTaskFunction(void* parameter);
    static void backendReachabilityTaskFunction(void* parameter);
    static bool checkBackendReachability();
    static bool uploadFileFromBuffer(uint8_t* buffer, size_t size, const String& filename);

public:
    // Prevent copying and assignment
    BackendClient(const BackendClient&) = delete;
    BackendClient& operator=(const BackendClient&) = delete;
    
    // Initialization function
    static bool init(Application* application);
    
    // Task management
    static bool startUploadTask();
    static bool startReachabilityTask();
    
    // Task handle getters
    static TaskHandle_t getUploadTaskHandle();
    static TaskHandle_t getReachabilityTaskHandle();
    
    // Mutex management
    static SemaphoreHandle_t getUploadMutex();
    
    // Backend check interval management
    static void setNextBackendCheckTime(unsigned long time);
    static unsigned long getNextBackendCheckTime();
    static void setCurrentBackendInterval(unsigned long interval);
    static unsigned long getCurrentBackendInterval();
    
    // Public API functions
    static bool isReachable();
    static void uploadFile(const String& filename);
};

#endif // BACKEND_CLIENT_H
