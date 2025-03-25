/**
 * @file FileSystem.cpp
 * @brief Implementation of file system management module
 */

#include "FileSystem.h"
#include "LogManager.h"

// Initialize static member
FileSystem* FileSystem::_instance = nullptr;

// Private helper class for RAII mutex handling
class SDLockGuard {
private:
    SemaphoreHandle_t& _mutex;
    bool _locked;
public:
    SDLockGuard(SemaphoreHandle_t& mutex) : _mutex(mutex), _locked(false) {
        _locked = (xSemaphoreTake(_mutex, pdMS_TO_TICKS(5000)) == pdTRUE);
    }
    ~SDLockGuard() {
        if (_locked) xSemaphoreGive(_mutex);
    }
    bool isLocked() const { return _locked; }
};

FileSystem* FileSystem::getInstance() {
    if (_instance == nullptr) {
        _instance = new FileSystem();
    }
    return _instance;
}

FileSystem::FileSystem() : _initialized(false), _sdMutex(nullptr) {
    // Initialize mutex
    _sdMutex = xSemaphoreCreateMutex();
    if (_sdMutex == nullptr) {
        Serial.println("ERROR: Failed to create SD card mutex");
    }
}

bool FileSystem::init() {
    if (_initialized) {
        return true;
    }

    if (_sdMutex == nullptr) {
        Serial.println("ERROR: SD card mutex is not initialized");
        return false;
    }

    SDLockGuard lock(_sdMutex);
    if (!lock.isLocked()) {
        Serial.println("ERROR: Failed to take SD card mutex during initialization");
        return false;
    }

    // Initialize SD card with retry mechanism
    const int maxRetries = 3;
    int retryCount = 0;
    bool sdInitialized = false;
    
    while (!sdInitialized && retryCount < maxRetries) {
        // Attempt to initialize the SD card
        Serial.printf("Initializing SD card (attempt %d of %d)...\n", retryCount + 1, maxRetries);
        
        // Try initializing with different speeds if we're retrying
        uint32_t sdSpeed = (retryCount == 0) ? SD_SPEED : (SD_SPEED / (retryCount + 1));
        
        if (SD.begin(21, SPI, sdSpeed)) {
            sdInitialized = true;
        } else {
            Serial.println("SD Card initialization failed, retrying...");
            retryCount++;
            // Short delay before retry
            delay(500);
        }
    }
    
    if (!sdInitialized) {
        Serial.println("ERROR: SD Card initialization failed after multiple attempts!");
        return false;
    }

    uint8_t cardType = SD.cardType();
    if (cardType == CARD_NONE) {
        Serial.println("ERROR: No SD card attached");
        return false;
    }

    Serial.print("SD Card Type: ");
    if (cardType == CARD_MMC) {
        Serial.println("MMC");
    } else if (cardType == CARD_SD) {
        Serial.println("SDSC");
    } else if (cardType == CARD_SDHC) {
        Serial.println("SDHC");
    } else {
        Serial.println("UNKNOWN");
    }

    uint64_t cardSize = SD.cardSize() / (1024 * 1024);
    Serial.printf("SD Card Size: %lluMB\n", cardSize);

    _initialized = true;
    return true;
}

bool FileSystem::ensureDirectory(const char* path) {
    SDLockGuard lock(_sdMutex);
    if (!lock.isLocked()) {
        Serial.printf("ERROR: Failed to take SD card mutex for directory creation: %s\n", path);
        return false;
    }

    bool result = true;
    if (!SD.exists(path)) {
        result = SD.mkdir(path);
        if (result) {
            Serial.printf("Created directory: %s\n", path);
        } else {
            Serial.printf("ERROR: Failed to create directory: %s\n", path);
        }
    }

    return result;
}

bool FileSystem::addToFile(const String& path, const String& content, bool isUploadQueue) {
    if (!_initialized) {
        Serial.println("ERROR: FileSystem not initialized");
        return false;
    }

    // Ensure parent directory exists
    int lastSlash = path.lastIndexOf('/');
    if (lastSlash > 0) {
        String dirPath = path.substring(0, lastSlash);
        if (!ensureDirectory(dirPath.c_str())) {
            LogManager::log("ERROR: Failed to create parent directory for " + path);
            return false;
        }
    }

    SDLockGuard lock(_sdMutex);
    if (!lock.isLocked()) {
        LogManager::log("ERROR: Failed to take SD card mutex for file append operation");
        return false;
    }

    File file = SD.open(path, FILE_APPEND);
    if (!file) {
        LogManager::log("ERROR: Failed to open file for appending: " + path);
        return false;
    }

    size_t bytesWritten = file.print(content);
    file.close();

    if (bytesWritten != content.length()) {
        LogManager::log("ERROR: Failed to write all data to file: " + path);
        return false;
    }

    if (isUploadQueue) {
        LogManager::log("Added to upload queue: " + content.substring(0, content.length() - 1)); // Remove newline
    }

    return true;
}

