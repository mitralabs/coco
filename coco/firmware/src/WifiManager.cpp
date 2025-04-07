/**
 * @file WifiManager.cpp
 * @brief Implementation of the WifiManager class
 * 
 * This file contains the implementation of WiFi connection management functionality
 * including scanning, connection handling, and automatic reconnection with
 * exponential backoff.
 */

#include "WifiManager.h"

// Initialize static members
Application* WifiManager::app = nullptr;
TaskHandle_t WifiManager::wifiConnectionTaskHandle = nullptr;
bool WifiManager::initialized = false;
unsigned long WifiManager::currentScanInterval = MIN_SCAN_INTERVAL;
unsigned long WifiManager::nextWifiScanTime = 0;

// Getter and setter implementations for state properties
unsigned long WifiManager::getCurrentScanInterval() {
    return currentScanInterval;
}

void WifiManager::setCurrentScanInterval(unsigned long interval) {
    currentScanInterval = interval;
}

unsigned long WifiManager::getNextWifiScanTime() {
    return nextWifiScanTime;
}

void WifiManager::setNextWifiScanTime(unsigned long time) {
    nextWifiScanTime = time;
}

bool WifiManager::init(Application* application) {
    // Store application instance
    app = application;
    
    if (!app) {
        return false;
    }
    
    // Initialize WiFi in station mode
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(false);  // We'll handle reconnection ourselves
    
    // Register event handlers
    WiFi.onEvent(WiFiStationConnected, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_CONNECTED);
    WiFi.onEvent(WiFiGotIP, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_GOT_IP);
    WiFi.onEvent(WiFiDisconnected, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
    
    // Initialize scan interval and time
    currentScanInterval = MIN_SCAN_INTERVAL;
    nextWifiScanTime = millis();
    
    app->log("WifiManager initialized");
    initialized = true;
    return true;
}

bool WifiManager::startConnectionTask() {
    if (!initialized || !app) {
        if (app) app->log("WifiManager not initialized!");
        return false;
    }
    
    // Start WiFi connection task
    if (xTaskCreatePinnedToCore(
        wifiConnectionTask,
        "WiFi Connection",
        4096,
        nullptr,
        1,
        &wifiConnectionTaskHandle,
        0  // Run on Core 0
    ) != pdPASS) {
        app->log("Failed to create WiFi connection task!");
        return false;
    }
    
    return true;
}

int WifiManager::scanNetworks() {
    if (app) app->log("Scanning for WiFi networks...");
    return WiFi.scanNetworks();
}

bool WifiManager::connect() {
    if (!initialized) {
        if (app) app->log("WifiManager not initialized!");
        return false;
    }
    
    app->log("Attempting to connect to: " + String(SS_ID));
    WiFi.begin(SS_ID, PASSWORD);
    WiFi.setTxPower(WIFI_POWER_8_5dBm); // Highest: WIFI_POWER_19_5dBm, Lowest: WIFI_POWER_2dBm (logarithmic)
    return true;
}

bool WifiManager::disconnect() {
    return WiFi.disconnect();
}

bool WifiManager::isConnected() {
    return WiFi.status() == WL_CONNECTED;
}

int WifiManager::getRSSI() {
    return isConnected() ? WiFi.RSSI() : 0;
}

String WifiManager::getLocalIP() {
    return WiFi.localIP().toString();
}

void WifiManager::wifiConnectionTask(void *parameter) {
    if (!initialized || !app) {
        if (app) app->log("WifiManager not properly initialized for connection task!");
        vTaskDelete(nullptr);
        return;
    }

    // Connection state tracking variables
    bool connectionInProgress = false;
    unsigned long connectionStartTime = 0;
    const unsigned long CONNECTION_TIMEOUT = 15000; // 15 seconds timeout for connection attempts

    while (true) {
        unsigned long currentTime = millis();
        
        // Handle active connection attempts
        if (connectionInProgress) {
            // If we've successfully connected
            if (app->isWifiConnected()) {
                app->log("Connection attempt succeeded");
                connectionInProgress = false;
                setCurrentScanInterval(MIN_SCAN_INTERVAL);
            } 
            // If connection attempt has timed out
            else if (currentTime - connectionStartTime > CONNECTION_TIMEOUT) {
                app->log("WiFi connection attempt timed out after " + 
                               String(CONNECTION_TIMEOUT/1000) + " seconds");
                connectionInProgress = false;
                // Schedule next scan with backoff
                unsigned long newInterval = std::min(getCurrentScanInterval() * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
                setCurrentScanInterval(newInterval);
                setNextWifiScanTime(currentTime + newInterval);
                app->log("Next scan in " + String(newInterval / 1000) + " seconds");
            } 
            // Still waiting for connection
            else {
                // Wait and continue the loop without scanning
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
        }
        
        // Only scan if not connected, not in connection progress, and it's time to scan
        if (!app->isWifiConnected() && !connectionInProgress && currentTime >= getNextWifiScanTime()) {
            app->log("Scanning for WiFi networks...");
            
            // Start network scan
            int networksFound = scanNetworks();
            bool ssidFound = false;
            
            if (networksFound > 0) {
                app->log("Found " + String(networksFound) + " networks");
                
                // Check if our SSID is in the list
                for (int i = 0; i < networksFound; i++) {
                    String scannedSSID = WiFi.SSID(i);
                    if (scannedSSID == String(SS_ID)) {
                        ssidFound = true;
                        app->log("Target network '" + String(SS_ID) + "' found with signal strength: " + 
                            String(WiFi.RSSI(i)) + " dBm");
                        break;
                    }
                }
                WiFi.scanDelete(); // Clean up scan results
                
                // If our SSID was found, try to connect
                if (ssidFound) {
                    connect();
                    // Mark connection as in progress and record start time
                    connectionInProgress = true;
                    connectionStartTime = currentTime;
                    app->log("Connection attempt started, waiting up to " + 
                                   String(CONNECTION_TIMEOUT/1000) + " seconds...");
                } else {
                    app->log("Target network not found in scan");
                    
                    // Apply exponential backoff for next scan
                    unsigned long newInterval = std::min(getCurrentScanInterval() * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
                    setCurrentScanInterval(newInterval);
                    setNextWifiScanTime(currentTime + newInterval);
                    app->log("Next scan in " + String(newInterval / 1000) + " seconds");
                }
            } else {
                app->log("No networks found");
                // Apply exponential backoff for next scan
                unsigned long newInterval = std::min(getCurrentScanInterval() * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
                setCurrentScanInterval(newInterval);
                setNextWifiScanTime(currentTime + newInterval);
                app->log("Next scan in " + String(newInterval / 1000) + " seconds");
            }
        }
        
        // If connected, reset backoff parameters
        if (app->isWifiConnected() && !connectionInProgress) {
            setCurrentScanInterval(MIN_SCAN_INTERVAL);
        }
        
        vTaskDelay(pdMS_TO_TICKS(1000)); // Check again after a delay
    }
}

void WifiManager::deleteConnectionTask() {
    if (wifiConnectionTaskHandle != nullptr) {
        TaskHandle_t tempHandle = wifiConnectionTaskHandle;
        wifiConnectionTaskHandle = nullptr;
        vTaskDelete(tempHandle);
        if (app) app->log("WiFi connection task deleted");
    }
}

void WifiManager::WiFiStationConnected(WiFiEvent_t event, WiFiEventInfo_t info) {
    if (app) app->log("Connected to WiFi access point");
}

void WifiManager::WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info) {
    if (!app) return;
    
    app->log("WiFi connected with IP: " + WiFi.localIP().toString());
    setCurrentScanInterval(MIN_SCAN_INTERVAL);
    app->setWifiConnected(true);
    
    // Delete the WiFi connection task since we're now connected
    deleteConnectionTask();
    
    // Update time as soon as we get an IP address using Application wrapper
    if (app->updateFromNTP()) {
        app->log("Time synchronized with NTP successfully");
    } else {
        // Schedule a retry in 30 seconds
        if(xTaskCreatePinnedToCore(
            [](void* parameter) {
                vTaskDelay(pdMS_TO_TICKS(30000)); // 30 seconds delay
                app->updateFromNTP();
                vTaskDelete(NULL);
            },
            "NTPRetry", 4096, NULL, 1, NULL, 0
        ) != pdPASS) {
            app->log("Failed to create NTP retry task");
        }
    }
    
    // Start backend reachability task now that we have a connection
    if (app->startBackendReachabilityTask()) {
        app->log("Backend reachability task started after WiFi connection");
    } else {
        app->log("Failed to start backend reachability task after WiFi connection");
    }
}

void WifiManager::WiFiDisconnected(WiFiEvent_t event, WiFiEventInfo_t info) {
    if (!app) return;
    
    app->log("Disconnected from WiFi access point");
    app->setWifiConnected(false);
    
    // Stop the backend reachability task since we lost WiFi
    if (app->stopBackendReachabilityTask()) {
        app->log("Backend reachability task stopped due to WiFi disconnection");
    }
    
    // Stop the file upload task if it's running
    if (app->stopFileUploadTask()) {
        app->log("File upload task stopped due to WiFi disconnection");
    }
    
    // Reset scan interval to minimum when disconnected to attempt reconnection faster
    setCurrentScanInterval(MIN_SCAN_INTERVAL);
    setNextWifiScanTime(millis() + MIN_SCAN_INTERVAL);
    
    // Restart the WiFi connection task to handle reconnection
    if (wifiConnectionTaskHandle == nullptr) {
        app->log("Restarting WiFi connection task");
        startConnectionTask();
    }
}
