#include <Arduino.h>

#include <WiFi.h>

#include <esp_wifi.h>
#include <esp_bt.h>

#include <Preferences.h>
#include <HTTPClient.h>

#include "ESP_I2S.h"
#include "FS.h"
#include "SD.h"

// Constants
#define RECORD_TIME 30  // seconds
#define INITIAL_WAIT_TIME 5 // seconds
#define SAMPLING_RATE 16000 // 16kHz is currently the best possible Sampling Rate. Optimizing Battery and Quality.
#define API_ENDPOINT "http://cocobase.local:3030/uploadAudio"  // Replace with your actual API endpoint
#define API_KEY "please_smile" // Replace with actual API key

#define BASE_DELAY 1000. // Delay between http Requests, if one failed.

#define RECORDINGS_DIR "/recordings" // Directory constant
#define SD_SPEED 20000000 // Set frequency to 20 MHz, Maximum is probably around 25MHz default is 4MHz, the rational is that a higher speed translates to a shorter SD Card operation, which in turn translates to a lower power consumption. Note: Higher is with current SD card not possible.

enum DeviceState {
  RECORDING,
  TRANSFERRING,
  SLEEP
};

// Global variables
Preferences preferences;
I2SClass i2s;

File file; 
File root;
File logFile;

DeviceState currentState = RECORDING;

HTTPClient http;

// Global variable for file index
int fileIndex = 0;
int recordingSession = 0;

const char *ssid = "coco_connect";
const char *password = "please_smile";

// Function prototypes
void setupWiFi();
void recordAudio();
void transferFiles();
void enterDeepSleep();
void log(const String& message);
void ensureRecordingDirectory();
void ensureLogFile();


////////////////////
// Main SETUP Function
////////////////////

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);

  // Initialize SD card
  if (!SD.begin(21, SPI, SD_SPEED)) {
    Serial.println("Failed to mount SD Card!");
    while (1) {
      // Rapid blink to indicate error
      blinkLED(100);
    }
  }
  Serial.println("SD card initialized.");
  // Ensure Filestructure
  ensureRecordingDirectory();
  ensureLogFile();


  // Connecting to the "power_state" directory on persistent storage
  preferences.begin("power_state", false);
  // Read the current state from persistent storage
  int state = preferences.getInt("state", 0);

  // Check the state and perform the appropriate actions
  if (state == 0) {
    log("Waiting for " + String(INITIAL_WAIT_TIME) + " seconds. In case User wants to initiate Transferring State.");
    preferences.putInt("state", 1); // Update state to 1
    
    // As long as the LED is off, the device can be set to transfer mode.
    delay(INITIAL_WAIT_TIME * 1000); // Wait for a couple of seconds.
    digitalWrite(LED_BUILTIN, LOW);

    preferences.putInt("state", 0); // Reset state to 0
    preferences.end();

    log("Entering 'Recording' Mode.");
    // Entering Recording Mode
    currentState = RECORDING;

  } else if (state == 1) {
    preferences.putInt("state", 0); // Reset state to 0
    preferences.end();

    log("Entering 'Transfer' Mode.");
    currentState = TRANSFERRING;

  } else {
    log("Invalid state, entering 'Sleep' Mode.");
    currentState = SLEEP;
  }
}


///////////////////////////////////////////////////////
////////////// Main Loop, but more a router I guess.
///////////////////////////////////////////////////////

