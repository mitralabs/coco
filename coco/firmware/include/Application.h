#ifndef APPLICATION_H
#define APPLICATION_H

#include <Arduino.h>
#include <ESP_I2S.h>
#include <FS.h>
#include <Preferences.h>
#include <SD.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

// Forward declarations
class LogManager;
class TimeManager;

// AudioBuffer and UploadBuffer struct definitions
enum AudioChunkType { START, MIDDLE, END };

struct AudioBuffer {
  uint8_t *buffer;
  size_t size;
  char timestamp[21];
  AudioChunkType type;
};

struct UploadBuffer {
  uint8_t *buffer;
  size_t size;
  String filename;
};

class Application {
private:
    // Singleton instance
    static Application* _instance;
    
    // Private constructor for singleton pattern
    Application();
    
    // System components
    Preferences preferences;
    I2SClass i2s;
    
    // File handles
    File curr_file;
    File recordings_root_dir;
    File logFile;
    
    // Counters and indexes
    int bootSession;
    int logFileIndex;
    int audioFileIndex;
    
    // Timing variables
    unsigned long nextWifiScanTime;
    unsigned long currentScanInterval;
    unsigned long nextBackendCheckTime;
    unsigned long currentBackendInterval;
    
    // State flags with mutexes for thread safety
    SemaphoreHandle_t stateMutex;
    volatile bool isRecording;
    volatile bool recordingRequested;
    volatile bool WIFIconnected;
    volatile bool backendReachable;
    volatile bool wavFilesAvailable;
    volatile bool uploadInProgress;
    volatile bool externalWakeTriggered;
    volatile bool readyForDeepSleep;
    volatile int externalWakeValid;  // -1: not determined, 0: invalid, 1: valid
    
    // Mutexes
    SemaphoreHandle_t ledMutex;
    SemaphoreHandle_t sdMutex;
    SemaphoreHandle_t uploadMutex;
    SemaphoreHandle_t httpMutex;
    
    // Queue handles
    QueueHandle_t audioQueue;
    QueueHandle_t logQueue;
    
    // Timer handle
    TimerHandle_t buttonTimer;
    
    // Task handles
    TaskHandle_t recordAudioTaskHandle;
    TaskHandle_t audioFileTaskHandle;
    TaskHandle_t logFlushTaskHandle;
    TaskHandle_t wifiConnectionTaskHandle;
    TaskHandle_t batteryMonitorTaskHandle;
    TaskHandle_t uploadTaskHandle;
    TaskHandle_t persistTimeTaskHandle;
    TaskHandle_t backendReachabilityTaskHandle;

public:
    // Delete copy constructor and assignment operator
    Application(const Application&) = delete;
    Application& operator=(const Application&) = delete;
    
    // Singleton accessor
    static Application* getInstance();
    
    // Initialization methods
    bool init();
    bool initSD();
    bool initI2S();
    bool initPreferences();
    bool initMutexes();
    bool initQueues();
    bool initRecordingMode();
    
    // State accessors (thread-safe)
    bool isRecordingActive() const;
    bool isRecordingRequested() const;
    void setRecordingRequested(bool requested);
    bool isWifiConnected() const;
    void setWifiConnected(bool connected);
    bool isBackendReachable() const;
    void setBackendReachable(bool reachable);
    bool hasWavFilesAvailable() const;
    void setWavFilesAvailable(bool available);
    bool isUploadInProgress() const;
    void setUploadInProgress(bool inProgress);
    bool isExternalWakeTriggered() const;
    void setExternalWakeTriggered(bool triggered);
    bool isReadyForDeepSleep() const;
    void setReadyForDeepSleep(bool ready);
    int getExternalWakeValid() const;
    void setExternalWakeValid(int valid);
    
    // Accessors for other state variables
    I2SClass* getI2S();
    Preferences* getPreferences();
    SemaphoreHandle_t getLedMutex();
    SemaphoreHandle_t getSDMutex();
    SemaphoreHandle_t getUploadMutex();
    SemaphoreHandle_t getHttpMutex();
    QueueHandle_t getAudioQueue();
    QueueHandle_t getLogQueue();
    TimerHandle_t getButtonTimer();
    int getBootSession() const;
    void setBootSession(int session);
    int getAudioFileIndex() const;
    void setAudioFileIndex(int index);
    
    // WiFi scan timing 
    unsigned long getNextWifiScanTime() const;
    void setNextWifiScanTime(unsigned long time);
    unsigned long getCurrentScanInterval() const;
    void setCurrentScanInterval(unsigned long interval);
    
    // Backend check timing
    unsigned long getNextBackendCheckTime() const;
    void setNextBackendCheckTime(unsigned long time);
    unsigned long getCurrentBackendInterval() const;
    void setCurrentBackendInterval(unsigned long interval);
    
    // Task handle accessors
    void setRecordAudioTaskHandle(TaskHandle_t handle);
    TaskHandle_t getRecordAudioTaskHandle() const;
    void setAudioFileTaskHandle(TaskHandle_t handle);
    TaskHandle_t getAudioFileTaskHandle() const;
    void setWifiConnectionTaskHandle(TaskHandle_t handle);
    TaskHandle_t getWifiConnectionTaskHandle() const;
    void setBatteryMonitorTaskHandle(TaskHandle_t handle);
    TaskHandle_t getBatteryMonitorTaskHandle() const;
    void setUploadTaskHandle(TaskHandle_t handle);
    TaskHandle_t getUploadTaskHandle() const;
    void setBackendReachabilityTaskHandle(TaskHandle_t handle);
    TaskHandle_t getBackendReachabilityTaskHandle() const;
    
    // File operations
    bool openFile(const String& path, File& file, const char* mode = FILE_READ);
    bool closeFile(File& file);
    bool ensureRecordingDirectory();
};

#endif // APPLICATION_H
