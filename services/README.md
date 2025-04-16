## Info:

- **Transcription**: A FastAPI-based service that transcribes audio files into text using the Whisper model.
- **Chunking**: Provides text chunking functionality using LangChain.
- **Database**: Offers vector database functionality using Postgres for storing embeddings and metadata.
- **Orchestrator**: Is the bridge between the coco hardware device and the backend.
- **Frontend**: A Gradio-based web interface that provides an Interactive chat interface and a view of the database 

#### Notes on the Database:
- The service automatically pads embeddings that are smaller than the maximum dimension
- Documents with identical text content will be skipped during insertion
- The API uses cosine similarity for finding semantically similar documents
- Please refer to the [migrations-doc](db_api/migrations.md) of the service for Database Migrations.


## Usage
1. Duplicate the `.env.template`file and rename it to `.env`
2. Choose a [whisper model](https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md).
3. Choose if you want to stay local with Ollama or Fallback to OpenAI or an OpenAI like service. If the latter is the case, set your OpenAI_API_KEY
4. Make sure to download an embedding model (case ollama) and/or set the COCO_EMBEDDING_MODEL.
5. Run the `backend_start.sh`script. It will do the following:
  - Download the whisper.cpp repository, and remove it's git connection.
  - Compile whisper for your machine.
  - Download the whisper model of your choice
  - Create a virtual environment for the packages needed for the transcription service.
  - Start a FastAPI App in the Background as Transcription Service.
  - Kick off the Build/Compose Process for all other services as Docker Containers.


### Spinning up individual Docker Containers:

You can start individual services as needed:

```bash
# From the services directory
docker compose up chunking
docker compose up db-api
docker compose up db
docker compose up frontend
docker compose up orchestrator

# To rebuild a specific container
docker compose up --build <service-name>
```

#### Service Ports:
- Chunking: http://localhost:8001 (FastAPI)
- DB-API: http://localhost:8003 (FastAPI)
- Database: localhost:5432 (PostgreSQL)
- Frontend: http://localhost:8002 (Gradio UI)
- Orchestrator: http://localhost:3030 (FastAPI)

API documentation for FastAPI services is available at `http://localhost:<port>/docs` (Swagger UI).

## Final Notes:
- It is currently not implemented, that transcription is not done locally. But it's definitely possible to change that, since our approach follows the openai transcription standard.
- If you want to see if the transcription process is running in the background use the command `ps aux | grep uvicorn`, which will show the uvicorn processes on your machine. If you further want to kill a process, use `kill <PID>` where <PID> is the Process ID.