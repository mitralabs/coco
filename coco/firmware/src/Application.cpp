/**
 * @file Application.cpp
 * @brief Implementation of the Application class
 * 
 * This file contains the implementation of the central Application class that 
 * coordinates all system functionality.
 */

// Standard libraries
#include <Preferences.h>

// ESP libraries

// Project includes
#include "Application.h"
#include "AudioManager.h"
#include "BackendClient.h"
#include "FileSystem.h"
#include "LogManager.h"
#include "PowerManager.h"
#include "TimeManager.h"
#include "WifiManager.h"

// Initialize static instance
Application* Application::instance = nullptr;

// Get singleton instance
Application* Application::getInstance() {
    if (instance == nullptr) {
        instance = new Application();
    }
    return instance;
}

// Private constructor
Application::Application() 
    : recordingRequested(false),
      externalWakeTriggered(false),
      externalWakeValid(-1),
      wavFilesAvailable(false),
      bootSession(0),
      audioFileIndex(0),
      backendReachable(false),
      uploadInProgress(false),
      wifiConnected(false),
      recordAudioTaskHandle(NULL),
      audioFileTaskHandle(NULL),
      wifiConnectionTaskHandle(NULL),
      uploadTaskHandle(NULL),
      backendReachabilityTaskHandle(NULL),
      batteryMonitorTaskHandle(NULL),
      deepSleepTaskHandle(NULL),
      stackMonitorTaskHandle(NULL) {
    
    // Create mutex
    ledMutex = xSemaphoreCreateMutex();
    httpMutex = xSemaphoreCreateMutex();
}

// Initialization
bool Application::init() {
    // Read boot session from preferences
    Preferences preferences;
    if (preferences.begin("app", false)) {
        bootSession = preferences.getInt("bootSession", 0);
        preferences.end();
        
        // Increment boot session
        incrementBootSession();
        
        // Initialize modules in the correct order (dependency chain)
        if (!FileSystem::init(this)) {
            Serial.println("Failed to initialize FileSystem");
            return false;
        }
        
        if (!TimeManager::init(this)) {
            Serial.println("Failed to initialize TimeManager");
            return false;
        }
        
        if (!LogManager::init(this)) {
            Serial.println("Failed to initialize LogManager");
            return false;
        }
        
        // Set the boot session for log messages
        LogManager::setBootSession(bootSession);
        
        // Set TimeManager as the timestamp provider for LogManager
        LogManager::setTimestampProvider(TimeManager::getTimestamp);
        
        // Log startup information
        log("\n\n\n======= Boot session: " + String(bootSession) + "=======");
        
        // Log initial free heap
        log("Initial free heap: " + String(ESP.getFreeHeap()) + " bytes");

        // Reset audio file index on boot
        audioFileIndex = 0;
        
        if (!PowerManager::init()) {
            Serial.println("Failed to initialize PowerManager");
            return false;
        }
        
        // Initialize LED Manager
        if (!LEDManager::init(this)) {
            log("Failed to initialize LED Manager!");
            return false;
        }
        
        // Initialize additional modules needed for recording
        if (!WifiManager::init(this)) {
            log("Failed to initialize WifiManager");
            return false;
        }
        
        if (!AudioManager::init(this)) {
            log("Failed to initialize AudioManager");
            return false;
        }
        
        if (!BackendClient::init(this)) {
            log("Failed to initialize BackendClient");
            return false;
        }
        
        // Start the necessary tasks
        if (!LogManager::startLogTask()) {
            log("Failed to start log task");
            return false;
        }
        
        if (!TimeManager::startPersistenceTask()) {
            log("Failed to start time persistence task");
            return false;
        }
        
        if (!AudioManager::startRecordingTask()) {
            log("Failed to start audio recording task");
            return false;
        }
        setRecordAudioTaskHandle(AudioManager::getRecordAudioTaskHandle());
        
        if (!AudioManager::startAudioFileTask()) {
            log("Failed to start audio file task");
            return false;
        }
        setAudioFileTaskHandle(AudioManager::getAudioFileTaskHandle());
        
        if (!WifiManager::startConnectionTask()) {
            log("Failed to start WiFi connection task");
            return false;
        }
        
        if (!PowerManager::startBatteryMonitorTask()) {
            log("Failed to start battery monitor task");
            return false;
        }
        setBatteryMonitorTaskHandle(PowerManager::getBatteryMonitorTaskHandle());
        
        if (!BackendClient::startUploadTask()) {
            log("Failed to start file upload task");
            return false;
        }
        
        if (!BackendClient::startReachabilityTask()) {
            log("Failed to start backend reachability task");
            return false;
        }
        
        // After starting all other tasks, start the deep sleep task
        if (!startDeepSleepTask()) {
            log("Failed to start deep sleep task");
            return false;
        }
        
        // Start stack monitoring task if enabled
        if (!startStackMonitorTask()) {
            log("Failed to start stack monitor task");
            return false;
        }
        
        return true;
    } else {
        return false;
    }
}

