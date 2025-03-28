/**
 * @file FileSystem.cpp
 * @brief Implementation of file system management module
 * 
 * Handles SD card operations, file manipulations, and upload queue management.
 */

#include "FileSystem.h"

// Initialize static variables
bool FileSystem::initialized = false;
SemaphoreHandle_t FileSystem::sdMutex = nullptr;
Application* FileSystem::app = nullptr;

// Private helper class for RAII mutex handling
class SDLockGuard {
private:
    SemaphoreHandle_t& mutex;
    bool locked;
public:
    SDLockGuard(SemaphoreHandle_t& mutex) : mutex(mutex), locked(false) {
        locked = (xSemaphoreTake(mutex, pdMS_TO_TICKS(5000)) == pdTRUE);
    }
    ~SDLockGuard() {
        if (locked) xSemaphoreGive(mutex);
    }
    bool isLocked() const { return locked; }
};

bool FileSystem::init(Application* appInstance) {
    if (initialized) {
        return true;
    }
    
    // Store application instance with fallback to singleton
    if (appInstance == nullptr) {
        app = Application::getInstance();
    } else {
        app = appInstance;
    }
    
    if (!app) {
        Serial.println("ERROR: Failed to get Application instance");
        return false;
    }
    
    // Initialize mutex
    sdMutex = xSemaphoreCreateMutex();
    if (sdMutex == nullptr) {
        app->log("ERROR: Failed to create SD card mutex");
        return false;
    }

    SDLockGuard lock(sdMutex);
    if (!lock.isLocked()) {
        app->log("ERROR: Failed to take SD card mutex during initialization");
        return false;
    }

    // Initialize SD card with retry mechanism
    const int maxRetries = 3;
    int retryCount = 0;
    bool sdInitialized = false;
    
    while (!sdInitialized && retryCount < maxRetries) {
        // Attempt to initialize the SD card
        app->log("Initializing SD card (attempt " + String(retryCount + 1) + " of " + String(maxRetries) + ")...");
        
        // Try initializing with different speeds if we're retrying
        uint32_t sdSpeed = (retryCount == 0) ? SD_SPEED : (SD_SPEED / (retryCount + 1));
        
        if (SD.begin(21, SPI, sdSpeed)) {
            sdInitialized = true;
        } else {
            app->log("SD Card initialization failed, retrying...");
            retryCount++;
            // Short delay before retry
            delay(500);
        }
    }
    
    if (!sdInitialized) {
        app->log("ERROR: SD Card initialization failed after multiple attempts!");
        return false;
    }

    uint8_t cardType = SD.cardType();
    if (cardType == CARD_NONE) {
        app->log("ERROR: No SD card attached");
        return false;
    }

    String cardTypeStr = "UNKNOWN";
    if (cardType == CARD_MMC) {
        cardTypeStr = "MMC";
    } else if (cardType == CARD_SD) {
        cardTypeStr = "SDSC";
    } else if (cardType == CARD_SDHC) {
        cardTypeStr = "SDHC";
    }
    app->log("SD Card Type: " + cardTypeStr);

    uint64_t cardSize = SD.cardSize() / (1024 * 1024);
    app->log("SD Card Size: " + String((unsigned long)cardSize) + "MB");

    initialized = true;
    app->log("FileSystem initialized successfully");
    return true;
}

SemaphoreHandle_t FileSystem::getSDMutex() {
    return sdMutex;
}

bool FileSystem::ensureDirectory(const char* path) {
    if (!initialized && !init()) {
        return false;
    }
    
    SDLockGuard lock(sdMutex);
    if (!lock.isLocked()) {
        app->log("ERROR: Failed to take SD card mutex for directory creation: " + String(path));
        return false;
    }

    bool result = true;
    if (!SD.exists(path)) {
        result = SD.mkdir(path);
        if (result) {
            app->log("Created directory: " + String(path));
        } else {
            app->log("ERROR: Failed to create directory: " + String(path));
        }
    }

    return result;
}

bool FileSystem::ensureDirectory(const String& path) {
    return ensureDirectory(path.c_str());
}

bool FileSystem::createEmptyFile(const String& path) {
    return overwriteFile(path, "");
}

