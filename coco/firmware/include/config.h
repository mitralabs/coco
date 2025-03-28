/**
 * @file config.h
 * @brief Configuration settings for the Coco firmware
 * 
 * This file contains all configuration parameters organized by their function.
 */

#ifndef CONFIG_H
#define CONFIG_H

#define CPU_FREQ_MHZ 80        // CPU frequency in MHz, // 80 is lowest stable frequency for this routine.

/**********************************
 *       PIN DEFINITIONS          *
 **********************************/
#define LED_PIN 2           // LED pin
#define BUTTON_PIN GPIO_NUM_1   // Button input pin
#define BATTERY_PIN 4           // ADC pin for battery voltage monitoring

/**********************************
 *    AUDIO RECORDING SETTINGS    *
 **********************************/
#define RECORD_TIME 10          // Recording duration in seconds
#define AUDIO_QUEUE_SIZE 10     // Size of the audio buffer queue
#define SAMPLING_RATE 16000     // 16kHz sampling rate (optimizing battery and quality)

/**********************************
 *    FILE & STORAGE SETTINGS     *
 **********************************/
#define RECORDINGS_DIR "/recordings"     // Directory for audio recordings
#define UPLOAD_QUEUE_FILE "/upload_queue.txt"  // File that stores the upload queue
#define UPLOAD_QUEUE_TEMP "/upload_queue.tmp"  // Temporary file for upload queue
#define SD_SPEED 20000000       // SD card SPI frequency (20 MHz)
#define LOG_FILE "/device.log"  // System log file path
#define TIME_FILE "/time.txt"   // Stored time file path

/**********************************
 *      TASK & QUEUE SETTINGS     *
 **********************************/
#define LOG_QUEUE_SIZE 20       // Size of the log message queue
#define ENABLE_STACK_MONITORING false  // Enable/disable stack usage monitoring

/**********************************
 *     TIMING & SLEEP SETTINGS    *
 **********************************/
#define BUTTON_PRESS_TIME 1000   // Button press detection time (ms)
#define SLEEP_TIMEOUT_SEC 6000   // Deep sleep period in seconds
#define BATTERY_MONITOR_INTERVAL 60000  // Battery check interval (ms)
#define TIME_PERSIST_INTERVAL 60000     // Time persistence interval (ms)
#define DEEP_SLEEP_CHECK_INTERVAL 5000  // Deep sleep readiness check interval (ms)

/**********************************
 *      TIME & DATE SETTINGS      *
 **********************************/
#define DEFAULT_TIME 1740049200  // Default time: 2025-02-20 12:00:00 GMT+01:00
#define TIMEZONE "GMT"           // Timezone setting

/**********************************
 *    NETWORK & WIFI SETTINGS     *
 **********************************/
#define MIN_SCAN_INTERVAL 5000   // Minimum interval between WiFi scans (ms)
#define MAX_SCAN_INTERVAL 600000 // Maximum interval between WiFi scans (ms)
#define HTTP_TIMEOUT 10000       // HTTP request timeout (ms)
#define UPLOAD_CHECK_INTERVAL 2000 // Upload queue check interval (ms)

/**********************************
 *      LED SETTINGS              *
 **********************************/
#define LED_FREQUENCY 5000       // LED PWM frequency
#define LED_RESOLUTION 8         // LED PWM resolution

/**********************************
 *     BATTERY SETTINGS           *
 **********************************/
#define BATTERY_UPLOAD_THRESHOLD 3.7  // Minimum battery voltage (V) required for file uploads
#define BATTERY_RECORDING_THRESHOLD 3.55  // Minimum battery voltage (V) required for recording
#define BATTERY_MIN_VOLTAGE 3.5f   // Minimum battery voltage (empty)
#define BATTERY_MAX_VOLTAGE 4.2f   // Maximum battery voltage (full)
#define VOLTAGE_DIVIDER_RATIO 2.0f // Based on the voltage divider used in the hardware

#endif // CONFIG_H