//-------------------------------------------------------------------------
// State Management
//-------------------------------------------------------------------------
bool Application::isRecordingRequested() const {
    return recordingRequested;
}

void Application::setRecordingRequested(bool val) {
    recordingRequested = val;
}

int Application::getBootSession() const {
    return bootSession;
}

void Application::incrementBootSession() {
    bootSession++;
    
    // Save to preferences
    Preferences preferences;
    if (preferences.begin("app", false)) {
        preferences.putInt("bootSession", bootSession);
        preferences.end();
    }
}

bool Application::startDeepSleepTask() {
    // Create deep sleep monitoring task, without passing 'this' as parameter
    if (xTaskCreatePinnedToCore(
        deepSleepTask,
        "Deep Sleep",
        4096,
        NULL,  // No parameter needed now
        1,     // Lower priority
        &deepSleepTaskHandle,
        0      // Run on Core 0
    ) != pdPASS) {
        log("Failed to create deep sleep task!");
        return false;
    }
    
    log("Deep sleep task started");
    return true;
}

bool Application::startStackMonitorTask() {
    // Only start if enabled in config
    if (ENABLE_STACK_MONITORING) {
        if (xTaskCreatePinnedToCore(
            stackMonitorTask,
            "Stack Monitor",
            4096,
            NULL,
            1,
            &stackMonitorTaskHandle,
            0 // Run on Core 0
        ) != pdPASS) {
            log("Failed to create stack monitor task!");
            return false;
        }
        
        log("Stack monitor task started");
    } else {
        log("Stack monitoring disabled in config");
    }
    
    return true;
}

void Application::stackMonitorTask(void* parameter) {
    // Get the singleton instance
    Application* app = Application::getInstance();
    
    while (true) {
        app->monitorStackUsage(app->getRecordAudioTaskHandle());
        app->monitorStackUsage(app->getAudioFileTaskHandle());
        app->monitorStackUsage(app->getWifiConnectionTaskHandle());
        app->monitorStackUsage(app->getBatteryMonitorTaskHandle());
        app->monitorStackUsage(app->getUploadTaskHandle());
        app->monitorStackUsage(app->getReachabilityTaskHandle());
        app->monitorStackUsage(app->getDeepSleepTaskHandle());
        
        vTaskDelay(pdMS_TO_TICKS(10000)); // Check every 10 seconds
    }
}

void Application::monitorStackUsage(TaskHandle_t taskHandle) {
    if (taskHandle == NULL) {
        log("Task handle is null");
        return;
    }
    UBaseType_t highWaterMark = uxTaskGetStackHighWaterMark(taskHandle);
    log("Task " + String(pcTaskGetName(taskHandle)) + " high water mark: " + String(highWaterMark));
}

TaskHandle_t Application::getStackMonitorTaskHandle() const {
    return stackMonitorTaskHandle;
}

void Application::setStackMonitorTaskHandle(TaskHandle_t handle) {
    stackMonitorTaskHandle = handle;
}

TaskHandle_t Application::getDeepSleepTaskHandle() const {
    return deepSleepTaskHandle;
}

void Application::setDeepSleepTaskHandle(TaskHandle_t handle) {
    deepSleepTaskHandle = handle;
}

