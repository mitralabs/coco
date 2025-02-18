#include <Arduino.h>
#include <ESP_I2S.h>
#include <FS.h>
#include <Preferences.h>
#include <SD.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>

#define LED_PIN 2

#define RECORD_TIME 30       // seconds
#define SAMPLING_RATE \
  16000  // 16kHz is currently the best possible Sampling Rate. Optimizing
         // Battery and Quality.
#define BASE_DELAY 2000  // Delay between http Requests, if one failed.

#define RECORDINGS_DIR "/recordings"  // Directory constant
#define SD_SPEED \
  20000000  // Set frequency to 20 MHz, Maximum is probably around 25MHz default
            // is 4MHz, the rational is that a higher speed translates to a
            // shorter SD Card operation, which in turn translates to a lower
            // power consumption. Note: Higher is with current SD card not
            // possible.

Preferences preferences;
I2SClass i2s;

File curr_file;
File recordings_root_dir;
File logFile;

int fileIndex = 0;
int recordingSession = 0;

struct AudioBuffer {
  uint8_t *buffer;
  size_t size;
};

QueueHandle_t audioQueue; // For multiple buffers

void initSD();
void initRecordingMode();
void recordLoop(void *parameter);
void saveToSD(void *parameter);
void log(const String &message);
void ensureRecordingDirectory();
void ensureLogFile();
void blinkLED(int interval);

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);

  initSD();
  ensureRecordingDirectory();
  ensureLogFile();
  initRecordingMode();

  // Create a queue with space for 4 AudioBuffer items.
  audioQueue = xQueueCreate(4, sizeof(AudioBuffer));

  xTaskCreatePinnedToCore(recordLoop, "Record Loop", 4096, NULL, 1, NULL, 1); // Name, Stack size, Priority, Task handle, Core
  xTaskCreatePinnedToCore(saveToSD, "Save to SD", 4096, NULL, 1, NULL, 0);
}

void loop() {
  // Empty loop as tasks are running on different cores
}

void recordLoop(void *parameter) {
  while (true) {
    AudioBuffer audio;
    // Record into a local buffer.
    audio.buffer = i2s.recordWAV(RECORD_TIME, &audio.size);
    
    // Enqueue the audio buffer, waiting if needed.
    if (xQueueSend(audioQueue, &audio, portMAX_DELAY) != pdPASS) {
      log("Failed to enqueue audio buffer!");
      free(audio.buffer);
    }
    
    // Delay to yield to other tasks.
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void saveToSD(void *parameter) {
  AudioBuffer audio;
  while (true) {
    // Try to receive audio buffer from the queue.
    if (xQueueReceive(audioQueue, &audio, portMAX_DELAY) == pdTRUE) {
      String fileName = String(RECORDINGS_DIR) + "/audio_" +
                        String(recordingSession) + "_" + String(fileIndex) + ".wav";

      File curr_file = SD.open(fileName, FILE_WRITE);
      if (!curr_file) {
        log("Failed to open file for writing: " + fileName);
        free(audio.buffer);
        continue;
      }

      if (curr_file.write(audio.buffer, audio.size) != audio.size) {
        log("Failed to write audio data to file: " + fileName);
      } else {
        log("Audio recorded and saved: " + fileName);
      }

      curr_file.close();
      free(audio.buffer);
      fileIndex++;
    }
    // Yield to the scheduler.
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void log(const String &message) {
  Serial.println(message);

  // Add timestamp to log message
  String timestamp = String(millis());
  String logMessage = timestamp + ": " + message;

  // Append the new log message
  logFile = SD.open("/device.log", FILE_APPEND);
  if (logFile) {
    logFile.println(logMessage);
    logFile.flush();
    logFile.close();
  } else {
    Serial.println("Failed to open log file!");
  }
}

void initSD() {
  if (!SD.begin(21, SPI, SD_SPEED)) {
    Serial.println("Failed to mount SD Card!");
    blinkLED(100);
  }
  Serial.println("SD card initialized.");
}

void ensureRecordingDirectory() {
  if (!SD.exists(RECORDINGS_DIR)) {
    if (SD.mkdir(RECORDINGS_DIR)) {
      log("Recordings directory created");
    } else {
      log("Failed to create recordings directory!");
    }
  }
}

void ensureLogFile() {
  if (!SD.exists("/device.log")) {
    File logFile = SD.open("/device.log", FILE_WRITE);
    if (logFile) {
      logFile.println("=== Device Log Started ===");
      logFile.flush();
      logFile.close();
    }
  }
}

void blinkLED(int interval) {
  unsigned long last_toggle = 0;
  bool led_state = HIGH;
  while (true) {
    unsigned long curr_millis = millis();

    if (curr_millis - last_toggle >= interval) {
      last_toggle = curr_millis;
      led_state = !led_state;
      digitalWrite(LED_PIN, led_state);
    }
    // Yield to ensure the watchdog is reset.
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void initRecordingMode() {
  
    log("ADjusting CPU Frequency");
    setCpuFrequencyMhz(80);  // 80 is lowest stable frequency for recording.
  
    log("Initializing PDM Microphone...");
    i2s.setPinsPdmRx(42, 41);
  
    // The transmission mode is PDM_MONO_MODE, which means that PDM (pulse
    // density modulation) mono mode is used for transmission
    if (!i2s.begin(I2S_MODE_PDM_RX, SAMPLING_RATE, I2S_DATA_BIT_WIDTH_16BIT,
                   I2S_SLOT_MODE_MONO)) {
      log("Failed to initialize I2S!");
      blinkLED(100);
    }
    log("Mic initialized.");
  
    preferences.begin("audio", false);
    recordingSession = preferences.getInt("session", 0);
    log("Recording Session: " + String(recordingSession));
    fileIndex = 1;  // Set the Fileindex to 1. Will be increased within the
                    // recording loop.
    preferences.putInt("session", recordingSession + 1);
    preferences.end();
  }