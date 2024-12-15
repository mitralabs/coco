# Orchestrator Service

This is a Python-based orchestrator that coordinates the transcription and text chunking services. It handles the flow of data between services and manages the overall pipeline.

At the moment, the orchestrator only calls the endpoints and does not run the docker containers. Start the docker containers before running the orchestrator on the ports specified in the following README.

## Usage

1. **Set up environment:**
   ```bash
   # Create a .env file with your API key
   echo "API_KEY=your_api_key_here" > .env
   ```

2. **Run the orchestrator:**
   ```bash
   python orchestrator.py path/to/your/audio_file.wav
   ```

## Service Configuration

The orchestrator connects to:
- Transcription service on port 8000
- Text chunking service on port 8001
Make sure the Docker services are running on the specified ports and are accessible from the orchestrator.

## Endpoints Used

### Transcription Service (Port 8000)
- **GET /test**: Health check
- **POST /transcribe/**: Transcribe audio files

### Chunking Service (Port 8001)
- **GET /test**: Health check
- **POST /chunk/json**: Process text into chunks

## Example Usage

```bash
# Process an audio file
python orchestrator.py ../data/sample.wav
```

## Notes

- Ensure both transcription and chunking services are running before using the orchestrator
- Default chunk size is 1000 with 200 overlap
- Uses 127.0.0.1 for local connections (more reliable than localhost on Windows)
- The orchestrator will run a health check on the transcription and chunking services before processing the audio file.