void Application::deepSleepTask(void* parameter) {
    
    // Record the task start time
    TickType_t startTime = xTaskGetTickCount();
    bool initialDelayPassed = false;
    
    // Get singleton instance
    Application* app = Application::getInstance();
    app->log("Deep sleep task starting with 3 second initialization delay");

    while (true) {
        // Check if initial delay has passed
        if (!initialDelayPassed) {
            TickType_t currentTime = xTaskGetTickCount();
            if ((currentTime - startTime) >= pdMS_TO_TICKS(3000)) {
                // Mark initial delay as passed
                initialDelayPassed = true;
                app->log("Deep sleep task initialization delay complete, monitoring can begin");
            } else {
                // Still in delay period, wait and continue
                vTaskDelay(pdMS_TO_TICKS(100)); // Short sleep before checking again
                continue;
            }
        }
        
        // Check if system is idle and can enter deep sleep
        if (app->isSystemIdle() && initialDelayPassed) {
            app->log("System is idle, preparing for deep sleep. Free heap: " + String(ESP.getFreeHeap()) + " bytes");
            app->initDeepSleep();
        }
        
        // Check periodically
        vTaskDelay(pdMS_TO_TICKS(DEEP_SLEEP_CHECK_INTERVAL));
    }
}



bool Application::isSystemIdle() const {
    // System is idle when:
    // 1. Can't record audio (no recording requested or battery too low)
    // 2. Can't upload files (no wifi/backend connectivity or battery too low)
    // 3. Not currently recording audio
    // 4. No audio files in processing queue
    
    // Check if system can record or upload
    bool canRecord = AudioManager::canRecord();
    bool canUpload = BackendClient::canUploadFiles();
    
    // If system can either record or upload, it's not idle
    if (canRecord || canUpload) {
        return false;
    }
    
    // Even if we can't record or upload, check if recording is active
    if (AudioManager::isRecordingActive()) {
        return false;
    }
    
    // Check if there are audio data waiting in the queue
    if (AudioManager::getAudioQueue() != NULL) {
        if (uxQueueMessagesWaiting(AudioManager::getAudioQueue()) > 0) {
            return false;
        }
    }
    
    // All checks passed, system is idle
    return true;
}

//-------------------------------------------------------------------------
// Task Management
//-------------------------------------------------------------------------
TaskHandle_t Application::getRecordAudioTaskHandle() const {
    return recordAudioTaskHandle;
}

void Application::setRecordAudioTaskHandle(TaskHandle_t handle) {
    recordAudioTaskHandle = handle;
}

TaskHandle_t Application::getAudioFileTaskHandle() const {
    return audioFileTaskHandle;
}

void Application::setAudioFileTaskHandle(TaskHandle_t handle) {
    audioFileTaskHandle = handle;
}

TaskHandle_t Application::getWifiConnectionTaskHandle() const {
    return wifiConnectionTaskHandle;
}

void Application::setWifiConnectionTaskHandle(TaskHandle_t handle) {
    wifiConnectionTaskHandle = handle;
}

TaskHandle_t Application::getUploadTaskHandle() const {
    return uploadTaskHandle;
}

void Application::setUploadTaskHandle(TaskHandle_t handle) {
    uploadTaskHandle = handle;
}

TaskHandle_t Application::getReachabilityTaskHandle() const {
    return backendReachabilityTaskHandle;
}

void Application::setReachabilityTaskHandle(TaskHandle_t handle) {
    backendReachabilityTaskHandle = handle;
}

TaskHandle_t Application::getBatteryMonitorTaskHandle() const {
    return batteryMonitorTaskHandle;
}

void Application::setBatteryMonitorTaskHandle(TaskHandle_t handle) {
    batteryMonitorTaskHandle = handle;
}

//-------------------------------------------------------------------------
// Resource Management
//-------------------------------------------------------------------------
SemaphoreHandle_t Application::getLedMutex() const {
    return ledMutex;
}

SemaphoreHandle_t Application::getHttpMutex() const {
    return httpMutex;
}

//-------------------------------------------------------------------------
// External Wake Management
//-------------------------------------------------------------------------
bool Application::isExternalWakeTriggered() const {
    return externalWakeTriggered;
}

void Application::setExternalWakeTriggered(bool val) {
    externalWakeTriggered = val;
}

int Application::getExternalWakeValid() const {
    return externalWakeValid;
}

