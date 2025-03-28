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
public:
    /**
     * @brief Initialize the LED manager
     * @param appInstance Pointer to the Application instance
     * @param pin LED pin number
     * @param frequency LED PWM frequency
     * @param resolution LED PWM resolution
     * @return true if initialization was successful, false otherwise
     */
    static bool init(Application* appInstance = nullptr, int pin = -1, int frequency = -1, int resolution = -1);
    
    /**
     * @brief Set the LED state
     * @param state true for ON, false for OFF
     */
    static void setLEDState(bool state);
    
    /**
     * @brief Set the LED brightness
     * @param brightness Brightness value (0-255)
     */
    static void setLEDBrightness(int brightness);
    
    /**
     * @brief Indicate battery level by blinking the LED
     * @param batteryLevel Battery level (1-4) where 1 is lowest and 4 is highest
     * @param blinkDuration Duration of each blink in milliseconds
     * @param pauseDuration Duration between blinks in milliseconds
     */
    static void indicateBatteryLevel(int batteryLevel, int blinkDuration = 200, int pauseDuration = 200);
    
    /**
     * @brief Blink the LED in an error pattern
     * @param interval Interval between state changes in milliseconds
     * @note This function does not return
     */
    static void errorBlinkLED(int interval);
    
    /**
     * @brief Blink the LED in an error pattern for a specific duration
     * @param interval Interval between state changes in milliseconds
     * @param duration Total duration in milliseconds to blink (0 for infinite)
     * @return True if completed successfully
     */
    static bool timedErrorBlinkLED(int interval, unsigned long duration = 0);
    
    /**
     * @brief Get the LED mutex
     * @return LED mutex handle
     */
    static SemaphoreHandle_t getLEDMutex();

private:
    // Private constructor for static-only class
    LEDManager() = default;
    LEDManager(const LEDManager&) = delete;
    LEDManager& operator=(const LEDManager&) = delete;
    
    // Static members
    static bool initialized;
    static Application* app;
    
    // LED related variables
    static SemaphoreHandle_t ledMutex;
    static int ledPin;
    static int ledFrequency;
    static int ledResolution;
    static int brightness;  // Store current brightness value
};

#endif // LED_MANAGER_H
