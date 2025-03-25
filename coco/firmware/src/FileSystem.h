/**
 * @file FileSystem.h
 * @brief File system management module for Coco firmware
 * 
 * This module handles SD card initialization, file operations, 
 * and upload queue management. It provides a centralized interface
 * for all file-related operations in the system.
 */

#ifndef FILESYSTEM_H
#define FILESYSTEM_H

#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "config.h"

/**
 * Singleton class for file system operations
 */
class FileSystem {
public:
    /**
     * @brief Get the singleton instance of the FileSystem
     * @return Pointer to the FileSystem instance
     */
    static FileSystem* getInstance();

    /**
     * @brief Initialize the file system module
     * @return true if initialization was successful, false otherwise
     */
    bool init();

    /**
     * @brief Get the mutex for SD card operations
     * @return Semaphore handle for SD card mutex
     */
    SemaphoreHandle_t getSDMutex() const { return _sdMutex; }

    /**
     * @brief Create a directory if it doesn't exist
     * @param path Directory path to create
     * @return true if directory exists or was created successfully, false otherwise
     */
    bool ensureDirectory(const char* path);

    /**
     * @brief Add content to a file (append)
     * @param path File path
     * @param content String content to add
     * @param isUploadQueue Whether this is an upload queue operation
     * @return true if operation was successful, false otherwise
     */
    bool addToFile(const String& path, const String& content, bool isUploadQueue = false);

    /**
     * @brief Overwrite a file with new content
     * @param path File path
     * @param content String content to write
     * @return true if operation was successful, false otherwise
     */
    bool overwriteFile(const String& path, const String& content);

    /**
     * @brief Read entire file content
     * @param path File path
     * @return String containing file content, or empty string on error
     */
    String readFile(const String& path);

    /**
     * @brief Delete a file
     * @param path File path
     * @return true if file was deleted successfully, false otherwise
     */
    bool deleteFile(const String& path);

    /**
     * @brief Add a file to the upload queue
     * @param filename Full path of the file to add
     * @return true if file was added successfully, false otherwise
     */
    bool addToUploadQueue(const String &filename);

    /**
     * @brief Get the next file from the upload queue
     * @return String containing the file path, or empty string if queue is empty
     */
    String getNextUploadFile();

    /**
     * @brief Remove the first file from the upload queue
     * @return true if file was removed successfully, false otherwise
     */
    bool removeFirstFromUploadQueue();

    /**
     * @brief Check if the upload queue is empty
     * @return true if queue is empty, false otherwise
     */
    bool isUploadQueueEmpty();

    /**
     * @brief Check if a file is in the upload queue
     * @param filename Full path of the file to check
     * @return true if file is in the queue, false otherwise
     */
    bool isFileInUploadQueue(const String &filename);

private:
    // Private constructor for singleton pattern
    FileSystem();
    
    // Delete copy constructor and assignment operator
    FileSystem(const FileSystem&) = delete;
    void operator=(const FileSystem&) = delete;
    
    // Filesystem state
    bool _initialized;
    SemaphoreHandle_t _sdMutex;
    
    // Singleton instance
    static FileSystem* _instance;
};

#endif // FILESYSTEM_H