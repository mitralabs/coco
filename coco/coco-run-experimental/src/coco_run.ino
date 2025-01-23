#include <Arduino.h>
#include <FreeRTOS.h>
#include <semphr.h>
#include "audio/recorder.h"
#include "storage/storage.h"
#include "utils/logger.h"

SemaphoreHandle_t xSemaphore;

void recordingTask(void *pvParameters) {
    Recorder recorder;
    while (true) {
        recorder.startRecording();
        log("Recording...");
        vTaskDelay(1000 / portTICK_PERIOD_MS); // Simulate recording delay
        xSemaphoreGive(xSemaphore);
        recorder.stopRecording();
    }
}

void savingTask(void *pvParameters) {
    Storage storage;
    while (true) {
        if (xSemaphoreTake(xSemaphore, portMAX_DELAY) == pdTRUE) {
            storage.saveAudio();
            log("Saving...");
            vTaskDelay(2000 / portTICK_PERIOD_MS); // Simulate saving delay
        }
    }
}

void setup() {
    Serial.begin(115200);
    xSemaphore = xSemaphoreCreateBinary();

    xTaskCreatePinnedToCore(recordingTask, "RecordingTask", 10000, NULL, 1, NULL, 0);
    xTaskCreatePinnedToCore(savingTask, "SavingTask", 10000, NULL, 1, NULL, 1);
}

void loop() {
    // The loop function is empty because the tasks are handling the work
}