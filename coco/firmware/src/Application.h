/**
 * @file Application.h
 * @brief Central application manager that orchestrates all system components
 * 
 * The Application class implements a singleton pattern and serves as the central
 * coordinator for all system functionality including audio recording, file management,
 * network operations, and power management.
 */

#ifndef APPLICATION_H
#define APPLICATION_H

// Standard libraries

// ESP libraries
#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <esp_sleep.h>

// Project includes
#include "config.h"
#include "LEDManager.h"

// Forward declarations for required classes
class FileSystem;
class LogManager;
class TimeManager;
class PowerManager;

/**
 * @brief Structure for handling audio data buffers
 */
struct AudioBuffer {
    uint8_t* buffer;    ///< Pointer to the audio data
    size_t size;        ///< Size of the buffer in bytes
    char timestamp[32]; ///< Timestamp string for the audio data
    enum { START, MIDDLE, END } type; ///< Position in the audio stream
};

/**
 * @brief Main application coordinator class implemented as a singleton
 */
class Application {
public:
    /**
     * @brief Gets the singleton instance of the Application
     * @return Pointer to the Application instance
     */
    static Application* getInstance();
    
    /**
     * @brief Initializes the application and all its subsystems
     * @return True if initialization succeeded, false otherwise
     */
    bool init();
    
    //-------------------------------------------------------------------------
    // State Management
    //-------------------------------------------------------------------------
    /**
     * @brief Checks if audio recording is requested
     * @return True if recording is requested, false otherwise
     */
    bool isRecordingRequested() const;
    
    /**
     * @brief Sets the recording request state
     * @param val The new recording request state
     */
    void setRecordingRequested(bool val);
    
    /**
     * @brief Starts the deep sleep task that monitors system for idle state
     * @return True if task started successfully, false otherwise
     */
    bool startDeepSleepTask();
    
    /**
     * @brief Gets the handle of the deep sleep task
     * @return FreeRTOS task handle
     */
    TaskHandle_t getDeepSleepTaskHandle() const;
    
    /**
     * @brief Sets the handle of the deep sleep task
     * @param handle FreeRTOS task handle
     */
    void setDeepSleepTaskHandle(TaskHandle_t handle);
    
    /**
     * @brief Deep sleep task that periodically checks if device can enter sleep
     * @param parameter Task parameter (unused)
     */
    static void deepSleepTask(void* parameter);
    
    /**
     * @brief Stack monitoring task that periodically checks stack usage
     * @param parameter Task parameter (unused)
     */
    static void stackMonitorTask(void* parameter);
    
    /**
     * @brief Starts the stack monitoring task if enabled in config
     * @return True if task started or not needed, false on failure
     */
    bool startStackMonitorTask();
    
    /**
     * @brief Monitor stack usage of a specific task
     * @param taskHandle Handle of the task to monitor
     */
    void monitorStackUsage(TaskHandle_t taskHandle);
    
    /**
     * @brief Checks if the system is in idle state (not recording or uploading)
     * @return True if system is idle, false otherwise
     */
    bool isSystemIdle() const;

    /**
     * @brief Gets the current boot session counter
     * @return The boot session count
     */
    int getBootSession() const;
    
    /**
     * @brief Increments the boot session counter and stores it
     */
    void incrementBootSession();
    
    //-------------------------------------------------------------------------
    // Task Management
    //-------------------------------------------------------------------------
    /**
     * @brief Gets the handle of the audio recording task
     * @return FreeRTOS task handle
     */
    TaskHandle_t getRecordAudioTaskHandle() const;
    
    /**
     * @brief Sets the handle of the audio recording task
     * @param handle FreeRTOS task handle
     */
    void setRecordAudioTaskHandle(TaskHandle_t handle);
    
    /**
     * @brief Gets the handle of the audio file task
     * @return FreeRTOS task handle
     */
    TaskHandle_t getAudioFileTaskHandle() const;
    
    /**
     * @brief Sets the handle of the audio file task
     * @param handle FreeRTOS task handle
     */
    void setAudioFileTaskHandle(TaskHandle_t handle);
    
    /**
     * @brief Gets the handle of the WiFi connection task
     * @return FreeRTOS task handle
     */
    TaskHandle_t getWifiConnectionTaskHandle() const;
    
    /**
     * @brief Sets the handle of the WiFi connection task
     * @param handle FreeRTOS task handle
     */
    void setWifiConnectionTaskHandle(TaskHandle_t handle);
    
    /**
     * @brief Gets the handle of the upload task
     * @return FreeRTOS task handle
     */
    TaskHandle_t getUploadTaskHandle() const;
    
    /**
     * @brief Sets the handle of the upload task
     * @param handle FreeRTOS task handle
     */
    void setUploadTaskHandle(TaskHandle_t handle);
    
    /**
     * @brief Gets the handle of the reachability task
     * @return FreeRTOS task handle
     */
    TaskHandle_t getReachabilityTaskHandle() const;
    
