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

#include "Application.h"
#include "config.h"

/**
 * Static class for file system operations
 */
class FileSystem {
public:
    /**
     * @brief Initialize the file system module
     * @param app Pointer to Application instance
     * @return true if initialization was successful, false otherwise
     */
    static bool init(Application* app = nullptr);

    /**
     * @brief Get the mutex for SD card operations
     * @return Semaphore handle for SD card mutex
     */
    static SemaphoreHandle_t getSDMutex();

    /**
     * @brief Create a directory if it doesn't exist
     * @param path Directory path to create
     * @return true if directory exists or was created successfully, false otherwise
     */
    static bool ensureDirectory(const char* path);
    
    /**
     * @brief Create a directory if it doesn't exist (String overload)
     * @param path Directory path to create
     * @return true if directory exists or was created successfully, false otherwise
     */
    static bool ensureDirectory(const String& path);

    /**
     * @brief Add content to a file (append)
     * @param path File path
     * @param content String content to add
     * @param isUploadQueue Whether this is an upload queue operation
     * @return true if operation was successful, false otherwise
     */
    static bool addToFile(const String& path, const String& content, bool isUploadQueue = false);

    /**
     * @brief Create an empty file
     * @param path File path
     * @return true if file was created successfully, false otherwise
     */
    static bool createEmptyFile(const String& path);

    /**
     * @brief Overwrite a file with new content
     * @param path File path
     * @param content String content to write
     * @return true if operation was successful, false otherwise
     */
    static bool overwriteFile(const String& path, const String& content);

    /**
     * @brief Read entire file content
     * @param path File path
     * @return String containing file content, or empty string on error
     */
    static String readFile(const String& path);

    /**
     * @brief Read a file into a binary buffer
     * @param path File path
     * @param buffer Pointer to buffer pointer that will be allocated
     * @param size Reference to size variable that will be set
     * @return true if file was read successfully, false otherwise
     * @note Caller is responsible for freeing the allocated buffer
     */
    static bool readFileToBuffer(const String& path, uint8_t** buffer, size_t& size);

    /**
     * @brief Delete a file
     * @param path File path
     * @return true if file was deleted successfully, false otherwise
     */
    static bool deleteFile(const String& path);

    /**
     * @brief Add a file to the upload queue
     * @param filename Full path of the file to add
     * @return true if file was added successfully, false otherwise
     */
    static bool addToUploadQueue(const String &filename);

    /**
     * @brief Get the next file from the upload queue
     * @return String containing the file path, or empty string if queue is empty
     */
    static String getNextUploadFile();

    /**
     * @brief Remove the first file from the upload queue
     * @return true if file was removed successfully, false otherwise
     */
    static bool removeFirstFromUploadQueue();

    /**
     * @brief Check if the upload queue is empty
     * @return true if queue is empty, false otherwise
     */
    static bool isUploadQueueEmpty();

    /**
     * @brief Check if a file is in the upload queue
     * @param filename Full path of the file to check
     * @return true if file is in the queue, false otherwise
     */
    static bool isFileInUploadQueue(const String &filename);

    // Prevent copying and assignment
    FileSystem(const FileSystem&) = delete;
    FileSystem& operator=(const FileSystem&) = delete;
    
private:
    // Private static state
    static bool initialized;
    static SemaphoreHandle_t sdMutex;
    static Application* app;
    
    // Private constructor (singleton pattern enforcement)
    FileSystem() = default;
};

#endif // FILESYSTEM_H