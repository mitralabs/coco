# Coco Firmware

## Setup
1. Install [PlatformIO VSCode Extension](https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide).
2. Open this `coco/firmware` directory in its own VSCode instance.
3. Copy `include/secrets.h.example` and rename it to `include/secrets.h`. Fill in all the values.
4. Plug in the Coco device via USB C.
5. Open the PlatformIO sidebar
    - Click on "Pick a Folder" and choose the `/firmware` folder as PlatformIO based project. This might close this VS Code Session and open a new one, with only the `/firmware`folder opened. So make sure to save all your file changes.
    - Click on `Upload and Monitor`. <br>-> Make sure to not open the Arduino IDE in parallel, since it might result in VS Code not being able to connect to the device. <br>(You can also manually `Build`, `Upload` and `Monitor` the ESP output.)


## Some Notes on the current blinking pattern (regarding v0.1)
- After you turn the device on, the LED will be off for 5s. If you switch of the device during this time period and turn it back on, it will go to "Transfer" Mode. Otherwise it will start recording.
- If you are in "Transfer" Mode, coco will try to send the saved .wav Files over the WiFi you configured (see Step 3 above), to a machine where the coco Backend is installed (which is also in your network).
- If coco blinks rapidly, this indicates an error.
	- If occurs directly after turning on, the most probable cause is a missing SD card, or one that is badly plugged in.
- During recording, the LED will be solid on. 

## ToDo
- [ ] Integrate Timezone into some .env file. E.g. secrets.h or so.
- [ ] Check if webrtc is available as c++ implementation to run on coco. [Link1](https://github.com/congjiye/vad), [Link2](https://chromium.googlesource.com/external/webrtc/+/branch-heads/43/webrtc/common_audio/vad/include/vad.h)

### Misc
- [Further Information](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)


---
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

## Next Steps:
5. Integrate File Transfer. Check if it's a blocking operation or not.
6. Überarbeite Setup and Init
7. Clean Up Task Frequency. Especially WiFi Connection and Time Grabbing.