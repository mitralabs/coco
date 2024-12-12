# Transcription Container (Whisper.cpp) !! Currently not working !!

[ ] Dockerfile builds and runs the container but throws an error when trying to transcribe an audio file.
[ ] The error is related to a missing model file.

This is a FastAPI-based container for transcribing audio files using Whisper.cpp, a high-performance C++ port of OpenAI's Whisper model. The service is containerized with Docker for easy deployment and is the first step of the pipeline.

## Build and Run

1. **Build the Docker image:**
   ```bash
   docker build -t data-transcription-cpp .    
   ```

2. **Run the Docker container:**
   
   For Unix/Linux/MacOS:
   ```bash
   docker run -d -p 8000:8000 \
       -v $(pwd)/app:/app \
       -v $(pwd)/../_data:/data \
       data-transcription-cpp
   ```

   For Windows (PowerShell):
   ```powershell
   docker run -d -p 8000:8000 `
       -v ${PWD}/app:/app `
       -v ${PWD}/../_data:/data `
       data-transcription-cpp
   ```

## Usage

Once the service is running, you can transcribe audio files by sending a POST request to the `/transcribe/` endpoint.

### Example using `curl`:

```bash
curl -X POST \
     -H "X-API-Key: your_api_key_here" \
     -F "audio_file=@filepath_to_audio_file.wav" \
     http://localhost:8000/transcribe/
```

Replace `your_api_key_here` with your API key and `filepath_to_audio_file.wav` with the path to your audio file.

## Endpoints

- **POST /transcribe/**: Transcribe an audio file. Accepts a file upload with the key `audio_file`.
  
  **Response Format:**
  ```json
  {
    "status": "success",
    "document": {
      "text": "The transcribed text content",
      "metadata": {
        "language": "detected language code",
        "filename": "original audio filename"
      }
    }
  }
  ```

  In case of an error:
  ```json
  {
    "status": "error",
    "error": "Error message description"
  }
  ```

- **GET /**: Health check endpoint. Returns a simple message indicating the service is running.

## Notes

- This implementation uses Whisper.cpp, which provides better performance compared to the Python implementation.
- The base model is used by default. You can change this in the Dockerfile to other sizes like "small", "medium", or "large".
- Ensure that the audio file is in a format supported by Whisper (e.g. WAV).
