#ifndef STORAGE_H
#define STORAGE_H

#include <Arduino.h>

class Storage {
public:
    Storage();
    void init();
    void saveAudioData(const uint8_t* data, size_t size);
};

#endif // STORAGE_H