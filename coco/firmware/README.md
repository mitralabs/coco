# Coco Firmware

## Setup
1. Install [PlatformIO VSCode Extension](https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide).
2. Open this `coco/firmware` directory in its own VSCode instance.
3. Copy `include/secrets.h.example` and rename it to `include/secrets.h`. Fill in all the values.
4. Plug in the Coco device via USB C.
5. Open the PlatformIO sidebar
    - Click on "Pick a Folder" and choose the `/firmware` folder as PlatformIO based project. This might close this VS Code Session and open a new one, with only the `/firmware`folder opened. So make sure to save all your file changes.
    - Click on `Upload and Monitor`. <br>-> Make sure to not open the Arduino IDE in parallel, since it might result in VS Code not being able to connect to the device. <br>(You can also manually `Build`, `Upload` and `Monitor` the ESP output.)


## Some Notes on the Firmware and the LED
When Coco is not running, it is in Deepsleep. The button can be used to wake the device from deepsleep. It needs to be pressed and hold until the LED either goes on, or goes off. When the device was off (LED is off) it starts with a short blinking pattern, which either indicates the Battery Status, or an Error state. The latter is indicated through a rapid blinking pattern which runs for ~30s, afterwards the device goes back to deepsleep. If there is no error, the device will blink 1 to 4 times, and then stay on. The blinks indicate the battery level. 1 blink is equivalent to 25% charge. The device will record and upload data on it's own. While on, the LED will slowly fade, according to the battery state.

*Note: The batterylifetime is bad at the moment. It's a serious area for improvement. I'd guess that task management is the place to start.*
*Note 2: The knowledge of embedded systems design + c++ are sub optimal within our team. So don't panic when you see the code.*

## ToDo
- [ ] Reintegrate learnings from testing.

### Links
- [Further Information on the ESP32S3](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)