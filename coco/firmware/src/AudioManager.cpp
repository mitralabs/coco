/**
 * @file AudioManager.cpp
 * @brief Implementation of audio recording and processing functionality
 */

#include "AudioManager.h"

// Initialize static member variables
bool AudioManager::initialized = false;
Application* AudioManager::app = nullptr;
I2SClass AudioManager::i2s;
TaskHandle_t AudioManager::recordAudioTaskHandle = NULL;
TaskHandle_t AudioManager::audioFileTaskHandle = NULL;
volatile bool AudioManager::isRecording = false;
volatile bool AudioManager::wasRecording = false;
unsigned long AudioManager::lastRecordStart = 0;
QueueHandle_t AudioManager::audioQueue = NULL;
int AudioManager::audioFileIndex = 0;

bool AudioManager::init(Application* appInstance) {
    if (initialized) {
        return true;
    }
    
    if (appInstance == nullptr) {
        app = Application::getInstance();
    } else {
        app = appInstance;
    }
    
    // Initialize audio queue if not already created
    if (audioQueue == NULL) {
        audioQueue = xQueueCreate(10, sizeof(AudioBuffer));
        if (audioQueue == NULL) {
            app->log("Failed to create audio queue!");
            return false;
        }
    }
    
    // Initialize I2S for audio recording
    if (!initI2S()) {
        app->log("Failed to initialize I2S in AudioManager!");
        return false;
    }

    // Ensure recordings directory exists
    if (!app->ensureDirectory(RECORDINGS_DIR)) {
        app->log("Failed to create recordings directory!");
        return false;
    }

    // Ensure upload queue file exists
    String queueContent = app->readFile(UPLOAD_QUEUE_FILE);
    if (queueContent.length() == 0) {
        // Create empty file if it doesn't exist
        if (app->createEmptyFile(UPLOAD_QUEUE_FILE)) {
            app->log("Created new upload queue file");
        } else {
            app->log("Failed to create upload queue file!");
            return false;
        }
    }
    
    initialized = true;
    app->log("AudioManager initialized successfully");
    return true;
}

bool AudioManager::initI2S() {
    // The error shows we need to use I2S0 instead of I2S1 for PDM
    // ESP32-S3 has multiple I2S controllers, we need to make sure we're using I2S0
    app->log("Initializing PDM Microphone on I2S0...");
    
    // Make sure pins are reset before configuration
    i2s.end();
    
    // Explicitly configure for I2S0 controller
    i2s.setPinsPdmRx(42, 41, I2S_NUM_0);  // Specify I2S0
    
    // Create a short delay to ensure pin reconfiguration takes effect
    delay(10);
    
    if (!i2s.begin(I2S_MODE_PDM_RX, SAMPLING_RATE, I2S_DATA_BIT_WIDTH_16BIT,
                 I2S_SLOT_MODE_MONO)) {
        app->log("Failed to initialize I2S! Error code: " + String(esp_err_to_name(i2s.lastError())));
        return false;
    }
    
    app->log("Mic initialized successfully.");
    return true;
}

bool AudioManager::startRecordingTask() {
    if (!initialized) {
        if (!init()) {
            app->log("Failed to initialize AudioManager!");
            return false;
        }
    }
    
    // Create recording task
    if (xTaskCreatePinnedToCore(
        recordAudioTask,
        "Record Loop",
        4096,
        NULL,
        1,
        &recordAudioTaskHandle,
        1  // Run on Core 1
    ) != pdPASS) {
        app->log("Failed to create record audio task!");
        return false;
    }
    
    app->log("Record audio task started");
    return true;
}

bool AudioManager::startAudioFileTask() {
    if (!initialized) {
        if (!init()) {
            app->log("Failed to initialize AudioManager!");
            return false;
        }
    }
    
    // Create audio file handling task
    if (xTaskCreatePinnedToCore(
        audioFileTask,
        "Audio File Save",
        4096,
        NULL,
        4,
        &audioFileTaskHandle,
        0  // Run on Core 0
    ) != pdPASS) {
        app->log("Failed to create audio file task!");
        return false;
    }
    
    app->log("Audio file task started");
    return true;
}

bool AudioManager::isBatteryOkForRecording() {
    if (!app) return false;
    
    float batteryVoltage = app->getBatteryVoltage();
    bool isOk = batteryVoltage >= BATTERY_RECORDING_THRESHOLD;
    
    if (!isOk) {
        app->log("Battery voltage too low for recording: " + String(batteryVoltage) + "V (threshold: " + 
                String(BATTERY_RECORDING_THRESHOLD) + "V)");
    }
    
    return isOk;
}

bool AudioManager::canRecord() {
    if (!app) return false;
    
    // Check if recording is requested and battery level is sufficient
    bool recordRequested = app->isRecordingRequested();
    bool batteryOk = isBatteryOkForRecording();
    
    bool canProceed = recordRequested && batteryOk;
    
    if (recordRequested && !batteryOk) {
        app->log("Recording requested but battery level is too low");
        // If battery is too low, disable recording request to prevent continuous warnings
        app->setRecordingRequested(false);
    }
    
    return canProceed;
}

