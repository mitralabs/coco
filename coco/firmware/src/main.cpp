#include <Arduino.h>
#include <ESP_I2S.h>
#include <FS.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <SD.h>
#include <WiFi.h>
#include <esp_bt.h>
#include <esp_wifi.h>

#include "secrets.h"

#define LED_PIN 42

#define RECORD_TIME 30       // seconds
#define INITIAL_WAIT_TIME 5  // seconds
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

enum DeviceState { RECORDING, TRANSFERRING, SLEEP };

Preferences preferences;
I2SClass i2s;

File curr_file;
File recordings_root_dir;
File logFile;

DeviceState mode = RECORDING;

HTTPClient http;

int fileIndex = 0;
int recordingSession = 0;
int currentSessionTransfer = -1;

void setupWiFi();
void initSD();
void waitForTransferMode();
void initRecordingMode();
void recordingModeOnNextStart();
void initTransferMode();
void recordLoop();
void transferLoop();
void sleepLoop();
void transferFile();
void log(const String &message);
void ensureRecordingDirectory();
void ensureLogFile();
void sessionCompletelyTransfered(int value);
void blinkLED(int interval);

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);

  initSD();
  ensureRecordingDirectory();
  ensureLogFile();

  preferences.begin("power_state", false);
  int persistant_mode = preferences.getInt("state", RECORDING);
  preferences.end();

  if (persistant_mode == RECORDING) {
    waitForTransferMode();
    initRecordingMode();
  } else if (persistant_mode == TRANSFERRING) {
    recordingModeOnNextStart();
    initTransferMode();
  } else {
    log("Invalid state, entering 'Sleep' Mode.");
    mode = SLEEP;
  }
}

void loop() {
  switch (mode) {
    case RECORDING:
      recordLoop();
      break;
    case TRANSFERRING:
      transferLoop();
      break;
    case SLEEP:
      sleepLoop();
      break;
  }
}

void recordLoop() {
  log("Recording audio...");
  digitalWrite(LED_PIN, LOW);

  uint8_t *wav_buffer;
  size_t wav_size;

  wav_buffer = i2s.recordWAV(RECORD_TIME, &wav_size);

  String fileName = String(RECORDINGS_DIR) + "/audio_" +
                    String(recordingSession) + "_" + String(fileIndex) + ".wav";

  curr_file = SD.open(fileName, FILE_WRITE);
  if (!curr_file) {
    log("Failed to open file for writing: " + fileName);
    return;
  }

  if (curr_file.write(wav_buffer, wav_size) != wav_size) {
    log("Failed to write audio data to file: " + fileName);
  } else {
    log("Audio recorded and saved: " + fileName);
  }

  curr_file.close();
  free(wav_buffer);
  fileIndex++;  // Increment the file index and save it to preferences
}

void transferLoop() {
  while (curr_file) {
    if (!curr_file.isDirectory() &&
        String(curr_file.name()).startsWith("audio_")) {
      String fileName = curr_file.name();
      int session = fileName.substring(6, fileName.indexOf('_', 6))
                        .toInt();  // Adjust indices if format changes

      if (session != currentSessionTransfer) {
        if (currentSessionTransfer != -1) {  // If it's not the first session
          sessionCompletelyTransfered(
              currentSessionTransfer);  // Call for previous session
        }
        currentSessionTransfer = session;
      }

      if (curr_file.size() == 0) {
        SD.remove(
            (String(RECORDINGS_DIR) + "/" + String(curr_file.name())).c_str());
        log("File empty and deleted successfully: " + String(curr_file.name()));
        curr_file.close();
      } else {
        transferFile();  // Call the transfer function for non-empty files
      }
    }
    curr_file = recordings_root_dir.openNextFile();
  }

  recordings_root_dir.close();
  log("File transfer complete.");

  // Include Function to call the TransferSuccess Endpoint.
  sessionCompletelyTransfered(currentSessionTransfer);
  mode = SLEEP;
}

void sleepLoop() {
  esp_wifi_stop();
  esp_bt_controller_disable();
  log("Sleeping");
  delay(60 * 1000);
}

