#include "Application.h"
#include "config.h"
#include "LogManager.h"
#include "TimeManager.h"
#include "FileSystem.h" // Added for using FileSystem
#include "AudioManager.h" // Add AudioManager include

// Initialize static instance to nullptr
Application* Application::_instance = nullptr;

// Singleton accessor
Application* Application::getInstance() {
    if (_instance == nullptr) {
        _instance = new Application();
    }
    return _instance;
}

// Private constructor
Application::Application() :
    bootSession(0),
    logFileIndex(0),
    audioFileIndex(0),
    nextWifiScanTime(0),
    currentScanInterval(MIN_SCAN_INTERVAL),
    nextBackendCheckTime(0),
    currentBackendInterval(MIN_SCAN_INTERVAL),
    isRecording(false),
    recordingRequested(false),
    WIFIconnected(false),
    backendReachable(false),
    wavFilesAvailable(false),
    uploadInProgress(false),
    externalWakeTriggered(false),
    readyForDeepSleep(false),
    externalWakeValid(-1),
    ledMutex(nullptr),
    uploadMutex(nullptr),
    httpMutex(nullptr),
    stateMutex(nullptr),
    audioQueue(nullptr),
    logQueue(nullptr),
    buttonTimer(nullptr),
    recordAudioTaskHandle(nullptr),
    audioFileTaskHandle(nullptr),
    logFlushTaskHandle(nullptr),
    wifiConnectionTaskHandle(nullptr),
    batteryMonitorTaskHandle(nullptr),
    uploadTaskHandle(nullptr),
    persistTimeTaskHandle(nullptr),
    backendReachabilityTaskHandle(nullptr)
{
    // Constructor left intentionally minimal
}

// Main initialization
bool Application::init() {
    // Initialize components in correct order
    if (!initMutexes()) {
        Serial.println("Failed to initialize mutexes!");
        return false;
    }
    
    if (!initSD()) {
        Serial.println("Failed to initialize SD card!");
        return false;
    }
    
    if (!initPreferences()) {
        LogManager::log("Failed to initialize preferences!");
        return false;
    }
    
    if (!initQueues()) {
        LogManager::log("Failed to initialize queues!");
        return false;
    }
    
    // Removed initI2S() call as it's now handled by AudioManager
    
    return true;
}

// Initialize mutexes
bool Application::initMutexes() {
    ledMutex = xSemaphoreCreateMutex();
    uploadMutex = xSemaphoreCreateMutex();
    httpMutex = xSemaphoreCreateMutex();
    stateMutex = xSemaphoreCreateMutex();
    
    return (ledMutex != nullptr && 
            uploadMutex != nullptr && 
            httpMutex != nullptr &&
            stateMutex != nullptr);
}

// Initialize queues
bool Application::initQueues() {
    audioQueue = xQueueCreate(AUDIO_QUEUE_SIZE, sizeof(AudioBuffer));
    logQueue = xQueueCreate(LOG_QUEUE_SIZE, sizeof(char*));
    
    return (audioQueue != nullptr && logQueue != nullptr);
}

// Initialize SD card
bool Application::initSD() {
    // Use FileSystem module instead of direct SD initialization
    FileSystem* fs = FileSystem::getInstance();
    if (!fs->init()) {
        Serial.println("Failed to initialize FileSystem for SD card access!");
        return false;
    }
    Serial.println("SD card initialized through FileSystem module.");
    return true;
}

// Initialize preferences
bool Application::initPreferences() {
    preferences.begin("boot", false);
    bootSession = preferences.getInt("bootSession", 0);
    bootSession++;  // Increment for a new boot
    preferences.putInt("bootSession", bootSession);
    preferences.end();
    return true;
}

// Initialize recording mode
bool Application::initRecordingMode() {
    // Use AudioManager for audio initialization
    if (!AudioManager::init(this)) {
        return false;
    }
    
    // Use FileSystem instead of local implementation
    FileSystem* fs = FileSystem::getInstance();
    return fs->ensureDirectory(RECORDINGS_DIR);
}

// Thread-safe state accessors
bool Application::isRecordingActive() const {
    return isRecording;
}

bool Application::isRecordingRequested() const {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        bool value = recordingRequested;
        xSemaphoreGive(stateMutex);
        return value;
    }
    return false; // Default if mutex can't be taken
}

void Application::setRecordingRequested(bool requested) {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        recordingRequested = requested;
        xSemaphoreGive(stateMutex);
    }
}

bool Application::isWifiConnected() const {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        bool value = WIFIconnected;
        xSemaphoreGive(stateMutex);
        return value;
    }
    return false;
}

void Application::setWifiConnected(bool connected) {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        WIFIconnected = connected;
        xSemaphoreGive(stateMutex);
    }
}

bool Application::isBackendReachable() const {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        bool value = backendReachable;
        xSemaphoreGive(stateMutex);
        return value;
    }
    return false;
}

void Application::setBackendReachable(bool reachable) {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        backendReachable = reachable;
        xSemaphoreGive(stateMutex);
    }
}

