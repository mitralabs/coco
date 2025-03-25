/**
 * @file WifiManager.cpp
 * @brief Implementation of the WifiManager class
 */

#include "WifiManager.h"
#include "TimeManager.h" // For NTP time updates when connected
#include "secrets.h"

// Initialize static members
Application* WifiManager::app = NULL;
TaskHandle_t WifiManager::wifiConnectionTaskHandle = NULL;
bool WifiManager::initialized = false;

bool WifiManager::init(Application* application) {
    // Store application instance
    app = application;
    
    // Initialize WiFi in station mode
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(false);  // We'll handle reconnection ourselves
    
    // Register event handlers
    WiFi.onEvent(WiFiStationConnected, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_CONNECTED);
    WiFi.onEvent(WiFiGotIP, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_GOT_IP);
    WiFi.onEvent(WiFiDisconnected, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
    
    LogManager::log("WifiManager initialized");
    initialized = true;
    return true;
}

bool WifiManager::startConnectionTask() {
    if (!initialized || !app) {
        LogManager::log("WifiManager not initialized!");
        return false;
    }
    
    // Start WiFi connection task
    if (xTaskCreatePinnedToCore(
        wifiConnectionTask,
        "WiFi Connection",
        4096,
        NULL,
        1,
        &wifiConnectionTaskHandle,
        0  // Run on Core 0
    ) != pdPASS) {
        LogManager::log("Failed to create WiFi connection task!");
        return false;
    }
    
    app->setWifiConnectionTaskHandle(wifiConnectionTaskHandle);
    return true;
}

int WifiManager::scanNetworks() {
    LogManager::log("Scanning for WiFi networks...");
    return WiFi.scanNetworks();
}

bool WifiManager::connect() {
    if (!initialized) {
        LogManager::log("WifiManager not initialized!");
        return false;
    }
    
    LogManager::log("Attempting to connect to: " + String(SS_ID));
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
        LogManager::log("WifiManager not properly initialized for connection task!");
        vTaskDelete(NULL);
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
                LogManager::log("Connection attempt succeeded");
                connectionInProgress = false;
                app->setCurrentScanInterval(MIN_SCAN_INTERVAL);
            } 
            // If connection attempt has timed out
            else if (currentTime - connectionStartTime > CONNECTION_TIMEOUT) {
                LogManager::log("WiFi connection attempt timed out after " + 
                               String(CONNECTION_TIMEOUT/1000) + " seconds");
                connectionInProgress = false;
                // Schedule next scan with backoff
                unsigned long currentInterval = app->getCurrentScanInterval();
                unsigned long newInterval = std::min(currentInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
                app->setCurrentScanInterval(newInterval);
                app->setNextWifiScanTime(currentTime + newInterval);
                LogManager::log("Next scan in " + String(newInterval / 1000) + " seconds");
            } 
            // Still waiting for connection
            else {
                // Wait and continue the loop without scanning
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
        }
        
        // Only scan if not connected, not in connection progress, and it's time to scan
        if (!app->isWifiConnected() && !connectionInProgress && currentTime >= app->getNextWifiScanTime()) {
            LogManager::log("Scanning for WiFi networks...");
            
            // Start network scan
            int networksFound = scanNetworks();
            bool ssidFound = false;
            
            if (networksFound > 0) {
                LogManager::log("Found " + String(networksFound) + " networks");
                
                // Check if our SSID is in the list
                for (int i = 0; i < networksFound; i++) {
                    String scannedSSID = WiFi.SSID(i);
                    if (scannedSSID == String(SS_ID)) {
                        ssidFound = true;
                        LogManager::log("Target network '" + String(SS_ID) + "' found with signal strength: " + 
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
                    LogManager::log("Connection attempt started, waiting up to " + 
                                   String(CONNECTION_TIMEOUT/1000) + " seconds...");
                } else {
                    LogManager::log("Target network not found in scan");
                    
                    // Apply exponential backoff for next scan
                    unsigned long currentInterval = app->getCurrentScanInterval();
                    unsigned long newInterval = std::min(currentInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
                    app->setCurrentScanInterval(newInterval);
                    app->setNextWifiScanTime(currentTime + newInterval);
                    LogManager::log("Next scan in " + String(newInterval / 1000) + " seconds");
                }
            } else {
                LogManager::log("No networks found");
                // Apply exponential backoff for next scan
                unsigned long currentInterval = app->getCurrentScanInterval();
                unsigned long newInterval = std::min(currentInterval * 2UL, (unsigned long)MAX_SCAN_INTERVAL);
                app->setCurrentScanInterval(newInterval);
                app->setNextWifiScanTime(currentTime + newInterval);
                LogManager::log("Next scan in " + String(newInterval / 1000) + " seconds");
            }
        }
        
        // If connected, reset backoff parameters
        if (app->isWifiConnected() && !connectionInProgress) {
            app->setCurrentScanInterval(MIN_SCAN_INTERVAL);
        }
        
        vTaskDelay(pdMS_TO_TICKS(1000)); // Check again after a delay
    }
}

void WifiManager::WiFiStationConnected(WiFiEvent_t event, WiFiEventInfo_t info) {
    LogManager::log("Connected to WiFi access point");
}

void WifiManager::WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info) {
    LogManager::log("WiFi connected with IP: " + WiFi.localIP().toString());
    app->setCurrentScanInterval(MIN_SCAN_INTERVAL);
    app->setWifiConnected(true);
    
    // Update time as soon as we get an IP address using TimeManager
    if (TimeManager::updateFromNTP()) {
        LogManager::log("Time synchronized with NTP successfully");
    } else {
        // Schedule a retry in 30 seconds
        if(xTaskCreatePinnedToCore(
            [](void* parameter) {
                vTaskDelay(pdMS_TO_TICKS(30000)); // 30 seconds delay
                TimeManager::updateFromNTP();
                vTaskDelete(NULL);
            },
            "NTPRetry", 4096, NULL, 1, NULL, 0
        ) != pdPASS) {
            LogManager::log("Failed to create NTP retry task");
        }
    }
}

void WifiManager::WiFiDisconnected(WiFiEvent_t event, WiFiEventInfo_t info) {
    LogManager::log("Disconnected from WiFi access point");
    app->setWifiConnected(false);
    
    // Reset scan interval to minimum when disconnected to attempt reconnection faster
    app->setCurrentScanInterval(MIN_SCAN_INTERVAL);
    app->setNextWifiScanTime(millis() + MIN_SCAN_INTERVAL);
}