void setupWiFi() {
  WiFi.mode(WIFI_STA);

  log("Attempting to connect to WiFi: " + String(SSID));
  WiFi.begin(SSID, PASSWORD);

  log("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }

  // Show that connection attempt was successfully established through solid LED
  // turn on
  digitalWrite(LED_PIN, LOW);
  delay(3000);
  digitalWrite(LED_PIN, HIGH);

  log("Connected to WiFi. IP: " + WiFi.localIP().toString());
}

void transferFile() {
  bool transferSuccess = false;

  while (!transferSuccess) {
    log("Transferring file: " + String(curr_file.name()));

    HTTPClient client;

    // Add timeout settings
    client.setTimeout(10000);  // 10 seconds timeout

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
    client.addHeader("X-API-Key",
                     API_KEY);  // Add the API key as a custom header
    client.addHeader("Content-Disposition",
                     "form-data; name=\"file\"; filename=\"" +
                         String(curr_file.name()) + "\"");

    // Debug headers
    // log("Request headers:");
    // log("Content-Type: audio/wav");
    // log("Content-Disposition: form-data; name=\"file\"; filename=\"" +
    // String(file.name()) + "\"");

    int httpResponseCode =
        client.sendRequest("POST", &curr_file, curr_file.size());

    log("HTTP Response Code: " + String(httpResponseCode));

    // Debug response details
    if (httpResponseCode > 0) {
      if (httpResponseCode == 200) {
        String response = client.getString();
        log("Response body: " + response);

        // Success - delete file
        if (SD.remove((String(RECORDINGS_DIR) + "/" + String(curr_file.name()))
                          .c_str())) {
          log("File processed and deleted successfully: " +
              String(curr_file.name()));
        } else {
          log("Error: File could not be deleted. SD card error: " +
              String(SD.cardType()));
        }
        curr_file.close();
        transferSuccess = true;
      } else {
        // Get error response body
        String errorResponse = client.getString();
        log("Error response body: " + errorResponse);
        delay(BASE_DELAY);
      }
    } else {
      log("Failed to connect to server. Error: " +
          String(client.errorToString(httpResponseCode)));
    }

    client.end();
  }
}

void sessionCompletelyTransfered(int sessionId) {
  HTTPClient client;

  // Set a timeout for the HTTP request (10 seconds)
  client.setTimeout(10000);

  // Ensure WiFi is connected before making the request
  if (WiFi.status() != WL_CONNECTED) {
    log("WiFi disconnected. Attempting to reconnect...");
    WiFi.reconnect();
    delay(3000);
  }

  // Construct the endpoint URL by adding the session ID as a query parameter.
  String endpoint = String(TRANSFER_COMPLETE_ENDPOINT) +
                    "?recording_session=" + String(sessionId);

  // Initialize the connection to the endpoint
  client.begin(endpoint);

  // Add the required header for authentication
  client.addHeader("X-API-Key", API_KEY);

  // Send a GET request to the endpoint
  int httpResponseCode = client.GET();

  log("HTTP Response Code: " + String(httpResponseCode));

  if (httpResponseCode > 0) {
    // If the request was successful, retrieve and log the response
    String response = client.getString();
    log("Response body: " + response);
  } else {
    // Log an error message if the request failed
    log("Failed to connect to server. Error: " +
        String(client.errorToString(httpResponseCode)));
  }

  // End the connection and free resources
  client.end();
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
  }
}

void waitForTransferMode() {
  preferences.begin("power_state", false);
  log("Waiting for " + String(INITIAL_WAIT_TIME) +
      " seconds. In case User wants to initiate Transferring State.");
  preferences.putInt("state", TRANSFERRING);
  delay(INITIAL_WAIT_TIME * 1000);
  digitalWrite(LED_PIN, LOW);
  preferences.putInt("state", RECORDING);
  preferences.end();
}

void initRecordingMode() {
  log("Entering 'Recording' Mode.");
  mode = RECORDING;

  log("ADjusting CPU Frequency");
  setCpuFrequencyMhz(80);  // 80 is lowest stable frequency for recording.

  log("Turning off WiFi and Bluetooth");
  esp_wifi_stop();
  esp_bt_controller_disable();

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

void recordingModeOnNextStart() {
  preferences.begin("power_state", false);
  preferences.putInt("state", RECORDING);
  preferences.end();
}

void initTransferMode() {
  log("Entering 'Transfer' Mode.");
  mode = TRANSFERRING;

  log("ADjusting CPU Frequency");
  setCpuFrequencyMhz(240);

  setupWiFi();

  recordings_root_dir = SD.open("/recordings");
  if (!recordings_root_dir) {
    log("Failed to open recordings directory! Going to sleep.");
    mode = SLEEP;
    return;
  }

  log("Starting file transfer...");
  log("Connecting to endpoint: " + String(API_ENDPOINT));
  curr_file = recordings_root_dir.openNextFile();
}