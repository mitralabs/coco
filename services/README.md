# Base Services
This directory contains all services running on the base station.

## Services
- **Transcription**: A FastAPI-based service that transcribes audio files into text using the Whisper model.
- **Chunking**: Provides text chunking functionality using LangChain.
- **Embedding**: Generates embeddings for text chunks using the Ollama API, supporting both batch and single text embedding.
- **Database**: Offers vector database functionality using ChromaDB for storing embeddings and metadata.
- **Orchestrator**: Coordinates the transcription, chunking, embedding, and database services, managing the overall data flow.
- **Docker Template**: A boilerplate FastAPI service for creating new services, including basic API key authentication.

## Usage
From **this directory**:
```sh
docker compose up -d --wait
```
This will:
- build the docker images if not present
- spin up all containers
- wait until container health checks pass
(meaning the `/test` endpoints actually return status 200)

(You can omit the `--wait` flag to not wait for the health check, but then containers might return no reply yet.)

If Dockerfiles were changed, force an image rebuild:
```sh
docker compose up -d --wait --build
```