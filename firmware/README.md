# Getting Started with the Sensor
**-> The "offline" versions send the audio files via Serial, and not via WiFi**

1. We used the Arduino IDE to upload Code to Coco (the ESP32 Sensor). Please have a look at the 'Software Preparation' Section on [this page](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/#software-preparation) from SeeedStudio. Once you completed steps 1 through 4. Please return here.

2. Now, within the Arduino IDE, you need to enable PSRAM. You can find this in Tools -> PSRAM -> "OPI PSRAM".

3. Now you are all good to go. These are the final steps:
- Open the latest .ino file from the [Firmware](/firmware)-Folder
- Select the "XIAO_ESP32S3" from the Dropdown
- Hit the Arrow in the top left, to compile the code and upload.

### Some Notes on the current blinking pattern (regarding v0.1)
- After you turn the device on, the LED will be on for 5s. If you switch of the device during this time period and turn it back on, it will go to "Transfer" Mode. Otherwise it will start recording.
- If you are in "Transfer" Mode. Shortly after turn on, the LED will be on for 3s to indicate connection to coco_base (the wifi).
- If Coco blinks rapidly, this indicates an error.
	- If occurs directly after turning on, the most probable cause is a missing SD card, or one that is badly plugged in.
    - Morse blinking to indicate Mic Setup Error.
- "Fizzy" Blinking indicates that the device is transferring.
- During recording, the LED will be solid on. 

- Once turned on, coco will blink shortly, after that the led will be off. once it goes back on, the recording starts.

# ToDo
- [ ] Move offline version and old versions to archive
- [ ] Check whether the CPU Clock has a notable effect on wifi transfer speed.
- [ ] 