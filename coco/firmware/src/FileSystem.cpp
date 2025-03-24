/**
 * @file FileSystem.cpp
 * @brief Implementation of file system management module
 */

#include "FileSystem.h"
#include "LogManager.h"

// Initialize static member
FileSystem* FileSystem::_instance = nullptr;

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

    if (xSemaphoreTake(_sdMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
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
        xSemaphoreGive(_sdMutex);
        return false;
    }

    uint8_t cardType = SD.cardType();
    if (cardType == CARD_NONE) {
        Serial.println("ERROR: No SD card attached");
        xSemaphoreGive(_sdMutex);
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

    // Create necessary directories
    ensureDirectory(RECORDINGS_DIR);

    // Initialize upload queue file if it doesn't exist
    if (!SD.exists(UPLOAD_QUEUE_FILE)) {
        File queueFile = SD.open(UPLOAD_QUEUE_FILE, FILE_WRITE);
        if (queueFile) {
            queueFile.close();
        } else {
            Serial.println("ERROR: Failed to create upload queue file");
            xSemaphoreGive(_sdMutex);
            return false;
        }
    }

    xSemaphoreGive(_sdMutex);
    _initialized = true;
    return true;
}

bool FileSystem::ensureDirectory(const char* path) {
    if (xSemaphoreTake(_sdMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
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

    xSemaphoreGive(_sdMutex);
    return result;
}

bool FileSystem::openFile(const String& path, File& file, const char* mode) {
    if (!_initialized) {
        Serial.println("ERROR: FileSystem not initialized");
        return false;
    }

    if (xSemaphoreTake(_sdMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
        Serial.println("ERROR: Failed to take SD card mutex for file operation");
        return false;
    }

    file = SD.open(path, mode);
    if (!file) {
        Serial.printf("ERROR: Failed to open file: %s\n", path.c_str());
        xSemaphoreGive(_sdMutex);
        return false;
    }

    return true;
}

void FileSystem::closeFile(File& file) {
    if (file) {
        file.close();
        xSemaphoreGive(_sdMutex);
    }
}

bool FileSystem::addToUploadQueue(const String &filename) {
    File queueFile;
    bool success = openFile(UPLOAD_QUEUE_FILE, queueFile, FILE_APPEND);
    if (!success) {
        LogManager::log("Failed to open upload queue file for writing");
        return false;
    }
    
    queueFile.println(filename);
    closeFile(queueFile);
    return true;
}

String FileSystem::getNextUploadFile() {
    String nextFile = "";
    
    File queueFile;
    if (openFile(UPLOAD_QUEUE_FILE, queueFile, FILE_READ)) {
        if (queueFile.available()) {
            nextFile = queueFile.readStringUntil('\n');
            nextFile.trim(); // Remove any newline characters
        }
        closeFile(queueFile);
    }
    
    return nextFile;
}

bool FileSystem::removeFirstFromUploadQueue() {
    if (xSemaphoreTake(_sdMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
        return false;
    }
    
    if (!SD.exists(UPLOAD_QUEUE_FILE)) {
        xSemaphoreGive(_sdMutex);
        return false;
    }
    
    File queueFile = SD.open(UPLOAD_QUEUE_FILE, FILE_READ);
    if (!queueFile) {
        xSemaphoreGive(_sdMutex);
        return false;
    }
    
    // Create a temporary file
    File tempFile = SD.open(UPLOAD_QUEUE_TEMP, FILE_WRITE);
    if (!tempFile) {
        queueFile.close();
        xSemaphoreGive(_sdMutex);
        return false;
    }
    
    // Skip the first line and copy the rest
    bool firstLine = true;
    String line;
    
    while (queueFile.available()) {
        line = queueFile.readStringUntil('\n');
        
        if (firstLine) {
            firstLine = false;
            // Skip the first line (we're removing it)
            continue;
        }
        
        tempFile.println(line);
    }
    
    queueFile.close();
    tempFile.close();
    
    // Replace original file with temp file
    SD.remove(UPLOAD_QUEUE_FILE);
    SD.rename(UPLOAD_QUEUE_TEMP, UPLOAD_QUEUE_FILE);
    
    xSemaphoreGive(_sdMutex);
    return true;
}

bool FileSystem::isUploadQueueEmpty() {
    String nextFile = getNextUploadFile();
    return nextFile.length() == 0;
}

int FileSystem::getFileCount(const char* dirPath) {
    if (xSemaphoreTake(_sdMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
        return -1;
    }
    
    File root = SD.open(dirPath);
    if (!root || !root.isDirectory()) {
        if (root) root.close();
        xSemaphoreGive(_sdMutex);
        return -1;
    }
    
    int count = 0;
    File file = root.openNextFile();
    
    while (file) {
        if (!file.isDirectory()) {
            count++;
        }
        file.close();
        file = root.openNextFile();
    }
    
    root.close();
    xSemaphoreGive(_sdMutex);
    return count;
}

int FileSystem::pruneOldestFiles(const char* dirPath, int maxFiles) {
    int fileCount = getFileCount(dirPath);
    if (fileCount <= maxFiles || fileCount < 0) {
        return 0;
    }
    
    if (xSemaphoreTake(_sdMutex, pdMS_TO_TICKS(5000)) != pdTRUE) {
        return 0;
    }
    
    // List all files with their creation time
    struct FileInfo {
        String path;
        time_t ctime;
    };
    
    // Allocate array for all files
    FileInfo* files = new FileInfo[fileCount];
    if (!files) {
        xSemaphoreGive(_sdMutex);
        return 0;
    }
    
    // Get all files and their creation time
    File root = SD.open(dirPath);
    if (!root || !root.isDirectory()) {
        if (root) root.close();
        delete[] files;
        xSemaphoreGive(_sdMutex);
        return 0;
    }
    
    int index = 0;
    File file = root.openNextFile();
    
    while (file && index < fileCount) {
        if (!file.isDirectory()) {
            files[index].path = String(dirPath) + "/" + file.name();
            files[index].ctime = file.getLastWrite();
            index++;
        }
        file.close();
        file = root.openNextFile();
    }
    
    root.close();
    
    // Sort files by creation time (oldest first)
    for (int i = 0; i < index - 1; i++) {
        for (int j = 0; j < index - i - 1; j++) {
            if (files[j].ctime > files[j + 1].ctime) {
                FileInfo temp = files[j];
                files[j] = files[j + 1];
                files[j + 1] = temp;
            }
        }
    }
    
    // Delete the oldest files
    int filesToDelete = index - maxFiles;
    int deleted = 0;
    
    for (int i = 0; i < filesToDelete; i++) {
        LogManager::log("Pruning old file: " + files[i].path);
        if (SD.remove(files[i].path.c_str())) {
            deleted++;
        } else {
            LogManager::log("Failed to delete file: " + files[i].path);
        }
    }
    
    delete[] files;
    xSemaphoreGive(_sdMutex);
    return deleted;
}
