# README.md

# Coco Run Firmware

## Overview

Coco Run is a firmware project designed for efficient audio recording and saving operations using FreeRTOS. The firmware leverages task management and semaphores to ensure that audio recordings are handled smoothly without interruptions, allowing for continuous recording and saving processes.

## Project Structure

```
coco-run
├── src
│   ├── coco_run.ino          # Main entry point of the firmware
│   ├── audio
│   │   ├── recorder.h        # Header file for the Recorder class
│   │   └── recorder.cpp      # Implementation of the Recorder class
│   ├── storage
│   │   ├── storage.h         # Header file for the Storage class
│   │   └── storage.cpp       # Implementation of the Storage class
│   └── utils
│       ├── config.h          # Configuration constants and settings
│       └── logger.h          # Logging functions for debugging
├── lib
│   └── README.md             # Documentation for libraries used
├── include
│   └── README.md             # Documentation for additional include files
├── platformio.ini            # PlatformIO configuration file
└── README.md                 # Project documentation
```

## Features

- **Audio Recording**: The firmware supports audio recording using a dedicated `Recorder` class.
- **Non-blocking Operations**: Utilizes FreeRTOS tasks and semaphores to manage recording and saving without blocking.
- **Configurable Settings**: Configuration constants are defined in `config.h` for easy adjustments.
- **Logging**: Integrated logging functionality for monitoring and debugging.

## Setup Instructions

1. Clone the repository to your local machine.
2. Open the project in PlatformIO.
3. Connect your hardware device.
4. Build and upload the firmware to your device.

## Usage

Once the firmware is uploaded, it will automatically start recording audio. The recorded audio will be saved to the specified storage location without interrupting the recording process.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.