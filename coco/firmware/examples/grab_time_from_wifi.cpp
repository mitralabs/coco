#include <WiFi.h>
#include <time.h>

const char* ssid     = "TLM";     // Replace with your network SSID
const char* password = "123456789"; // Replace with your network password

bool isConnected = false;  // Track connection status

void setup() {
  Serial.begin(115200);

  // Configure time settings
  configTime(0, 0, "pool.ntp.org");  // Use NTP server to get UTC time
  setenv("TZ", "CET-1CEST,M3.5.0/2,M10.5.0/3", 1);  // Set timezone for Central European Time
  tzset();
}

void loop() {
  Serial.println("WiFi Status:");
  Serial.println(WiFi.status());
  Serial.println("WiFi Status End");

  if (WiFi.status() != WL_CONNECTED) {
    if (isConnected) {
      Serial.println("WiFi disconnected. Trying to reconnect...");
      isConnected = false;
    }
    WiFi.begin(ssid, password);

    // Wait a short time for the connection attempt
    unsigned long startAttemptTime = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttemptTime < 5000) {
      delay(500);
      Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\nConnected to WiFi");
      isConnected = true;
    }
  }

  if (isConnected) {
    struct tm timeinfo;
    if (!getLocalTime(&timeinfo)) {
      Serial.println("Failed to obtain time");
    } else {
      Serial.printf("Current time: %02d:%02d:%02d\n", timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
    }
  } else {
    Serial.println("No WiFi connection");
  }
  
  delay(1000);  // Check every second
}

