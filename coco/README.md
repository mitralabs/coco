# Getting Started with the Sensor

1. We used the Arduino IDE to upload Code to coco (the ESP32 Sensor). Please have a look at the 'Software Preparation' Section on [this page](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/#software-preparation) from SeeedStudio. Once you completed steps 1 through 4. Please return here.

2. Now, within the Arduino IDE, you need to enable PSRAM. You can find this in Tools -> PSRAM -> "OPI PSRAM".

3. Now you are all good to go. These are the final steps:
- Open the latest .ino file from the coco_run_* Folder.
- Exchange the default WiFi Settings, for your own. Look for the latter in the code:
```
const char *ssid = "coco_connect";
const char *password = "please_smile";
``` 
- Select the "XIAO_ESP32S3" from the Dropdown (within the Arduino IDE)
- Hit the Arrow in the top left, to compile the code and upload.

### Some Notes on the current blinking pattern (regarding v0.1)
- After you turn the device on, the LED will be off for 5s. If you switch of the device during this time period and turn it back on, it will go to "Transfer" Mode. Otherwise it will start recording.
- If you are in "Transfer" Mode, coco will try to send the saved .wav Files over the WiFi you configured (see Step 3 above), to a machine where the coco Backend is installed (which is also in your network).
- If coco blinks rapidly, this indicates an error.
	- If occurs directly after turning on, the most probable cause is a missing SD card, or one that is badly plugged in.
- During recording, the LED will be solid on. 

# ToDo
- [ ] Include a "How to Build" the Thing Tutorial or YouTube Video.
- [ ] Check whether the CPU Clock has a notable effect on wifi transfer speed.