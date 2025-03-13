# Coco Firmware

## Setup
1. Install [PlatformIO VSCode Extension](https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide).
2. Open this `coco/firmware` directory in its own VSCode instance.
3. Copy `include/secrets.h.example` and rename it to `include/secrets.h`. Fill in all the values.
4. Plug in the Coco device via USB C.
5. Open the PlatformIO sidebar
    - Click on "Pick a Folder" and choose the `/firmware` folder as PlatformIO based project. This might close this VS Code Session and open a new one, with only the `/firmware`folder opened. So make sure to save all your file changes.
    - Click on `Upload and Monitor`. <br>-> Make sure to not open the Arduino IDE in parallel, since it might result in VS Code not being able to connect to the device. <br>(You can also manually `Build`, `Upload` and `Monitor` the ESP output.)


## Some Notes on the current blinking pattern (regarding v1.0)
- If coco blinks rapidly, this indicates an error.
	- If occurs directly after turning on, the most probable cause is a missing SD card, or one that is badly plugged in.
- During recording, the LED will be solid on.

### Task Priority Guidelines
IDLE Task: Priority 0
Your Background Tasks: 1-3
Your Time-Critical Tasks: 4-5
System Critical Tasks: 18-24
Never use priority 25 (reserved for system tasks)

## ToDo
- [ ] Solve Device shutdown on FileUpload. Currently the device sometimes crashes when it tries to send the file...
- [ ] Überarbeite Setup and Init (maybe find a routine for initial boot or boot from complete power loss). Consider removing the "if task creation fails" parts.
- [ ] Check if there is a possibility that audio queue get's lost on the SD card. E.g. when the new one is being written and the device loses power.
- [ ] Integrate Routine which brings device to deepsleep, when Voltage below a certain threshold.
- [ ] Find a handle for SD Card Error to reset device utilizing the button. Factory Reset Button will mostlikely not be reachable, since inside of case.
- [ ] Rewrite logging. It's currently pretty wild.
- [ ] Include WiFiMulti, so that multiple Networks are known.
- [ ] Integrate WiFi, and Timezone on SD Card (although this poses security risks, if device is lost, and card inspected.)
- [ ] Look into File Compression like LZ77H (common in HTTP headers)


---

### Misc
- [Further Information](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)