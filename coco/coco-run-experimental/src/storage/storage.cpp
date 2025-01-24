#include "storage.h"
#include <Arduino.h>
#include <Preferences.h>

Preferences preferences;

void Storage::init() {
    preferences.begin("audio", false);
}

void Storage::saveAudioData(const uint8_t* data, size_t size) {
    String fileName = "recording_" + String(preferences.getInt("session", 0)) + ".wav";
    File file = SPIFFS.open("/" + fileName, "w");

    if (!file) {
        Serial.println("Failed to open file for writing");
        return;
    }

    file.write(data, size);
    file.close();
    Serial.println("Audio data saved to " + fileName);
}

void Storage::endSession() {
    preferences.putInt("session", preferences.getInt("session", 0) + 1);
    preferences.end();
}