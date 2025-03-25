#include "AudioManager.h"
#include "LogManager.h"
#include "TimeManager.h"
#include "FileSystem.h"
#include "PowerManager.h"

// Initialize static member variables
bool AudioManager::_initialized = false;
Application* AudioManager::_app = nullptr;
I2SClass AudioManager::_i2s;
TaskHandle_t AudioManager::_recordAudioTaskHandle = NULL;
TaskHandle_t AudioManager::_audioFileTaskHandle = NULL;
volatile bool AudioManager::_isRecording = false;
volatile bool AudioManager::_wasRecording = false;
unsigned long AudioManager::_lastRecordStart = 0;

bool AudioManager::init(Application* app) {
    if (_initialized) {
        return true;
    }
    
    if (app == nullptr) {
        _app = Application::getInstance();
    } else {
        _app = app;
    }
    
    // Initialize I2S for audio recording
    if (!initI2S()) {
        LogManager::log("Failed to initialize I2S in AudioManager!");
        return false;
    }

    // Get FileSystem instance
    FileSystem* fs = FileSystem::getInstance();

    // Ensure recordings directory exists
    if (!fs->ensureDirectory(RECORDINGS_DIR)) {
        LogManager::log("Failed to create recordings directory!");
        return false;
    }

    // Ensure upload queue file exists
    String queueContent = fs->readFile(UPLOAD_QUEUE_FILE);
    if (queueContent.length() == 0) {
        // Create empty file if it doesn't exist
        if (fs->overwriteFile(UPLOAD_QUEUE_FILE, "")) {
            LogManager::log("Created new upload queue file");
        } else {
            LogManager::log("Failed to create upload queue file!");
            return false;
        }
    }
    
    _initialized = true;
    LogManager::log("AudioManager initialized successfully");
    return true;
}

bool AudioManager::initI2S() {
    // The error shows we need to use I2S0 instead of I2S1 for PDM
    // ESP32-S3 has multiple I2S controllers, we need to make sure we're using I2S0
    LogManager::log("Initializing PDM Microphone on I2S0...");
    
    // Make sure pins are reset before configuration
    _i2s.end();
    
    // Explicitly configure for I2S0 controller
    _i2s.setPinsPdmRx(42, 41, I2S_NUM_0);  // Specify I2S0
    
    // Create a short delay to ensure pin reconfiguration takes effect
    delay(10);
    
    if (!_i2s.begin(I2S_MODE_PDM_RX, SAMPLING_RATE, I2S_DATA_BIT_WIDTH_16BIT,
                 I2S_SLOT_MODE_MONO)) {
        LogManager::log("Failed to initialize I2S! Error code: " + String(esp_err_to_name(_i2s.lastError())));
        return false;
    }
    
    LogManager::log("Mic initialized successfully.");
    return true;
}

bool AudioManager::startRecordingTask() {
    if (!_initialized) {
        if (!init()) {
            LogManager::log("Failed to initialize AudioManager!");
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
        &_recordAudioTaskHandle,
        1  // Run on Core 1
    ) != pdPASS) {
        LogManager::log("Failed to create record audio task!");
        return false;
    }
    
    LogManager::log("Record audio task started");
    return true;
}

bool AudioManager::startAudioFileTask() {
    if (!_initialized) {
        if (!init()) {
            LogManager::log("Failed to initialize AudioManager!");
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
        &_audioFileTaskHandle,
        0  // Run on Core 0
    ) != pdPASS) {
        LogManager::log("Failed to create audio file task!");
        return false;
    }
    
    LogManager::log("Audio file task started");
    return true;
}