void loop() {
  switch (currentState) {
    case RECORDING:
      setCpuFrequencyMhz(80); // 80 is lowest stable frequency for recording.

      // Turn off WiFi and Bluetooth to save power
      esp_wifi_stop();
      esp_bt_controller_disable();

      // setup 42 PDM clock and 41 PDM data pins
      log("Initializing PDM Microphone...");
      i2s.setPinsPdmRx(42, 41);

      //The transmission mode is PDM_MONO_MODE, which means that PDM (pulse density modulation) mono mode is used for transmission
      if (!i2s.begin(I2S_MODE_PDM_RX, SAMPLING_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
        log("Failed to initialize I2S!");
        while (1) {
          // Rapid blink to indicate error
          blinkLED(100);
        }
      }
      log("Mic initialized.");
      
      preferences.begin("audio", false);
      recordingSession = preferences.getInt("session", 0);
      log("Recording Session: " + String(recordingSession));
      preferences.putInt("session", recordingSession + 1); // Reset state to 0
      preferences.end();
      
      fileIndex = 1; // Set the Fileindex to 1. Will be increased within the recording loop.

      recordAudio();
      break;

    case TRANSFERRING:
      setCpuFrequencyMhz(240); // Set to highest frequency to ensure speedy file transfer.
      transferFiles();
      break;

    case SLEEP:
      // Turn off WiFi and Bluetooth to save power
      esp_wifi_stop();
      esp_bt_controller_disable();
      log("Sleeping");
      setCpuFrequencyMhz(10); // Maybe setting CPU to lowest clock.
      // Do nothing. Maybe include some DeepSleep Functionallity some time.
      delay(60000); // Wait for a minute. Without the delay, the processor will freeze sooner or later. 
      break;
  }
}

///////////////////////////////////////////////////////
////////////// Main Functions
///////////////////////////////////////////////////////

void recordAudio() {
  
  log("Recording audio...");
  digitalWrite(LED_BUILTIN, LOW);

  while (1) {
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
}

/////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////

void setupWiFi() {
  WiFi.mode(WIFI_STA);

  log("Attempting to connect to WiFi: " + String(ssid));
  WiFi.begin(ssid, password);

  log("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }

  // Show that connection attempt was successfully established through solid LED turn on
  digitalWrite(LED_BUILTIN, LOW);  
  delay(3000);                   
  digitalWrite(LED_BUILTIN, HIGH);

  log("Connected to WiFi. IP: " + WiFi.localIP().toString());
}


/////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////

void transferFiles() {
  setupWiFi();
  
  // Open the recordings directory
  root = SD.open("/recordings");
  if(!root){
    log("Failed to open recordings directory! Going to sleep.");
    currentState = SLEEP;
    return;
  }

  log("Starting file transfer...");
  log("Connecting to endpoint: " + String(API_ENDPOINT));
  file = root.openNextFile();
  while (file) {
      if (!file.isDirectory() && String(file.name()).startsWith("audio_")) {
          if (file.size() == 0) {
            SD.remove((String(RECORDINGS_DIR) + "/" + String(file.name())).c_str());
            log("File empty and deleted successfully: " + String(file.name()));
            file.close();
          } else{
            bool transferSuccess = false;
            
            while (!transferSuccess) {
                log("Transferring file: " + String(file.name()));

                HTTPClient client;

                // Add timeout settings
                client.setTimeout(10000); // 10 seconds timeout

                // Debug connection details
                // log("File name: " + String(file.name()));
                // log("File size: " + String(file.size()));
                
                // Check WiFi status before trying
                if (WiFi.status() != WL_CONNECTED) {
                    log("WiFi disconnected. Attempting to reconnect...");
                    WiFi.reconnect();
                    delay(3000);
                }

                client.begin(API_ENDPOINT);
                client.addHeader("Content-Type", "audio/wav");
                client.addHeader("X-API-Key", API_KEY); // Add the API key as a custom header
                client.addHeader("Content-Disposition", "form-data; name=\"file\"; filename=\"" + String(file.name()) + "\"");

                // Debug headers
                // log("Request headers:");
                // log("Content-Type: audio/wav");
                // log("Content-Disposition: form-data; name=\"file\"; filename=\"" + String(file.name()) + "\"");

                int httpResponseCode = client.sendRequest("POST", &file, file.size());

                log("HTTP Response Code: " + String(httpResponseCode));

                // Debug response details
                if (httpResponseCode > 0) {
                                    
                    if (httpResponseCode == 200) {
                        String response = client.getString();
                        log("Response body: " + response);
                        
                        // Success - delete file
                        if (SD.remove((String(RECORDINGS_DIR) + "/" + String(file.name())).c_str())) {
                            log("File processed and deleted successfully: " + String(file.name()));
                        } else {
                            log("Error: File could not be deleted. SD card error: " + String(SD.cardType()));
                        }
                        file.close();
                        transferSuccess = true;
                    } else {                      
                        // Get error response body
                        String errorResponse = client.getString();
                        log("Error response body: " + errorResponse);
                    }
                } else {
                    log("Failed to connect to server. Error: " + String(client.errorToString(httpResponseCode)));
                }

                client.end();
                
                delay(BASE_DELAY);
            }
          }        
        }
        file = root.openNextFile();
  }
  
  root.close();
  log("File transfer complete.");
  currentState = SLEEP;
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

/////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////

void blinkLED(int interval) {
  static unsigned long previousMillis = 0;
  static bool ledState = HIGH;
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    ledState = !ledState;
    digitalWrite(LED_BUILTIN, ledState);
  }
}