bool FileSystem::addToFile(const String& path, const String& content, bool isUploadQueue) {
    if (!initialized && !init()) {
        return false;
    }

    // Ensure parent directory exists
    int lastSlash = path.lastIndexOf('/');
    if (lastSlash > 0) {
        String dirPath = path.substring(0, lastSlash);
        if (!ensureDirectory(dirPath.c_str())) {
            app->log("ERROR: Failed to create parent directory for " + path);
            return false;
        }
    }

    SDLockGuard lock(sdMutex);
    if (!lock.isLocked()) {
        app->log("ERROR: Failed to take SD card mutex for file append operation");
        return false;
    }

    File file = SD.open(path, FILE_APPEND);
    if (!file) {
        app->log("ERROR: Failed to open file for appending: " + path);
        return false;
    }

    size_t bytesWritten = file.print(content);
    file.close();

    if (bytesWritten != content.length()) {
        app->log("ERROR: Failed to write all data to file: " + path);
        return false;
    }

    if (isUploadQueue) {
        app->log("Added to upload queue: " + content.substring(0, content.length() - 1)); // Remove newline
    }

    return true;
}

bool FileSystem::overwriteFile(const String& path, const String& content) {
    if (!initialized && !init()) {
        return false;
    }

    // Ensure parent directory exists
    int lastSlash = path.lastIndexOf('/');
    if (lastSlash > 0) {
        String dirPath = path.substring(0, lastSlash);
        if (!ensureDirectory(dirPath.c_str())) {
            app->log("ERROR: Failed to create parent directory for " + path);
            return false;
        }
    }

    SDLockGuard lock(sdMutex);
    if (!lock.isLocked()) {
        app->log("ERROR: Failed to take SD card mutex for file write operation");
        return false;
    }

    File file = SD.open(path, FILE_WRITE);
    if (!file) {
        app->log("ERROR: Failed to open file for writing: " + path);
        return false;
    }

    size_t bytesWritten = file.print(content);
    file.close();

    if (bytesWritten != content.length()) {
        app->log("ERROR: Failed to write all data to file: " + path);
        return false;
    }

    return true;
}

String FileSystem::readFile(const String& path) {
    String content = "";
    
    if (!initialized && !init()) {
        return content;
    }

    SDLockGuard lock(sdMutex);
    if (!lock.isLocked()) {
        app->log("ERROR: Failed to take SD card mutex for file read operation");
        return content;
    }

    if (!SD.exists(path)) {
        return content; // Return empty string if file doesn't exist
    }

    File file = SD.open(path, FILE_READ);
    if (!file) {
        app->log("ERROR: Failed to open file for reading: " + path);
        return content;
    }

    content = file.readString();
    file.close();
    
    return content;
}

bool FileSystem::readFileToBuffer(const String& path, uint8_t** buffer, size_t& size) {
    if (!initialized && !init()) {
        return false;
    }

    *buffer = nullptr;
    size = 0;

    SDLockGuard lock(sdMutex);
    if (!lock.isLocked()) {
        app->log("ERROR: Failed to take SD card mutex for file read operation");
        return false;
    }

    if (!SD.exists(path)) {
        app->log("ERROR: File does not exist: " + path);
        return false;
    }

    File file = SD.open(path, FILE_READ);
    if (!file) {
        app->log("ERROR: Failed to open file for reading: " + path);
        return false;
    }

    size = file.size();
    *buffer = (uint8_t*)malloc(size);
    
    if (*buffer == nullptr) {
        app->log("ERROR: Failed to allocate memory for file: " + path);
        file.close();
        return false;
    }

    size_t bytesRead = file.read(*buffer, size);
    file.close();

    if (bytesRead != size) {
        app->log("ERROR: Failed to read entire file: " + path);
        free(*buffer);
        *buffer = nullptr;
        size = 0;
        return false;
    }

    return true;
}

bool FileSystem::deleteFile(const String& path) {
    if (!initialized && !init()) {
        return false;
    }

    SDLockGuard lock(sdMutex);
    if (!lock.isLocked()) {
        app->log("ERROR: Failed to take SD card mutex for file delete operation");
        return false;
    }

    if (!SD.exists(path)) {
        return true; // File doesn't exist, consider it "successfully deleted"
    }

    if (!SD.remove(path)) {
        app->log("ERROR: Failed to delete file: " + path);
        return false;
    }

    return true;
}

bool FileSystem::addToUploadQueue(const String &filename) {
    // Basic validation
    if (filename.length() == 0) {
        app->log("ERROR: Cannot add empty filename to upload queue");
        return false;
    }

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
        app->log("ERROR: Cannot remove from empty upload queue");
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
        app->log("Removed from upload queue: " + removedFile);
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