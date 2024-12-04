#include <Arduino.h>

#include <esp_wifi.h>
#include <esp_bt.h>

#include <Preferences.h>

#include "ESP_I2S.h"
#include "FS.h"
#include "SD.h"

// Constants
#define RECORD_TIME 30  // seconds
#define INITIAL_WAIT_TIME 5 // seconds
#define SAMPLING_RATE 16000 // 16kHz is currently the best possible Sampling Rate. Optimizing Battery and Quality.

#define RECORDINGS_DIR "/recordings" // Directory constant
#define SD_SPEED 20000000 // Set frequency to 20 MHz, Maximum is probably around 25MHz default is 4MHz, the rational is that a higher speed translates to a shorter SD Card operation, which in turn translates to a lower power consumption. Note: Higher is with current SD card not possible.

enum DeviceState {
  RECORDING,
  TRANSFERRING
};

// Global variables
Preferences preferences;
I2SClass i2s;

File file; 
File root;
File logFile;
File audioFile;

DeviceState currentState = RECORDING;

// Global variable for file index
int fileIndex = 0;
int recordingSession = 0;


// Function prototypes
void recordAudio();
void log(const String& message);
void ensureRecordingDirectory();
void ensureLogFile();
void listFiles();
void deleteFile(String filename);
void sendFile(String filename);

////////////////////
// Main SETUP Function
////////////////////

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);

  // Turn off WiFi and Bluetooth to save power
  esp_wifi_stop();
  esp_bt_controller_disable();

  // Initialize SD card
  if (!SD.begin(21, SPI, SD_SPEED)) {
    Serial.println("Failed to mount SD Card!");
    while (1) {
      // Rapid blink to indicate error
      digitalWrite(LED_BUILTIN, HIGH);  
      delay(200);                   
      digitalWrite(LED_BUILTIN, LOW);
      delay(200);
    }
  }
  Serial.println("SD card initialized.");
  // Ensure Filestructure
  ensureRecordingDirectory();
  ensureLogFile();

  if (Serial) {
    currentState = TRANSFERRING;
    log("Entering 'Transfer' Mode.");
  }
  else {
    currentState = RECORDING;
    log("Entering 'Recording' Mode.");

    // setup 42 PDM clock and 41 PDM data pins
    log("Initializing PDM Microphone...");
    i2s.setPinsPdmRx(42, 41);

    //The transmission mode is PDM_MONO_MODE, which means that PDM (pulse density modulation) mono mode is used for transmission
    if (!i2s.begin(I2S_MODE_PDM_RX, SAMPLING_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
      log("Failed to initialize I2S!");
      while (1) {
        // Distinct blink to indicate Mic SetUp Error (is rare)
        digitalWrite(LED_BUILTIN, LOW);  
        delay(100);
        digitalWrite(LED_BUILTIN, HIGH);
        delay(100);
        digitalWrite(LED_BUILTIN, LOW);  
        delay(2000);
        digitalWrite(LED_BUILTIN, HIGH);
        delay(2000);
      }
    }
    log("Mic initialized.");
    
    preferences.begin("audio", false);
    recordingSession = preferences.getInt("session", 0);
    log("Recording Session: " + String(recordingSession));
    preferences.putInt("session", recordingSession + 1); // Reset state to 0
    preferences.end();
    
    fileIndex = 1; // Set the Fileindex to 1. Will be increased within the recording loop.
    log("Recording audio...");
  }
}


///////////////////////////////////////////////////////
////////////// Main Loop, but more a router I guess.
///////////////////////////////////////////////////////

void loop() {
  switch (currentState) {
    case RECORDING:
      recordAudio();
      break;

    case TRANSFERRING:
      if (Serial.available()) {
          char cmd = Serial.read();
          if (cmd == 'L') {
              listFiles();
          }
          else if (cmd == 'R') {
              String filename = Serial.readStringUntil('\n');
              sendFile(filename);
          }
          else if (cmd == 'D') {
              String filename = Serial.readStringUntil('\n');
              deleteFile(filename);
          }
      }
      break;
  }
}

///////////////////////////////////////////////////////
////////////// Main Functions
///////////////////////////////////////////////////////

void recordAudio() {
  digitalWrite(LED_BUILTIN, LOW);
  uint8_t *wav_buffer;
  size_t wav_size;

  wav_buffer = i2s.recordWAV(RECORD_TIME, &wav_size);

  String fileName = String(RECORDINGS_DIR) + "/audio_" + String(recordingSession) + "_" + String(fileIndex) + ".wav";

  file = SD.open(fileName, FILE_WRITE);
  if (!file) {
    log("Failed to open file for writing: " + fileName);
    return;
  }

  if (file.write(wav_buffer, wav_size) != wav_size) {
    log("Failed to write audio data to file: " + fileName);
  } else {
    log("Audio recorded and saved: " + fileName);
  }

  file.close();
  free(wav_buffer);
  fileIndex++; // Increment the file index and save it to preferences
  digitalWrite(LED_BUILTIN, LOW);
}

/////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////
void listFiles() {
    File root = SD.open("/recordings");
    while (File file = root.openNextFile()) {
        Serial.println(file.name());
        file.close();
    }
    root.close();
    Serial.println("END_LIST");
}

void sendFile(String filename) {
    File file = SD.open("/recordings/" + filename);
    if (!file) {
        Serial.write((uint8_t)0);  // Size 0 indicates error
        return;
    }
    
    uint32_t fileSize = file.size();
    Serial.write((uint8_t*)&fileSize, 4);
    
    // Send in chunks
    uint8_t buffer[1024];
    while (file.available()) {
        int bytesRead = file.read(buffer, sizeof(buffer));
        Serial.write(buffer, bytesRead);
    }
    file.close();
}

void deleteFile(String filename) {
    if (SD.remove("/recordings/" + filename)) {
        Serial.write((uint8_t)1);  // Success
    } else {
        Serial.write((uint8_t)0);  // Failed
    }
}

///////////////////////////////////////////////////////
////////////// Helper Functions
///////////////////////////////////////////////////////

void log(const String& message) {
  
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

/////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////

void ensureRecordingDirectory() {
  if (!SD.exists(RECORDINGS_DIR)) {
    if (SD.mkdir(RECORDINGS_DIR)) {
      log("Recordings directory created");
    } else {
      log("Failed to create recordings directory!");
    }
  }
}

/////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////

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