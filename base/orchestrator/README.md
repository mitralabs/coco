# Orchestrator Service

This is a Python-based orchestrator that coordinates the transcription, text chunking, embedding and database services. It handles the flow of data between services and manages the overall pipeline.

At the moment, the orchestrator only calls the endpoints and does not run the docker containers. Start the docker containers before running the orchestrator on the ports specified in the following README.

## Usage

1. **Set up environment:**
   ```bash
   # Create a .env file with your API key
   echo "API_KEY=your_api_key_here" > .env
   ```

2. **Build and run the Containers:**
   ```bash
   # Build Docker images
   docker build -t data-transcription-openai .
   docker build -t text-chunking .
   docker build -t embedding .
   docker build -t chroma-database .

   # Run Docker containers
   docker run -d -p 8000:8000 -v ${PWD}/app:/app -v ${PWD}/../../_data/models/whisper_cpp:/whisper.cpp/models --name whisper-cpp whisper-cpp
   docker run -d -p 8001:8000 -v ${PWD}/app:/app -v ${PWD}/../_data:/data text-chunking
   docker run -d -p 8002:8000 -v ${PWD}/app:/app embedding
   docker run -d -p 8003:8000 -v ${PWD}/app:/app -v ${PWD}/../_data:/data chroma-database
   ```
   
3. **Run the orchestrator:**
   ```bash
   python orchestrator.py path/to/your/audio_file.wav
   ```

## Service Configuration

The orchestrator connects to:
- Transcription service on port 8000
- Text chunking service on port 8001
- Embedding service on port 8002
- Database service on port 8003
- Make sure the Docker services are running on the specified ports and are accessible from the orchestrator.

## Endpoints Used

### Transcription Service (Port 8000)
- **GET /test**: Health check
- **POST /transcribe/**: Transcribe audio files

### Chunking Service (Port 8001)
- **GET /test**: Health check
- **POST /chunk/json**: Process text into chunks

### Embedding Service (Port 8002)
- **GET /test**: Health check
- **POST /embed**: Embed the chunks

### Database Service (Port 8003)
- **GET /test**: Health check
- **POST /add**: Add the data (chunks and embeddings) into the database

## Example Usage

```bash
# Process an audio file
python orchestrator.py ../data/sample.wav
```

## Notes

- Ensure all Containers are running before using the orchestrator
- Default chunk size is 1000 with 200 overlap
- Uses 127.0.0.1 for local connections (more reliable than localhost on Windows)
- The orchestrator will run a health check on the transcription and chunking services before processing the audio file.

##ToDo

[ ] Change the containers to load the models/db at startup (see OpenAI container)
[ ] Connect the Coco connection for end-to-end connection
[ ] Optimize the data format between the endpoints
[ ] Modular selection of the endpoints