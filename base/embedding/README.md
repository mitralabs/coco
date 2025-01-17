# Embedding Container

This FastAPI-based service generates embeddings for text chunks using the Ollama API. The service is containerized with Docker for easy deployment and integration.

## Setup

1. **Build the Docker image:**
   ```bash
   docker build -t embedding .
   ```

2. **Run the Docker container:**
   
   For Unix/Linux/MacOS:
   ```bash
   docker run -d -p 8000:8000 -v $(pwd)/app:/app embedding
   ```

   For Windows (PowerShell):
   ```powershell
   docker run -d -p 8000:8000 -v ${PWD}/app:/app embedding
   ```

## Usage

The service provides three main endpoints:

### 1. Pull Model Endpoint

First, ensure the embedding model is available https://ollama.com/search

```bash
curl -X GET -H "X-API-Key: your_api_key_here" http://localhost:8000/model/pull
```

### 2. Embed Chunks Endpoint

Send multiple text chunks for embedding:

```bash
curl -X POST "http://localhost:8000/embed_chunks" \
     -H "X-API-Key: your_api_key_here" \
     -H "Content-Type: application/json" \
     -d '{
       "status": "success",
       "chunks": [
         {
           "text": "Your text here",
           "metadata": {
             "language": "en",
             "filename": "example.txt",
             "chunk_index": 0,
             "total_chunks": 1
           }
         }
       ]
     }'
```

The response will maintain the same structure but include embeddings for each chunk:

```json
{
  "status": "success",
  "chunks": [
    {
      "text": "Your text here",
      "metadata": {
        "language": "en",
        "filename": "example.txt",
        "chunk_index": 0,
        "total_chunks": 1
      },
      "embedding": [0.1, 0.2, 0.3, ...]
    }
  ]
}
```

### 3. Embed Single Text Endpoint

Send a single text for embedding:

```bash
curl -X POST "http://localhost:8000/embed_text" \
     -H "X-API-Key: your_api_key_here" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "Your text here"
     }'
```

The response will contain the embedding vector:

```json
{
  "status": "success",
  "embedding": [0.1, 0.2, 0.3, ...]
}
```

### Health Check

Test if the service is running:

```bash
curl -X GET -H "X-API-Key: your_api_key_here" http://localhost:8000/test
```

## Configuration

The service requires the following environment variables:

- `API_KEY`: Your API key for authentication
- `OLLAMA_MODEL`: The model to use for embeddings (defaults to "nomic-embed-text")

## Notes

- The service uses the Ollama API to generate embeddings
- Ensure your API key is properly set in the environment variables
- The service provides both batch embedding (/embed_chunks) and single text embedding (/embed_text) capabilities
- All endpoints require API key authentication via the X-API-Key header
