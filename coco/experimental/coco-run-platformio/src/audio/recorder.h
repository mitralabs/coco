#ifndef RECORDER_H
#define RECORDER_H

#include <Arduino.h>
#include <semphr.h>

class Recorder {
public:
    Recorder();
    void startRecording();
    void stopRecording();
    
private:
    void recordAudio();
    SemaphoreHandle_t xSemaphore;
};

#endif // RECORDER_H