void AudioManager::recordAudioTask(void* parameter) {
    if (!initialized) {
        init();
    }
    
    while (true) {
        
        if (canRecord()) {
            lastRecordStart = millis(); // Track when recording started
            AudioBuffer audio;

            // Use TimeManager for timestamp through Application wrapper
            String ts = app->getTimestamp();
            snprintf(audio.timestamp, sizeof(audio.timestamp), "%s", ts.c_str());
            
            // Use "start" marker for the first chunk, then MIDDLE afterwards.
            if (!wasRecording) {
                wasRecording = true;
                audio.type = AudioBuffer::START;
                app->log("Started audio recording");
            } else {
                audio.type = AudioBuffer::MIDDLE;
            }
            
            audio.buffer = i2s.recordWAV(RECORD_TIME, &audio.size);
            
            if (audio.buffer == NULL || audio.size == 0) {
                app->log("Failed to record audio: buffer is empty");
                free(audio.buffer); // Just in case
                vTaskDelay(pdMS_TO_TICKS(10));
                continue;
            }
            
            if (xQueueSend(audioQueue, &audio, pdMS_TO_TICKS(1000)) != pdPASS) {
                app->log("Failed to enqueue audio buffer!");
                free(audio.buffer);
            }
        } else {
            // If we were recording but recording is now off, record a final chunk with "end" marker.
            if (wasRecording) {
                AudioBuffer audio;
                String ts = app->getTimestamp();
                snprintf(audio.timestamp, sizeof(audio.timestamp), "%s", ts.c_str());
                audio.type = AudioBuffer::END;
                audio.buffer = i2s.recordWAV(RECORD_TIME, &audio.size);
                
                if (audio.buffer == NULL || audio.size == 0) {
                    app->log("Failed to record final audio: buffer is empty");
                    wasRecording = false;
                    free(audio.buffer); // Just in case
                    continue;
                }
                
                if (xQueueSend(audioQueue, &audio, pdMS_TO_TICKS(1000)) != pdPASS) {
                    app->log("Failed to enqueue final audio buffer!");
                    free(audio.buffer);
                }
                wasRecording = false;
                app->log("Ended audio recording");
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

void AudioManager::audioFileTask(void* parameter) {
    if (!initialized) {
        init();
    }
    
    AudioBuffer audio;
    
    while (true) {
        while (xQueueReceive(audioQueue, &audio, pdMS_TO_TICKS(10)) == pdTRUE) {
            String prefix = "_";
            if (audio.type == AudioBuffer::START)
                prefix += "start";
            else if (audio.type == AudioBuffer::END)
                prefix += "end";
            else if (audio.type == AudioBuffer::MIDDLE)
                prefix += "middle";
                
            String fileName = String(RECORDINGS_DIR) + "/" +
                              String(app->getBootSession()) + "_" +
                              String(app->getAudioFileIndex()) + "_" +
                              String(audio.timestamp) +
                              prefix + ".wav";
            app->setAudioFileIndex(app->getAudioFileIndex() + 1);

            // Create a binary-safe string to hold the WAV data
            String binaryData;
            binaryData.reserve(audio.size);  // Reserve space to avoid reallocations
            
            // Manually copy binary data to the String 
            for (size_t i = 0; i < audio.size; i++) {
                binaryData += (char)audio.buffer[i];
            }
            
            // Write the binary data to file using Application wrapper
            if (app->overwriteFile(fileName, binaryData)) {
                app->log("Audio recorded and saved: " + fileName);
                app->setWavFilesAvailable(true);

                // Add to upload queue
                if (app->addToUploadQueue(fileName)) {
                    app->log("Added to upload queue: " + fileName);
                } else {
                    app->log("Failed to add to upload queue: " + fileName);
                }
            } else {
                app->log("Failed to write audio data to file: " + fileName);
            }
            
            free(audio.buffer);
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

TaskHandle_t AudioManager::getRecordAudioTaskHandle() {
    return recordAudioTaskHandle;
}

TaskHandle_t AudioManager::getAudioFileTaskHandle() {
    return audioFileTaskHandle;
}

bool AudioManager::isRecordingActive() {
    return wasRecording;
}

I2SClass* AudioManager::getI2S() {
    return &i2s;
}

uint8_t* AudioManager::recordWAV(unsigned long recordTimeMs, size_t* size) {
    if (!initialized) {
        init();
    }
    return i2s.recordWAV(recordTimeMs, size);
}

QueueHandle_t AudioManager::getAudioQueue() {
    return audioQueue;
}

void AudioManager::setAudioQueue(QueueHandle_t queue) {
    audioQueue = queue;
}

int AudioManager::getAudioFileIndex() {
    return audioFileIndex;
}

void AudioManager::setAudioFileIndex(int index) {
    audioFileIndex = index;
}