/**
 * @file WifiManager.h
 * @brief WiFi connection management system for the Coco firmware
 * 
 * This module handles WiFi initialization, connection, scanning, and event handling.
 */

#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "config.h"
#include "Application.h"
#include "LogManager.h"

class WifiManager {
public:
    /**
     * Initialize the WiFi management system
     * @param app Reference to the Application singleton
     * @return True if initialization succeeded, false otherwise
     */
    static bool init(Application* app);
    
    /**
     * Start the WiFi connection task
     * @return True if task creation succeeded, false otherwise
     */
    static bool startConnectionTask();
    
    /**
     * Scan for available WiFi networks
     * @return Number of networks found, or -1 on error
     */
    static int scanNetworks();
    
    /**
     * Attempt to connect to the configured WiFi network
     * @return True if connection attempt initiated, false otherwise
     */
    static bool connect();
    
    /**
     * Disconnect from the current WiFi network
     * @return True if successfully disconnected, false otherwise
     */
    static bool disconnect();
    
    /**
     * Check if WiFi is currently connected
     * @return True if connected, false otherwise
     */
    static bool isConnected();
    
    /**
     * Get the current RSSI (signal strength)
     * @return RSSI value in dBm, or 0 if not connected
     */
    static int getRSSI();
    
    /**
     * Get the current local IP address
     * @return String representation of IP address
     */
    static String getLocalIP();

private:
    // Private constructor - singleton pattern
    WifiManager() {}
    
    // WiFi connection task function
    static void wifiConnectionTask(void *parameter);
    
    // WiFi event handlers
    static void WiFiStationConnected(WiFiEvent_t event, WiFiEventInfo_t info);
    static void WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info);
    static void WiFiDisconnected(WiFiEvent_t event, WiFiEventInfo_t info);
    
    // Static state variables
    static Application* app;
    static TaskHandle_t wifiConnectionTaskHandle;
    static bool initialized;
};

#endif // WIFI_MANAGER_H
