# Transcription Container

This is a FastAPI-based container for transcribing audio files using OpenAI's Whisper model. The service is containerized with Docker for easy deployment and the first step of the pipeline.

1. **Build the Docker image:**
   ```bash
   docker build -t whisper-api .    
   ```

2. **Run the Docker container:**
   
   For Unix/Linux/MacOS:
   ```bash
   docker run -d -p 8000:8000 -v $(pwd)/app:/app -v $(pwd)/../_data:/data transcription
   ```

   For Windows (PowerShell):
   ```powershell
   docker run -d -p 8000:8000 -v ${PWD}/app:/app -v ${PWD}/../_data:/data transcription
   ```

## Usage

Once the service is running, you can transcribe audio files by sending a POST request to the `/transcribe/` endpoint.

### Example using `curl`:

```bash
curl -X POST -H "X-API-Key: your_api_key_here" -F "audio_file=@filepath_to_audio_file.wav" http://localhost:8000/transcribe/
```

Replace `X-API-Key: your_api_key_here` with your API key and `filepath_to_audio_file.wav` with the path to your audio file.

## Endpoints

- **POST /transcribe/**: Transcribe an audio file. Accepts a file upload with the key `audio_file`.

- **GET /**: Health check endpoint. Returns a simple message indicating the service is running.

## Notes

- The Whisper model used is the "tiny" version. You can change this in `app/main.py` to other sizes like "small", "medium", or "large" depending on your needs and available resources.

- Ensure that the audio file is in a format supported by Whisper (e.g., WAV).

## ToDo
- [ ] Deploy and run other models like whisper-large-v3, whisper.cpp to compare the results
- [ ] Implement a routing system that chooses the best model based on the audio file size, quality, language, etc.