Yes, it is possible to call one task from another in FreeRTOS, but it's important to understand that tasks in FreeRTOS are meant to run independently and concurrently. Directly calling a task function from another task is not the typical way to manage task interactions. Instead, you can use FreeRTOS mechanisms like semaphores, queues, or task notifications to synchronize and communicate between tasks.

Here's an example of how you can use a semaphore to signal the saving task to start after each recording loop is over:

Include the necessary libraries:


#include <Arduino.h>
#include <semphr.h>  // For semaphore
Define the tasks and the semaphore:


SemaphoreHandle_t xSemaphore;

void recordingTask(void *pvParameters) {
    while (true) {
        // Your recording code here
        Serial.println("Recording...");
        // Simulate recording delay
        vTaskDelay(1000 / portTICK_PERIOD_MS);

        // Signal the saving task to start
        xSemaphoreGive(xSemaphore);
    }
}

void savingTask(void *pvParameters) {
    while (true) {
        // Wait for the semaphore to be given
        if (xSemaphoreTake(xSemaphore, portMAX_DELAY) == pdTRUE) {
            // Your saving code here
            Serial.println("Saving...");
            // Simulate saving delay
            vTaskDelay(2000 / portTICK_PERIOD_MS);
        }
    }
}
Create the tasks and the semaphore in the setup function:


void setup() {
    Serial.begin(115200);

    // Create the semaphore
    xSemaphore = xSemaphoreCreateBinary();

    // Create the recording task
    xTaskCreatePinnedToCore(
        recordingTask,   // Task function
        "RecordingTask", // Name of task
        10000,           // Stack size of task
        NULL,            // Parameter of the task
        1,               // Priority of the task
        NULL,            // Task handle to keep track of created task
        0);              // Pin task to core 0

    // Create the saving task
    xTaskCreatePinnedToCore(
        savingTask,      // Task function
        "SavingTask",    // Name of task
        10000,           // Stack size of task
        NULL,            // Parameter of the task
        1,               // Priority of the task
        NULL,            // Task handle to keep track of created task
        1);              // Pin task to core 1
}

void loop() {
    // The loop function is empty because the tasks are handling the work
}
Explanation:

Semaphore: A semaphore is used to signal between tasks. The xSemaphoreCreateBinary function creates a binary semaphore, which can be either available (1) or not available (0).
xSemaphoreGive: This function gives (or sets) the semaphore, making it available. In the recordingTask, this is called after the recording is complete to signal the savingTask.
xSemaphoreTake: This function takes (or waits for) the semaphore. In the savingTask, this is called to wait for the semaphore to be given by the recordingTask. The portMAX_DELAY parameter makes the task wait indefinitely until the semaphore is available.
This setup ensures that the saving task starts only after the recording task has completed its loop, achieving the desired synchronization between the tasks.