void AudioManager::recordAudioTask(void* parameter) {
    if (!_initialized) {
        init();
    }
    
    while (true) {
        bool currentlyRequested = _app->isRecordingRequested();
        
        if (currentlyRequested) {
            _lastRecordStart = millis(); // Track when recording started
            AudioBuffer audio;

            // Use TimeManager for timestamp
            String ts = TimeManager::getTimestamp();
            snprintf(audio.timestamp, sizeof(audio.timestamp), "%s", ts.c_str());
            
            // Use "start" marker for the first chunk, then MIDDLE afterwards.
            if (!_wasRecording) {
                _wasRecording = true;
                audio.type = START;
                LogManager::log("Started audio recording");
            } else {
                audio.type = MIDDLE;
            }
            
            audio.buffer = _i2s.recordWAV(RECORD_TIME, &audio.size);
            
            if (audio.buffer == NULL || audio.size == 0) {
                LogManager::log("Failed to record audio: buffer is empty");
                free(audio.buffer); // Just in case
                vTaskDelay(pdMS_TO_TICKS(10));
                continue;
            }
            
            if (xQueueSend(_app->getAudioQueue(), &audio, pdMS_TO_TICKS(1000)) != pdPASS) {
                LogManager::log("Failed to enqueue audio buffer!");
                free(audio.buffer);
            }
        } else {
            // If we were recording but recording is now off, record a final chunk with "end" marker.
            if (_wasRecording) {
                AudioBuffer audio;
                String ts = TimeManager::getTimestamp();
                snprintf(audio.timestamp, sizeof(audio.timestamp), "%s", ts.c_str());
                audio.type = END;
                audio.buffer = _i2s.recordWAV(RECORD_TIME, &audio.size);
                
                if (audio.buffer == NULL || audio.size == 0) {
                    LogManager::log("Failed to record final audio: buffer is empty");
                    _wasRecording = false;
                    free(audio.buffer); // Just in case
                    continue;
                }
                
                if (xQueueSend(_app->getAudioQueue(), &audio, pdMS_TO_TICKS(1000)) != pdPASS) {
                    LogManager::log("Failed to enqueue final audio buffer!");
                    free(audio.buffer);
                }
                _wasRecording = false;
                LogManager::log("Ended audio recording");
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

void AudioManager::audioFileTask(void* parameter) {
    if (!_initialized) {
        init();
    }
    
    AudioBuffer audio;
    FileSystem* fs = FileSystem::getInstance();
    
    while (true) {
        QueueHandle_t audioQueue = _app->getAudioQueue();
        while (xQueueReceive(audioQueue, &audio, pdMS_TO_TICKS(10)) == pdTRUE) {
            String prefix = "_";
            if (audio.type == START)
                prefix += "start";
            else if (audio.type == END)
                prefix += "end";
            else if (audio.type == MIDDLE)
                prefix += "middle";
                
            String fileName = String(RECORDINGS_DIR) + "/" +
                              String(_app->getBootSession()) + "_" +
                              String(_app->getAudioFileIndex()) + "_" +
                              String(audio.timestamp) +
                              prefix + ".wav";
            _app->setAudioFileIndex(_app->getAudioFileIndex() + 1);

            // Instead of opening and writing to the file directly,
            // use the overwriteFile method with the raw bytes
            bool writeSuccess = false;
            
            // Create a temporary string to hold the binary data
            // Note: This is not an ideal approach for binary data, but it works for the WAV files
            uint8_t* buffer = audio.buffer;
            size_t size = audio.size;
            
            // Use a memory buffer to store the WAV data
            // Since overwriteFile expects a String, we'll need to create a special binary-safe string
            String binaryData;
            binaryData.reserve(size);  // Reserve space to avoid reallocations
            
            // Manually copy binary data to the String 
            for (size_t i = 0; i < size; i++) {
                binaryData += (char)buffer[i];
            }
            
            // Write the binary data to file
            if (fs->overwriteFile(fileName, binaryData)) {
                LogManager::log("Audio recorded and saved: " + fileName);
                _app->setWavFilesAvailable(true);

                // Add to upload queue
                if (fs->addToUploadQueue(fileName)) {
                    LogManager::log("Added to upload queue: " + fileName);
                } else {
                    LogManager::log("Failed to add to upload queue: " + fileName);
                }
            } else {
                LogManager::log("Failed to write audio data to file: " + fileName);
            }
            
            free(audio.buffer);
        }

        // Check if we should enter deep sleep
        if (_app->isReadyForDeepSleep() && 
            !_app->isRecordingRequested() && 
            !_app->isRecordingActive() &&
            uxQueueMessagesWaiting(_app->getAudioQueue()) == 0) {
        
            // Make sure log queue is also empty before sleep
            if (!LogManager::hasPendingLogs()) {
                LogManager::log("Recording stopped and all data processed. Entering deep sleep.");
                vTaskDelay(pdMS_TO_TICKS(500)); // Short delay to allow log to be written
                PowerManager::initDeepSleep();
            }
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

TaskHandle_t AudioManager::getRecordAudioTaskHandle() {
    return _recordAudioTaskHandle;
}

TaskHandle_t AudioManager::getAudioFileTaskHandle() {
    return _audioFileTaskHandle;
}

bool AudioManager::isRecordingActive() {
    return _wasRecording;
}

I2SClass* AudioManager::getI2S() {
    return &_i2s;
}

uint8_t* AudioManager::recordWAV(unsigned long recordTimeMs, size_t* size) {
    if (!_initialized) {
        init();
    }
    return _i2s.recordWAV(recordTimeMs, size);
}