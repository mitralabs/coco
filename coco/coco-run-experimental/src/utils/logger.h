#ifndef LOGGER_H
#define LOGGER_H

#include <Arduino.h>

void log(const String &message) {
    Serial.println(message);
}

void logError(const String &message) {
    Serial.print("ERROR: ");
    Serial.println(message);
}

void logInfo(const String &message) {
    Serial.print("INFO: ");
    Serial.println(message);
}

#endif // LOGGER_H