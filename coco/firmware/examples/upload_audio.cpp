#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>

#include "secrets.h"  // The API endpoint and WIFI Credentials are stored here

HTTPClient http;

void transferFile() {
  bool transferSuccess = false;

  while (!transferSuccess) {
    log("Transferring file: " + String(curr_file.name()));

    HTTPClient client;

    // Add timeout settings
    client.setTimeout(10000);  // 10 seconds timeout

    // Check WiFi status before trying
    if (WiFi.status() != WL_CONNECTED) {
      log("WiFi disconnected. Attempting to reconnect...");
      WiFi.reconnect();
      delay(3000);
    }

    client.begin(API_ENDPOINT);
    client.addHeader("Content-Type", "audio/wav");
    client.addHeader("X-API-Key",
                     API_KEY);  // Add the API key as a custom header
    client.addHeader("Content-Disposition",
                     "form-data; name=\"file\"; filename=\"" +
                         String(curr_file.name()) + "\"");

    int httpResponseCode =
        client.sendRequest("POST", &curr_file, curr_file.size());

    log("HTTP Response Code: " + String(httpResponseCode));

    // Debug response details
    if (httpResponseCode > 0) {
      if (httpResponseCode == 200) {
        String response = client.getString();
        log("Response body: " + response);

        // Success - delete file
        if (SD.remove((String(RECORDINGS_DIR) + "/" + String(curr_file.name()))
                          .c_str())) {
          log("File processed and deleted successfully: " +
              String(curr_file.name()));
        } else {
          log("Error: File could not be deleted. SD card error: " +
              String(SD.cardType()));
        }
        curr_file.close();
        transferSuccess = true;
      } else {
        // Get error response body
        String errorResponse = client.getString();
        log("Error response body: " + errorResponse);
        delay(BASE_DELAY);
      }
    } else {
      log("Failed to connect to server. Error: " +
          String(client.errorToString(httpResponseCode)));
    }

    client.end();
  }
}
