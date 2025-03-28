/**
 * @file BackendClient.h
 * @brief Client for communicating with backend server
 *
 * This class handles all communication with the backend server,
 * including file uploads and reachability checks. It implements
 * a singleton pattern and manages background tasks for file uploads
 * and connectivity monitoring.
 */

#ifndef BACKEND_CLIENT_H
#define BACKEND_CLIENT_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <HTTPClient.h>
#include <esp_heap_caps.h>

#include "Application.h"
#include "config.h"
#include "secrets.h"

// 512KB PSRAM buffer size
#define UPLOAD_BUFFER_SIZE (512 * 1024)

class BackendClient {
public:
    // Prevent copying and assignment
    BackendClient(const BackendClient&) = delete;
    BackendClient& operator=(const BackendClient&) = delete;
    
    /**
     * @brief Initializes the BackendClient
     * @param app Pointer to Application instance (uses singleton if nullptr)
     * @return true if initialization succeeds, false otherwise
     */
    static bool init(Application* app = nullptr);
    
    /**
     * @brief Starts the file upload background task
     * @return true if task creation succeeds, false otherwise
     */
    static bool startUploadTask();
    
    /**
     * @brief Starts the backend reachability check background task
     * @return true if task creation succeeds, false otherwise
     */
    static bool startReachabilityTask();
    
    /**
     * @brief Gets the handle to the upload task
     * @return TaskHandle_t for the upload task
     */
    static TaskHandle_t getUploadTaskHandle();
    
    /**
     * @brief Gets the handle to the reachability task
     * @return TaskHandle_t for the reachability task
     */
    static TaskHandle_t getReachabilityTaskHandle();
    
    /**
     * @brief Gets the mutex used to protect upload operations
     * @return SemaphoreHandle_t for the upload mutex
     */
    static SemaphoreHandle_t getUploadMutex();
    
    /**
     * @brief Sets the next time to check backend reachability
     * @param time Timestamp in milliseconds for next check
     */
    static void setNextBackendCheckTime(unsigned long time);
    
    /**
     * @brief Gets the time for the next backend check
     * @return Timestamp in milliseconds for next check
     */
    static unsigned long getNextBackendCheckTime();
    
    /**
     * @brief Sets the current interval for backend checks
     * @param interval Time in milliseconds between checks
     */
    static void setCurrentBackendInterval(unsigned long interval);
    
    /**
     * @brief Gets the current interval for backend checks
     * @return Time in milliseconds between checks
     */
    static unsigned long getCurrentBackendInterval();
    
    /**
     * @brief Checks if the backend is currently reachable
     * @return true if backend is reachable, false otherwise
     */
    static bool isReachable();
    
    /**
     * @brief Queues a file for upload to the backend
     * @param filename Path to the file to upload
     */
    static void uploadFile(const String& filename);
    
    /**
     * @brief Checks if battery voltage is above threshold for uploading
     * @return true if battery voltage is above threshold, false otherwise
     */
    static bool isBatteryOkForUpload();
    
    /**
     * @brief Checks if all upload conditions are met
     * @return true if WiFi is connected, backend is reachable, files are in queue, and battery is above threshold
     */
    static bool canUploadFiles();

private:
    // Private constructor (singleton pattern enforcement)
    BackendClient() = default;
    
    // Private static state
    static bool initialized;
    static TaskHandle_t uploadTaskHandle;
    static TaskHandle_t reachabilityTaskHandle;
    static Application* app;
    static SemaphoreHandle_t uploadMutex;
    static unsigned long nextBackendCheckTime;
    static unsigned long currentBackendInterval;
    static uint8_t* uploadBuffer;  // Fixed-size PSRAM buffer
    
    // Internal helper functions
    static void fileUploadTaskFunction(void* parameter);
    static void backendReachabilityTaskFunction(void* parameter);
    static bool checkBackendReachability();
    static bool uploadFileFromBuffer(size_t size, const String& filename);
    
    // Upload conditions meta variable
    static bool uploadConditionsMet();
};

#endif // BACKEND_CLIENT_H