bool Application::hasWavFilesAvailable() const {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        bool value = wavFilesAvailable;
        xSemaphoreGive(stateMutex);
        return value;
    }
    return false;
}

void Application::setWavFilesAvailable(bool available) {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        wavFilesAvailable = available;
        xSemaphoreGive(stateMutex);
    }
}

bool Application::isUploadInProgress() const {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        bool value = uploadInProgress;
        xSemaphoreGive(stateMutex);
        return value;
    }
    return false;
}

void Application::setUploadInProgress(bool inProgress) {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        uploadInProgress = inProgress;
        xSemaphoreGive(stateMutex);
    }
}

bool Application::isExternalWakeTriggered() const {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        bool value = externalWakeTriggered;
        xSemaphoreGive(stateMutex);
        return value;
    }
    return false;
}

void Application::setExternalWakeTriggered(bool triggered) {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        externalWakeTriggered = triggered;
        xSemaphoreGive(stateMutex);
    }
}

bool Application::isReadyForDeepSleep() const {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        bool value = readyForDeepSleep;
        xSemaphoreGive(stateMutex);
        return value;
    }
    return false;
}

void Application::setReadyForDeepSleep(bool ready) {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        readyForDeepSleep = ready;
        xSemaphoreGive(stateMutex);
    }
}

int Application::getExternalWakeValid() const {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        int value = externalWakeValid;
        xSemaphoreGive(stateMutex);
        return value;
    }
    return -1;
}

void Application::setExternalWakeValid(int valid) {
    if (xSemaphoreTake(stateMutex, portMAX_DELAY) == pdPASS) {
        externalWakeValid = valid;
        xSemaphoreGive(stateMutex);
    }
}

// Accessors for components
I2SClass* Application::getI2S() {
    // Return AudioManager's I2S instance instead
    return AudioManager::getI2S();
}

Preferences* Application::getPreferences() {
    return &preferences;
}

SemaphoreHandle_t Application::getLedMutex() {
    return ledMutex;
}

// Updated to delegate to FileSystem's mutex
SemaphoreHandle_t Application::getSDMutex() {
    return FileSystem::getInstance()->getSDMutex();
}

SemaphoreHandle_t Application::getUploadMutex() {
    return uploadMutex;
}

SemaphoreHandle_t Application::getHttpMutex() {
    return httpMutex;
}

QueueHandle_t Application::getAudioQueue() {
    return audioQueue;
}

QueueHandle_t Application::getLogQueue() {
    return logQueue;
}

TimerHandle_t Application::getButtonTimer() {
    return buttonTimer;
}

int Application::getBootSession() const {
    return bootSession;
}

void Application::setBootSession(int session) {
    bootSession = session;
}

int Application::getAudioFileIndex() const {
    return audioFileIndex;
}

void Application::setAudioFileIndex(int index) {
    audioFileIndex = index;
}

// WiFi scan timing
unsigned long Application::getNextWifiScanTime() const {
    return nextWifiScanTime;
}

void Application::setNextWifiScanTime(unsigned long time) {
    nextWifiScanTime = time;
}

unsigned long Application::getCurrentScanInterval() const {
    return currentScanInterval;
}

void Application::setCurrentScanInterval(unsigned long interval) {
    currentScanInterval = interval;
}

// Backend check timing
unsigned long Application::getNextBackendCheckTime() const {
    return nextBackendCheckTime;
}

void Application::setNextBackendCheckTime(unsigned long time) {
    nextBackendCheckTime = time;
}

unsigned long Application::getCurrentBackendInterval() const {
    return currentBackendInterval;
}

void Application::setCurrentBackendInterval(unsigned long interval) {
    currentBackendInterval = interval;
}

// Task handle accessors
void Application::setRecordAudioTaskHandle(TaskHandle_t handle) {
    recordAudioTaskHandle = handle;
}

TaskHandle_t Application::getRecordAudioTaskHandle() const {
    return recordAudioTaskHandle;
}

void Application::setAudioFileTaskHandle(TaskHandle_t handle) {
    audioFileTaskHandle = handle;
}

TaskHandle_t Application::getAudioFileTaskHandle() const {
    return audioFileTaskHandle;
}

void Application::setWifiConnectionTaskHandle(TaskHandle_t handle) {
    wifiConnectionTaskHandle = handle;
}

TaskHandle_t Application::getWifiConnectionTaskHandle() const {
    return wifiConnectionTaskHandle;
}

void Application::setBatteryMonitorTaskHandle(TaskHandle_t handle) {
    batteryMonitorTaskHandle = handle;
}

TaskHandle_t Application::getBatteryMonitorTaskHandle() const {
    return batteryMonitorTaskHandle;
}

void Application::setUploadTaskHandle(TaskHandle_t handle) {
    uploadTaskHandle = handle;
}

TaskHandle_t Application::getUploadTaskHandle() const {
    return uploadTaskHandle;
}

void Application::setBackendReachabilityTaskHandle(TaskHandle_t handle) {
    backendReachabilityTaskHandle = handle;
}

TaskHandle_t Application::getBackendReachabilityTaskHandle() const {
    return backendReachabilityTaskHandle;
}
