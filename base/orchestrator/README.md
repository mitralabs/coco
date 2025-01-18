# Orchestrator Service

This is a Python-based orchestrator that coordinates the transcription, text chunking, embedding, and database services. It handles the flow of data between services and manages the overall pipeline.

At the moment, the orchestrator only calls the endpoints and does not run the docker containers. Start the docker containers before running the orchestrator on the ports specified in the following README by using the SDK and compose.yaml file.

## Usage
1. **Make sure all services run**  
   Follow [this readme](../README.md).

2. **Install Dependencies**
   - Setup a virtual environment if you want to.
   - Follow [this readme](../sdk/README.md) to install the Coco Python SDK.
   - Install additional modules used in `orchestrator.py` manually.
   
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

## New Feature: RAG Query

The `ragquery` function allows you to query the system using a specific question and context. It retrieves relevant chunks from the database and formats the response based on the provided context.

### Example Usage
To test the `ragquery` function, you can modify the `main` function in `orchestrator.py` as follows:

```python
def main():
    ragquery("What do you know?")
```

### Required Containers
To use the `ragquery` function, ensure the following containers are running:

- **Embedding Service** (Port 8002)
- **Database Service** (Port 8003)

## Example Usage

```bash
# Process an audio file
python orchestrator.py
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