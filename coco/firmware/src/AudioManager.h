#ifndef AUDIO_MANAGER_H
#define AUDIO_MANAGER_H

#include <Arduino.h>
#include <ESP_I2S.h>
#include "config.h"
#include "Application.h"

class AudioManager {
public:
    // Initialize the audio manager
    static bool init(Application* app = nullptr);
    
    // Recording functions
    static bool startRecordingTask();
    static bool startAudioFileTask();
    static void recordAudioTask(void* parameter);
    static void audioFileTask(void* parameter);
    
    // Getters for task handles
    static TaskHandle_t getRecordAudioTaskHandle();
    static TaskHandle_t getAudioFileTaskHandle();

    // Audio buffer management functions
    static uint8_t* recordWAV(unsigned long recordTimeMs, size_t* size);
    static bool isRecordingActive();
    
    // I2S management
    static bool initI2S();
    static I2SClass* getI2S();

private:
    // Private static variables for state
    static bool _initialized;
    static Application* _app;
    static I2SClass _i2s;
    static TaskHandle_t _recordAudioTaskHandle;
    static TaskHandle_t _audioFileTaskHandle;
    static volatile bool _isRecording;
    
    // Audio recording state
    static volatile bool _wasRecording;
    static unsigned long _lastRecordStart;
};

#endif // AUDIO_MANAGER_H
