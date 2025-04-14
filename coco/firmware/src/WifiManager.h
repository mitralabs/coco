/**
 * @file WifiManager.h
 * @brief WiFi connection management system for the Coco firmware
 * 
 * This module handles WiFi initialization, connection management, scanning,
 * and event handling. It manages connections with exponential backoff and
 * implements automatic reconnection logic.
 */

#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

// Standard libraries
#include <Arduino.h>

// ESP libraries
#include <WiFi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

// Project includes
#include "config.h"
#include "secrets.h"
#include "Application.h"

class WifiManager {
public:
    // Singleton pattern enforcement
    WifiManager(const WifiManager&) = delete;
    WifiManager& operator=(const WifiManager&) = delete;
    
    /**
     * @brief Initialize the WiFi management system
     * @param app Pointer to the Application instance
     * @return True if initialization succeeded, false otherwise
     */
    static bool init(Application* app = nullptr);
    
    // Connection management methods
    /**
     * @brief Attempt to connect to the configured WiFi network
     * @return True if connection attempt initiated, false otherwise
     */
    static bool connect();
    
    /**
     * @brief Disconnect from the current WiFi network
     * @return True if successfully disconnected, false otherwise
     */
    static bool disconnect();
    
    /**
     * @brief Check if WiFi is currently connected
     * @return True if connected, false otherwise
     */
    static bool isConnected();
    
    // Network information methods
    /**
     * @brief Scan for available WiFi networks
     * @return Number of networks found, or -1 on error
     */
    static int scanNetworks();
    
    /**
     * @brief Get the current RSSI (signal strength)
     * @return RSSI value in dBm, or 0 if not connected
     */
    static int getRSSI();
    
    /**
     * @brief Get the current local IP address
     * @return String representation of IP address
     */
    static String getLocalIP();
    
    // Task management methods
    /**
     * @brief Start the WiFi connection task
     * @return True if task creation succeeded, false otherwise
     */
    static bool startConnectionTask();
    
    /**
     * @brief Delete the WiFi connection task if it exists
     */
    static void deleteConnectionTask();
    
    /**
     * @brief Get the task handle for the WiFi connection task
     * @return FreeRTOS task handle
     */
    static TaskHandle_t getConnectionTaskHandle() { return wifiConnectionTaskHandle; }
    
    // State management methods
    /**
     * @brief Get the current scan interval
     * @return Current scan interval in milliseconds
     */
    static unsigned long getCurrentScanInterval();
    
    /**
     * @brief Set the current scan interval
     * @param interval New scan interval in milliseconds
     */
    static void setCurrentScanInterval(unsigned long interval);
    
    /**
     * @brief Get the next WiFi scan time
     * @return Next scheduled scan time in milliseconds
     */
    static unsigned long getNextWifiScanTime();
    
    /**
     * @brief Set the next WiFi scan time
     * @param time Next scan time in milliseconds
     */
    static void setNextWifiScanTime(unsigned long time);

private:
    // Private constructor - singleton pattern
    WifiManager() = default;
    
    // WiFi task management
    /**
     * @brief WiFi connection task function
     * @param parameter Task parameters (unused)
     */
    static void wifiConnectionTask(void *parameter);
    
    // WiFi event handlers
    /**
     * @brief Handler for WiFi station connected events
     */
    static void WiFiStationConnected(WiFiEvent_t event, WiFiEventInfo_t info);
    
    /**
     * @brief Handler for WiFi got IP events
     */
    static void WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info);
    
    /**
     * @brief Handler for WiFi disconnected events
     */
    static void WiFiDisconnected(WiFiEvent_t event, WiFiEventInfo_t info);
    
    // Static state variables
    static Application* app;
    static TaskHandle_t wifiConnectionTaskHandle;
    static bool initialized;
    static unsigned long currentScanInterval;
    static unsigned long nextWifiScanTime;
};

#endif // WIFI_MANAGER_H