    /**
     * @brief Sets the handle of the reachability task
     * @param handle FreeRTOS task handle
     */
    void setReachabilityTaskHandle(TaskHandle_t handle);
    
    /**
     * @brief Gets the handle of the battery monitor task
     * @return FreeRTOS task handle
     */
    TaskHandle_t getBatteryMonitorTaskHandle() const;
    
    /**
     * @brief Sets the handle of the battery monitor task
     * @param handle FreeRTOS task handle
     */
    void setBatteryMonitorTaskHandle(TaskHandle_t handle);
    
    /**
     * @brief Gets the handle of the stack monitor task
     * @return FreeRTOS task handle
     */
    TaskHandle_t getStackMonitorTaskHandle() const;
    
    /**
     * @brief Sets the handle of the stack monitor task
     * @param handle FreeRTOS task handle
     */
    void setStackMonitorTaskHandle(TaskHandle_t handle);
    
    //-------------------------------------------------------------------------
    // Resource Management
    //-------------------------------------------------------------------------
    /**
     * @brief Gets the mutex for LED operations
     * @return FreeRTOS semaphore handle
     */
    SemaphoreHandle_t getLedMutex() const;
    
    /**
     * @brief Gets the mutex for HTTP operations
     * @return FreeRTOS semaphore handle
     */
    SemaphoreHandle_t getHttpMutex() const;
    
    //-------------------------------------------------------------------------
    // External Wake Management
    //-------------------------------------------------------------------------
    /**
     * @brief Checks if the device was awakened by external trigger
     * @return True if external wake was triggered, false otherwise
     */
    bool isExternalWakeTriggered() const;
    
    /**
     * @brief Sets the external wake triggered state
     * @param val The new external wake triggered state
     */
    void setExternalWakeTriggered(bool val);
    
    /**
     * @brief Gets the external wake validity state
     * @return -1 if undetermined, 0 if invalid, 1 if valid
     */
    int getExternalWakeValid() const;
    
    /**
     * @brief Sets the external wake validity state
     * @param val The new external wake validity state (-1, 0, or 1)
     */
    void setExternalWakeValid(int val);
    
    //-------------------------------------------------------------------------
    // Audio File Management
    //-------------------------------------------------------------------------
    /**
     * @brief Gets the current audio file index
     * @return The audio file index
     */
    int getAudioFileIndex() const;
    
    /**
     * @brief Sets the audio file index
     * @param index The new audio file index
     */
    void setAudioFileIndex(int index);
    
    /**
     * @brief Checks if WAV files are available for processing
     * @return True if WAV files are available, false otherwise
     */
    bool hasWavFilesAvailable() const;
    
    /**
     * @brief Sets the WAV files available state
     * @param val The new WAV files available state
     */
    void setWavFilesAvailable(bool val);
    
    //-------------------------------------------------------------------------
    // Network State Management
    //-------------------------------------------------------------------------
    /**
     * @brief Checks if WiFi is connected
     * @return True if WiFi is connected, false otherwise
     */
    bool isWifiConnected() const;
    
    /**
     * @brief Sets the WiFi connection state
     * @param connected The new WiFi connection state
     */
    void setWifiConnected(bool connected);
    
    /**
     * @brief Checks if the backend server is reachable
     * @return True if backend is reachable, false otherwise
     */
    bool isBackendReachable() const;
    
    /**
     * @brief Sets the backend reachability state
     * @param val The new backend reachability state
     */
    void setBackendReachable(bool val);
    
    /**
     * @brief Checks if a file upload is in progress
     * @return True if upload is in progress, false otherwise
     */
    bool isUploadInProgress() const;
    
    /**
     * @brief Sets the upload in progress state
     * @param val The new upload in progress state
     */
    void setUploadInProgress(bool val);
    
    //-------------------------------------------------------------------------
    // Module Wrapper Methods
    //-------------------------------------------------------------------------
    // Logging wrappers
    /**
     * @brief Logs a message through LogManager
     * @param message The message to log
     */
    void log(const String& message);
    
    /**
     * @brief Checks if there are pending logs
     * @return True if there are pending logs, false otherwise
     */
    bool hasPendingLogs();
    
    // Time wrappers
    /**
     * @brief Gets the current timestamp
     * @return Current timestamp as a string
     */
    String getTimestamp();
    
    /**
     * @brief Stores the current time to persistent storage
     * @return True if successful, false otherwise
     */
    bool storeCurrentTime();
    
    /**
     * @brief Updates the system time from an NTP server
     * @return True if successful, false otherwise
     */
    bool updateFromNTP();
    
    // FileSystem wrappers
    /**
     * @brief Ensures a directory exists, creating it if necessary
     * @param directory Path to the directory
     * @return True if directory exists or was created, false otherwise
     */
    bool ensureDirectory(const String& directory);
    
