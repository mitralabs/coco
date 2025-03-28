/**
 * @file AudioManager.h
 * @brief Manager for audio recording and processing functionality
 *
 * This class handles I2S microphone initialization, audio recording,
 * and saving recordings to the file system. It follows a singleton pattern
 * and manages audio recording tasks.
 */

#ifndef AUDIO_MANAGER_H
#define AUDIO_MANAGER_H

// Standard libraries

// ESP libraries
#include <Arduino.h>
#include <ESP_I2S.h>

// Project includes
#include "config.h"
#include "Application.h"

class AudioManager {
public:
    /**
     * @brief Initialize the audio manager
     * @param app Pointer to the Application instance (optional)
     * @return true if initialization successful, false otherwise
     */
    static bool init(Application* app = nullptr);
    
    // Recording task management
    /**
     * @brief Start the audio recording task
     * @return true if task started successfully, false otherwise
     */
    static bool startRecordingTask();
    
    /**
     * @brief Record audio in a dedicated task
     * @param parameter Task parameters (unused)
     */
    static void recordAudioTask(void* parameter);
    
    /**
     * @brief Get the handle for the audio recording task
     * @return TaskHandle_t for the recording task
     */
    static TaskHandle_t getRecordAudioTaskHandle();
    
    // Audio file management
    /**
     * @brief Start the audio file handling task
     * @return true if task started successfully, false otherwise
     */
    static bool startAudioFileTask();
    
    /**
     * @brief Process and save audio files in a dedicated task
     * @param parameter Task parameters (unused)
     */
    static void audioFileTask(void* parameter);
    
    /**
     * @brief Get the handle for the audio file task
     * @return TaskHandle_t for the audio file task
     */
    static TaskHandle_t getAudioFileTaskHandle();

    // Audio recording operations
    /**
     * @brief Record WAV audio for the specified duration
     * @param recordTimeMs Time to record in milliseconds
     * @param size Pointer to store the size of the recorded data
     * @return Pointer to buffer containing recorded WAV data (must be freed by caller)
     */
    static uint8_t* recordWAV(unsigned long recordTimeMs, size_t* size);
    
    /**
     * @brief Check if audio recording is currently active
     * @return true if recording is active, false otherwise
     */
    static bool isRecordingActive();
    
    /**
     * @brief Check if the battery level is sufficient for recording
     * @return true if battery level is okay for recording, false otherwise
     */
    static bool isBatteryOkForRecording();
    
    /**
     * @brief Check if recording should be allowed (combines battery check and recording request)
     * @return true if recording is requested and battery is okay, false otherwise
     */
    static bool canRecord();
    
    // I2S management
    /**
     * @brief Initialize the I2S interface for audio recording
     * @return true if I2S initialized successfully, false otherwise
     */
    static bool initI2S();
    
    /**
     * @brief Get the I2S interface instance
     * @return Pointer to the I2S interface
     */
    static I2SClass* getI2S();
    
    // Audio queue management
    /**
     * @brief Get the audio queue handle
     * @return Handle to the audio queue
     */
    static QueueHandle_t getAudioQueue();
    
    /**
     * @brief Set the audio queue handle
     * @param queue New audio queue handle
     */
    static void setAudioQueue(QueueHandle_t queue);
    
    // Audio file index management
    /**
     * @brief Get the current audio file index
     * @return Current audio file index
     */
    static int getAudioFileIndex();
    
    /**
     * @brief Set the audio file index
     * @param index New audio file index
     */
    static void setAudioFileIndex(int index);

private:
    // Private constructor and deleted copy/assignment for singleton pattern
    AudioManager() = default;
    AudioManager(const AudioManager&) = delete;
    AudioManager& operator=(const AudioManager&) = delete;
    
    // Private static variables for state
    static bool initialized;
    static Application* app;
    static I2SClass i2s;
    static TaskHandle_t recordAudioTaskHandle;
    static TaskHandle_t audioFileTaskHandle;
    static volatile bool isRecording;
    
    // Audio recording state
    static volatile bool wasRecording;
    static unsigned long lastRecordStart;
    
    // Audio queue and file index
    static QueueHandle_t audioQueue;
    static int audioFileIndex;
};

#endif // AUDIO_MANAGER_H
