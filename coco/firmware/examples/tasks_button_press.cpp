#include <Arduino.h>

#define GPIO_INPUT_PIN 7  // GPIO pin to monitor
#define PRESS_TIME_MS   2000  // 2 seconds (threshold time in milliseconds)

TaskHandle_t micTaskHandle = NULL;

// Microphone Task on Core 1
void MicrophoneTask(void *pvParameters) {
    Serial.println("Microphone Task running on Core 1");
    while (1) {
        Serial.println("Recording audio...");
        delay(500);  // Simulate recording (replace with actual logic)

        // Wait for a stop signal
        if (ulTaskNotifyTake(pdTRUE, 0)) {  // Check for notification
            Serial.println("Recording stopped due to button press!");
            break;  // Stop recording
        }
    }
    vTaskDelete(NULL);  // End task
}

// GPIO Monitoring Task on Core 0
void GPIOMonitorTask(void *pvParameters) {
    pinMode(GPIO_INPUT_PIN, INPUT_PULLUP);
    Serial.println("GPIO Monitoring Task running on Core 0");

    TickType_t pressStartTime = 0;  // Variable to track the press start time
    bool buttonPressed = false;

    while (1) {
        if (digitalRead(GPIO_INPUT_PIN) == HIGH) {  // Button is pressed
            if (!buttonPressed) {
                // Record the tick count when the button press starts
                pressStartTime = xTaskGetTickCount();
                buttonPressed = true;
                Serial.println("Button pressed... monitoring duration.");
            } else {
                // Check if button has been pressed for the threshold time
                TickType_t elapsedTime = xTaskGetTickCount() - pressStartTime;
                if (elapsedTime >= pdMS_TO_TICKS(PRESS_TIME_MS)) {  // 2 seconds
                    Serial.println("Button held for 2 seconds. Stopping microphone task...");
                    xTaskNotifyGive(micTaskHandle);  // Notify the microphone task
                    buttonPressed = false;  // Reset the button state
                    vTaskDelay(500);  // Avoid retriggering immediately
                }
            }
        } else {
            // Button is released, reset state
            if (buttonPressed) {
                Serial.println("Button released before 2 seconds.");
            }
            buttonPressed = false;
        }

        vTaskDelay(10);  // Poll the button state every 10ms
    }
}

void setup() {
    Serial.begin(115200);

    // Create Microphone Task on Core 1
    xTaskCreatePinnedToCore(
        MicrophoneTask, "Microphone Task", 4096, NULL, 1, &micTaskHandle, 1);

    // Create GPIO Monitoring Task on Core 0
    xTaskCreatePinnedToCore(
        GPIOMonitorTask, "GPIO Monitor", 2048, NULL, 1, NULL, 0);
}

void loop() {
    // Main loop does nothing; tasks run independently
}
