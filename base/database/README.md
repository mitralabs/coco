# Database Container with ChromaDB

This is a FastAPI-based service that provides vector database functionality using ChromaDB. The service is containerized with Docker for easy deployment and serves as the storage component of the pipeline.

## Setup

1. **Build the Docker image:**
   ```bash
   docker build -t chroma-database .
   ```

2. **Run the Docker container:**
   
   For Unix/Linux/MacOS:
   ```bash
   docker run -d -p 8000:8000 -v $(pwd)/app:/app -v $(pwd)/../_data:/data chroma-database
   ```

   For Windows (PowerShell):
   ```powershell
   docker run -d -p 8000:8000 -v ${PWD}/app:/app -v ${PWD}/../_data:/data chroma-database
   ```

## Usage

The service provides three endpoints:

### 1. Add Documents Endpoint (`/add`)

Send a POST request to add documents to the ChromaDB collection:

```bash
curl -X POST "http://localhost:8000/add" \
     -H "X-API-Key: your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
       "status": "success",
       "documents": [
         {
           "text": "Your document text here",
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

Parameters:
- `documents`: Array of document objects containing:
  - `text`: The document content (required)
  - `metadata`: Document metadata (required)
    - `language`: Document language (optional)
    - `filename`: Source filename (optional)
    - `chunk_index`: Index of this chunk (required)
    - `total_chunks`: Total number of chunks (required)

### 2. Query Documents Endpoint (`/query`)

Send a POST request to search for similar documents:

```bash
curl -X POST "http://localhost:8000/query" \
     -H "X-API-Key: your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
       "query_text": "Your search query here",
       "n_results": 5
     }'
```

Parameters:
- `query_text`: The text to search for (required)
- `n_results`: Number of results to return (optional, default: 5)

### 3. Get All Documents Endpoint (`/all`)

Send a GET request to retrieve all documents from the collection:

```bash
curl -X GET "http://localhost:8000/all" \
     -H "X-API-Key: your_api_key"
```

Response format:
```json
{
  "status": "success",
  "count": 2,
  "documents": [
    {
      "document": "Document content here",
      "metadata": {
        "language": "en",
        "filename": "example.txt",
        "chunk_index": 0,
        "total_chunks": 1
      },
      "distance": 0.0
    },
    {
      "document": "Another document content",
      "metadata": {
        "language": "en",
        "filename": "example2.txt",
        "chunk_index": 1,
        "total_chunks": 2
      },
      "distance": 0.0
    }
  ]
}
```

### 4. Test Endpoint (`/test`)

Basic endpoint to verify the service is running:

```bash
curl -X GET -H "X-API-Key: your_api_key" http://localhost:8000/test
```

## Response Formats

### Add Documents Response:
```json
{
  "status": "success",
  "message": "Documents added successfully"
}
```

### Query Response:
```json
{
  "status": "success",
  "results": [
    {
      "documents": ["document content"],
      "metadatas": [{
        "language": "en",
        "filename": "example.txt",
        "chunk_index": 0,
        "total_chunks": 1
      }],
      "distances": [0.123]
    }
  ]
}
```

## Configuration

The service requires the following environment variables:

- `API_KEY`: Your API key for authentication

## Notes

- The service uses ChromaDB for efficient vector storage and similarity search
- All endpoints require API key authentication
- Documents are stored with their metadata for easy retrieval and filtering
- For more information on ChromaDB, visit the [ChromaDB Documentation](https://github.com/chroma-core/chroma)