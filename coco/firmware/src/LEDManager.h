/**
 * @file LEDManager.h
 * @brief Header file for LED management functionality
 */

#ifndef LED_MANAGER_H
#define LED_MANAGER_H

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

// Forward declaration
class Application;

class LEDManager {
private:
    // Static members for singleton pattern
    static bool initialized;
    static LEDManager* instance;
    static Application* app;
    
    // LED related variables
    SemaphoreHandle_t ledMutex;
    int ledPin;
    int ledFrequency;
    int ledResolution;
    
    // Private constructor for singleton pattern
    LEDManager();
    
public:
    /**
     * @brief Get the singleton instance of LEDManager
     * @return Pointer to the LEDManager instance
     */
    static LEDManager* getInstance();
    
    /**
     * @brief Initialize the LED manager
     * @param appInstance Pointer to the Application instance
     * @param pin LED pin number
     * @param frequency LED PWM frequency
     * @param resolution LED PWM resolution
     * @return true if initialization was successful, false otherwise
     */
    bool init(Application* appInstance = nullptr, int pin = -1, int frequency = -1, int resolution = -1);
    
    /**
     * @brief Set the LED state
     * @param state true for ON, false for OFF
     */
    void setLEDState(bool state);
    
    /**
     * @brief Set the LED brightness
     * @param brightness Brightness value (0-255)
     */
    void setLEDBrightness(int brightness);
    
    /**
     * @brief Blink the LED in an error pattern
     * @param interval Interval between state changes in milliseconds
     * @note This function does not return
     */
    void errorBlinkLED(int interval);
    
    /**
     * @brief Get the LED mutex
     * @return LED mutex handle
     */
    SemaphoreHandle_t getLEDMutex();
};

#endif // LED_MANAGER_H