void Application::setExternalWakeValid(int val) {
    externalWakeValid = val;
}

//-------------------------------------------------------------------------
// Audio File Management
//-------------------------------------------------------------------------
int Application::getAudioFileIndex() const {
    return audioFileIndex;
}

void Application::setAudioFileIndex(int index) {
    audioFileIndex = index;
}

bool Application::hasWavFilesAvailable() const {
    return wavFilesAvailable;
}

void Application::setWavFilesAvailable(bool val) {
    wavFilesAvailable = val;
}

//-------------------------------------------------------------------------
// Network State Management
//-------------------------------------------------------------------------
bool Application::isWifiConnected() const {
    return wifiConnected;
}

void Application::setWifiConnected(bool connected) {
    wifiConnected = connected;
}

bool Application::isBackendReachable() const {
    return backendReachable;
}

void Application::setBackendReachable(bool val) {
    backendReachable = val;
}

bool Application::isUploadInProgress() const {
    return uploadInProgress;
}

void Application::setUploadInProgress(bool val) {
    uploadInProgress = val;
}

//-------------------------------------------------------------------------
// Module Wrapper Methods
//-------------------------------------------------------------------------

// Logging wrappers
void Application::log(const String& message) {
    LogManager::log(message);
}

bool Application::hasPendingLogs() {
    return LogManager::hasPendingLogs();
}

// Time wrappers
String Application::getTimestamp() {
    return TimeManager::getTimestamp();
}

bool Application::storeCurrentTime() {
    return TimeManager::storeCurrentTime();
}

bool Application::updateFromNTP() {
    return TimeManager::updateFromNTP();
}

// FileSystem wrappers
bool Application::ensureDirectory(const String& directory) {
    return FileSystem::ensureDirectory(directory);
}

bool Application::overwriteFile(const String& filename, const String& content) {
    return FileSystem::overwriteFile(filename, content);
}

String Application::readFile(const String& filename) {
    return FileSystem::readFile(filename);
}

bool Application::addToUploadQueue(const String& filename) {
    return FileSystem::addToUploadQueue(filename);
}

bool Application::createEmptyFile(const String& filename) {
    return FileSystem::createEmptyFile(filename);
}

bool Application::addToFile(const String& filename, const String& content) {
    return FileSystem::addToFile(filename, content);
}

bool Application::readFileToBuffer(const String& filename, uint8_t** buffer, size_t& size) {
    return FileSystem::readFileToBuffer(filename, buffer, size);
}

bool Application::readFileToFixedBuffer(const String& path, uint8_t* buffer, size_t bufferSize, size_t& readSize) {
    return FileSystem::readFileToFixedBuffer(path, buffer, bufferSize, readSize);
}

String Application::getNextUploadFile() {
    return FileSystem::getNextUploadFile();
}

bool Application::removeFirstFromUploadQueue() {
    return FileSystem::removeFirstFromUploadQueue();
}

bool Application::deleteFile(const String& filename) {
    return FileSystem::deleteFile(filename);
}

// PowerManager wrappers
void Application::initDeepSleep() {
    PowerManager::initDeepSleep();
}

esp_sleep_wakeup_cause_t Application::getWakeupCause() {
    return PowerManager::getWakeupCause();
}

float Application::getBatteryVoltage() {
    return PowerManager::getBatteryVoltage();
}

// LED Manager wrapper functions
SemaphoreHandle_t Application::getLedMutex() {
    return LEDManager::getLEDMutex();
}

void Application::setLEDState(bool state) {
    LEDManager::setLEDState(state);
}

void Application::setLEDBrightness(int brightness) {
    LEDManager::setLEDBrightness(brightness);
}

void Application::indicateBatteryLevel() {
    // Get the battery level category from PowerManager
    int batteryLevel = PowerManager::getBatteryLevelCategory();
    
    // Indicate the battery level through LED blinks
    LEDManager::indicateBatteryLevel(batteryLevel);
}

void Application::errorBlinkLED(int interval) {
    LEDManager::errorBlinkLED(interval);
}

bool Application::timedErrorBlinkLED(int interval, unsigned long duration) {
    return LEDManager::timedErrorBlinkLED(interval, duration);
}
