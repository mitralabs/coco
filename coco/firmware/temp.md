```
// Audio recording task on Core 1 (away from system tasks)
xTaskCreatePinnedToCore(
    i2s_adc,
    "i2s_adc",
    1024 * 8,
    NULL,
    1,             // Higher than idle task priority
    NULL,
    1             // Application core
);

// WiFi task on Core 0 (with system network stack)
xTaskCreatePinnedToCore(
    wifiConnect,
    "wifi_Connect",
    4096,
    NULL,
    3,            // Higher priority for network stability
    NULL,
    0            // Protocol core
);
```

### Task Priority Guidelines
IDLE Task: Priority 0
Your Background Tasks: 1-3
Your Time-Critical Tasks: 4-5
System Critical Tasks: 18-24
Never use priority 25 (reserved for system tasks)

---

### Weiterer Plan:
1. Integrate DeepSleep
1. Fix LED Indication. To be solid on during recording.
2. Integrate Time Knowledge
    - Save Time Knowledge to RTC 
3. Integrate File Transfer, after saving data to SD. (see chatgpt code)
4. Integrate Power Logging ()
5. Integrate File Transfer on charging the device. Integrate Wake Up from Deep Sleep, e.g. every hour, to check, if connected to power source and connected to wifi to start file transfer.4. 