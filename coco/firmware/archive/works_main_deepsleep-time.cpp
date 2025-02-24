//works_main_deepsleep-time

#include <WiFi.h>
#include <time.h>
#include "esp_sleep.h"

RTC_DATA_ATTR time_t storedTime; // Stored UNIX timestamp
RTC_DATA_ATTR int bootCount = 0;
RTC_DATA_ATTR time_t sleep_enter_time; // Time when the device enters deep sleep

const char* ssid     = "";         // Replace with your network SSID
const char* password = "";   // Replace with your network password

#define LED_PIN          2           // LED connected to Pin 2 (on during awake period)
#define BUTTON_PIN       GPIO_NUM_3  // Button on GPIO1 (external pulldown)
#define AWAKE_PERIOD_MS  60000       // Device stays awake for 60s maximum
#define SLEEP_TIMEOUT_SEC 60        // Deep sleep period is 60s

void obtainTimeFromNTP() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  unsigned long startAttemptTime = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttemptTime < 20000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConnected to WiFi.");
    // Configure time: using UTC from NTP server and then applying timezone settings
    configTime(0, 0, "pool.ntp.org");
    setenv("TZ", "CET-1CEST,M3.5.0/2,M10.5.0/3", 1);
    tzset();
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
      storedTime = mktime(&timeinfo);
      Serial.printf("Current time obtained: %02d:%02d:%02d\n",
                    timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
    } else {
      Serial.println("Failed to obtain time");
    }
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
  } else {
    Serial.println("\nFailed to connect to WiFi.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000); // Allow time for Serial Monitor to start
  ++bootCount;

  // Retrieve the wakeup cause
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  // Print the wakeup reason for ESP32
  switch (wakeup_reason) {
    case ESP_SLEEP_WAKEUP_EXT0:     Serial.println("Wakeup caused by external signal using RTC_IO"); break;
    case ESP_SLEEP_WAKEUP_EXT1:     Serial.println("Wakeup caused by external signal using RTC_CNTL"); break;
    case ESP_SLEEP_WAKEUP_TIMER:    Serial.println("Wakeup caused by timer"); break;
    case ESP_SLEEP_WAKEUP_TOUCHPAD: Serial.println("Wakeup caused by touchpad"); break;
    case ESP_SLEEP_WAKEUP_ULP:      Serial.println("Wakeup caused by ULP program"); break;
    default:                        Serial.printf("Wakeup was not caused by deep sleep: %d\n", wakeup_reason); break;
  }

  if (wakeup_reason != ESP_SLEEP_WAKEUP_TIMER && wakeup_reason != ESP_SLEEP_WAKEUP_EXT0) {
    obtainTimeFromNTP();
  } else {
    Serial.printf("Woke up from deep sleep (boot #%d).\n", bootCount);
    struct tm* timeinfo = localtime(&storedTime);
    if (timeinfo) {
      Serial.printf("Recovered time from RTC memory: %02d:%02d:%02d\n",
                    timeinfo->tm_hour, timeinfo->tm_min, timeinfo->tm_sec);
    } else {
      Serial.println("Failed to recover time from RTC memory.");
    }
  }

  if (wakeup_reason != ESP_SLEEP_WAKEUP_UNDEFINED) {
    time_t now = time(NULL);
    int elapsed = difftime(now, sleep_enter_time);
    Serial.printf("Time spent in deep sleep: %d seconds\n", elapsed);
  }

  // Set up LED and button pins
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // LED is ON during awake mode
  // Enable internal pull-up on BUTTON_PIN for EXT0
  pinMode(BUTTON_PIN, INPUT_PULLUP);  

  Serial.println("Device is awake. Press the button (GPIO0) to sleep early.");

  // Awake period loop: remain active for 60 seconds or exit early if button is pressed.
  // Active low means button press is detected when digitalRead returns LOW.
  unsigned long awakeStart = millis();
  while (millis() - awakeStart < AWAKE_PERIOD_MS) {
    if (digitalRead(BUTTON_PIN) == LOW) {
      Serial.println("Button pressed during awake period. Going to sleep early.");
      break;
    }
    delay(100);
  }

  // Turn off LED before sleep
  digitalWrite(LED_PIN, LOW);

  // Prepare wakeup sources:
  // Use EXT0 wakeup on BUTTON_PIN: trigger when the pin reads LOW.
  esp_sleep_enable_ext0_wakeup(static_cast<gpio_num_t>(BUTTON_PIN), 0);
  // Timer wakeup after SLEEP_TIMEOUT_SEC seconds
  esp_sleep_enable_timer_wakeup(SLEEP_TIMEOUT_SEC * 1000000ULL);

  // Store the current time before entering deep sleep
  sleep_enter_time = time(NULL);

  Serial.println("Entering deep sleep now.");
  delay(1000);
  Serial.flush();
  esp_deep_sleep_start();
}

void loop() {
  // Empty loop as deep sleep is used
}