bool FileSystem::overwriteFile(const String& path, const String& content) {
    if (!_initialized) {
        Serial.println("ERROR: FileSystem not initialized");
        return false;
    }

    // Ensure parent directory exists
    int lastSlash = path.lastIndexOf('/');
    if (lastSlash > 0) {
        String dirPath = path.substring(0, lastSlash);
        if (!ensureDirectory(dirPath.c_str())) {
            LogManager::log("ERROR: Failed to create parent directory for " + path);
            return false;
        }
    }

    SDLockGuard lock(_sdMutex);
    if (!lock.isLocked()) {
        LogManager::log("ERROR: Failed to take SD card mutex for file write operation");
        return false;
    }

    File file = SD.open(path, FILE_WRITE);
    if (!file) {
        LogManager::log("ERROR: Failed to open file for writing: " + path);
        return false;
    }

    size_t bytesWritten = file.print(content);
    file.close();

    if (bytesWritten != content.length()) {
        LogManager::log("ERROR: Failed to write all data to file: " + path);
        return false;
    }

    return true;
}

String FileSystem::readFile(const String& path) {
    String content = "";
    
    if (!_initialized) {
        Serial.println("ERROR: FileSystem not initialized");
        return content;
    }

    SDLockGuard lock(_sdMutex);
    if (!lock.isLocked()) {
        LogManager::log("ERROR: Failed to take SD card mutex for file read operation");
        return content;
    }

    if (!SD.exists(path)) {
        return content; // Return empty string if file doesn't exist
    }

    File file = SD.open(path, FILE_READ);
    if (!file) {
        LogManager::log("ERROR: Failed to open file for reading: " + path);
        return content;
    }

    content = file.readString();
    file.close();
    
    return content;
}

bool FileSystem::deleteFile(const String& path) {
    if (!_initialized) {
        Serial.println("ERROR: FileSystem not initialized");
        return false;
    }

    SDLockGuard lock(_sdMutex);
    if (!lock.isLocked()) {
        LogManager::log("ERROR: Failed to take SD card mutex for file delete operation");
        return false;
    }

    if (!SD.exists(path)) {
        return true; // File doesn't exist, consider it "successfully deleted"
    }

    if (!SD.remove(path)) {
        LogManager::log("ERROR: Failed to delete file: " + path);
        return false;
    }

    return true;
}

bool FileSystem::addToUploadQueue(const String &filename) {
    // Basic validation
    if (filename.length() == 0) {
        LogManager::log("ERROR: Cannot add empty filename to upload queue");
        return false;
    }

    // Use the existing method to check for duplicates
    // if (isFileInUploadQueue(filename)) {
    //     LogManager::log("File already in upload queue: " + filename);
    //     return true; // Not an error, file is already queued
    // }
    
    // Add to queue using addToFile method
    return addToFile(UPLOAD_QUEUE_FILE, filename + "\n", true);
}

String FileSystem::getNextUploadFile() {
    String content = readFile(UPLOAD_QUEUE_FILE);
    if (content.isEmpty()) {
        return "";
    }
    
    // Extract first line
    int newlinePos = content.indexOf('\n');
    if (newlinePos == -1) {
        return content; // No newline, return entire content
    }
    
    return content.substring(0, newlinePos);
}

bool FileSystem::removeFirstFromUploadQueue() {
    String content = readFile(UPLOAD_QUEUE_FILE);
    if (content.isEmpty()) {
        LogManager::log("ERROR: Cannot remove from empty upload queue");
        return false;
    }
    
    // Find first newline
    int newlinePos = content.indexOf('\n');
    if (newlinePos == -1) {
        // No newline, queue has just one entry
        return deleteFile(UPLOAD_QUEUE_FILE);
    }
    
    // Get the file that will be removed for logging
    String removedFile = content.substring(0, newlinePos);
    
    // Extract remaining content (skip the newline)
    String remaining = content.substring(newlinePos + 1);
    
    // Overwrite the file with remaining content
    bool success = overwriteFile(UPLOAD_QUEUE_FILE, remaining);
    
    if (success) {
        LogManager::log("Removed from upload queue: " + removedFile);
    }
    
    return success;
}

bool FileSystem::isUploadQueueEmpty() {
    String content = readFile(UPLOAD_QUEUE_FILE);
    return content.isEmpty();
}

bool FileSystem::isFileInUploadQueue(const String &filename) {
    String content = readFile(UPLOAD_QUEUE_FILE);
    if (content.isEmpty()) {
        return false;
    }
    
    int pos = 0;
    while (pos < content.length()) {
        int newlinePos = content.indexOf('\n', pos);
        
        // If no more newlines, check the rest of the string
        if (newlinePos == -1) {
            String line = content.substring(pos);
            return (line == filename);
        }
        
        // Check the current line
        String line = content.substring(pos, newlinePos);
        if (line == filename) {
            return true;
        }
        
        // Move to next line
        pos = newlinePos + 1;
    }
    
    return false;
}