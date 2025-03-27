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
      readyForDeepSleep(false),
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
      batteryMonitorTaskHandle(NULL) {
    
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
        
        if (!PowerManager::init()) {
            Serial.println("Failed to initialize PowerManager");
            return false;
        }
        
        return true;
    } else {
        return false;
    }
}

bool Application::initRecordingMode() {
    // Initialize modules needed for recording
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
    
    return true;
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

bool Application::isReadyForDeepSleep() const {
    return readyForDeepSleep;
}

void Application::setReadyForDeepSleep(bool val) {
    readyForDeepSleep = val;
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
