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
    
    // Add getter for SD mutex
    SemaphoreHandle_t getSDMutex() const { return _sdMutex; }

    /**
     * @brief Create a directory if it doesn't exist
     * @param path Directory path to create
     * @return true if directory exists or was created successfully, false otherwise
     */
    bool ensureDirectory(const char* path);

    /**
     * @brief Open a file safely with mutex protection
     * @param path File path
     * @param file Reference to File object
     * @param mode File access mode (FILE_READ, FILE_WRITE, FILE_APPEND)
     * @return true if file was opened successfully, false otherwise
     */
    bool openFile(const String& path, File& file, const char* mode);

    /**
     * @brief Close a file safely
     * @param file File object to close
     */
    void closeFile(File& file);
    
    /**
     * @brief Get the mutex for SD card operations
     * @return Semaphore handle for SD card mutex
     */
    SemaphoreHandle_t getSDMutex() { return _sdMutex; }

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
     * @brief Get total file count in a directory
     * @param dirPath Directory path to check
     * @return Number of files in the directory
     */
    int getFileCount(const char* dirPath);

    /**
     * @brief Delete oldest files if count exceeds limit
     * @param dirPath Directory to manage
     * @param maxFiles Maximum number of files to keep
     * @return Number of files deleted
     */
    int pruneOldestFiles(const char* dirPath, int maxFiles);

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