    /**
     * @brief Overwrites a file with new content
     * @param filename Name of the file to write
     * @param content Content to write to the file
     * @return True if successful, false otherwise
     */
    bool overwriteFile(const String& filename, const String& content);
    
    /**
     * @brief Reads the content of a file
     * @param filename Name of the file to read
     * @return Content of the file as a string, or empty string on error
     */
    String readFile(const String& filename);
    
    /**
     * @brief Adds a file to the upload queue
     * @param filename Name of the file to add to the queue
     * @return True if successful, false otherwise
     */
    bool addToUploadQueue(const String& filename);
    
    /**
     * @brief Creates an empty file
     * @param filename Name of the file to create
     * @return True if successful, false otherwise
     */
    bool createEmptyFile(const String& filename);
    
    /**
     * @brief Appends content to an existing file
     * @param filename Name of the file to append to
     * @param content Content to append
     * @return True if successful, false otherwise
     */
    bool addToFile(const String& filename, const String& content);
    
    /**
     * @brief Reads a file into a memory buffer
     * @param filename Name of the file to read
     * @param buffer Pointer to the buffer pointer that will be allocated
     * @param size Size of the allocated buffer
     * @return True if successful, false otherwise
     * @deprecated Use readFileToFixedBuffer instead
     */
    bool readFileToBuffer(const String& filename, uint8_t** buffer, size_t& size);
    
    /**
     * @brief Reads a file into a pre-allocated fixed buffer
     * @param path Path to the file
     * @param buffer Pre-allocated buffer to read into
     * @param bufferSize Size of the pre-allocated buffer
     * @param readSize Reference to variable that will receive actual bytes read
     * @return True if successful, false otherwise
     */
    bool readFileToFixedBuffer(const String& path, uint8_t* buffer, size_t bufferSize, size_t& readSize);
    
    /**
     * @brief Gets the next file from the upload queue
     * @return Filename of the next file to upload, or empty string if queue is empty
     */
    String getNextUploadFile();
    
    /**
     * @brief Removes the first file from the upload queue
     * @return True if successful, false otherwise
     */
    bool removeFirstFromUploadQueue();
    
    /**
     * @brief Deletes a file
     * @param filename Name of the file to delete
     * @return True if successful, false otherwise
     */
    bool deleteFile(const String& filename);
    
    // PowerManager wrappers
    /**
     * @brief Prepares the system for deep sleep
     */
    void initDeepSleep();
    
    /**
     * @brief Gets the wakeup cause from ESP sleep
     * @return ESP sleep wakeup cause
     */
    esp_sleep_wakeup_cause_t getWakeupCause();
    
    /**
     * @brief Gets the current battery voltage
     * @return float Battery voltage in volts
     */
    float getBatteryVoltage();
    
    // LED Manager wrappers
    SemaphoreHandle_t getLedMutex();
    void setLEDState(bool state);
    void setLEDBrightness(int brightness);
    void indicateBatteryLevel();
    void errorBlinkLED(int interval);
    bool timedErrorBlinkLED(int interval, unsigned long duration);
    
    //-------------------------------------------------------------------------
    // BackendClient Wrappers
    //-------------------------------------------------------------------------
    /**
     * @brief Starts the file upload background task
     * @return true if task creation succeeds, false otherwise
     */
    bool startFileUploadTask();
    
    /**
     * @brief Stops the file upload background task
     * @return true if task was successfully stopped, false otherwise
     */
    bool stopFileUploadTask();
    
    /**
     * @brief Starts the backend reachability check background task
     * @return true if task creation succeeds, false otherwise
     */
    bool startBackendReachabilityTask();
    
    /**
     * @brief Stops the backend reachability check background task
     * @return true if task was successfully stopped, false otherwise
     */
    bool stopBackendReachabilityTask();
    
private:
    // Private constructor and deleted copy/assignment for singleton pattern
    Application();
    Application(const Application&) = delete;
    Application& operator=(const Application&) = delete;
    
    // Member variables for application state
    static Application* instance;
    bool recordingRequested;
    bool externalWakeTriggered;
    int externalWakeValid; // -1: undetermined, 0: invalid, 1: valid
    bool wavFilesAvailable;
    int bootSession;
    int audioFileIndex;
    bool backendReachable;
    bool uploadInProgress;
    bool wifiConnected;
    
    // Task handles
    TaskHandle_t recordAudioTaskHandle;
    TaskHandle_t audioFileTaskHandle;
    TaskHandle_t wifiConnectionTaskHandle;
    TaskHandle_t uploadTaskHandle;
    TaskHandle_t backendReachabilityTaskHandle;
    TaskHandle_t batteryMonitorTaskHandle;
    TaskHandle_t deepSleepTaskHandle;
    TaskHandle_t stackMonitorTaskHandle;
    
    // Mutex for LED access
    SemaphoreHandle_t ledMutex;
    // Mutex for HTTP operations
    SemaphoreHandle_t httpMutex;
};

#endif // APPLICATION_H
