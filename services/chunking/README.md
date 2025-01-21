# Text Chunking Container

This is a FastAPI-based service that provides text chunking functionality using LangChain's RecursiveCharacterTextSplitter. The service is containerized with Docker for easy deployment and the second step of the pipeline.

1. **Build the Docker image:**
   ```bash
   docker build -t text-chunking .
   ```

2. **Run the Docker container:**
   
   For Unix/Linux/MacOS:
   ```bash
   docker run -d -p 8000:8000 -v $(pwd)/app:/app -v $(pwd)/../_data:/data text-chunking
   ```

   For Windows (PowerShell):
   ```powershell
   docker run -d -p 8000:8000 -v ${PWD}/app:/app -v ${PWD}/../_data:/data text-chunking
   ```

## Usage

The service provides three endpoints:

### 1. File Chunking Endpoint (`/chunk/file`)

Send a POST request with a text file to split it into chunks:

```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  -F "file=@your_file.txt" \
  -F "chunk_size=1000" \
  -F "chunk_overlap=200" \
  "http://localhost:8000/chunk/file"
```

Parameters:
- `file`: The text file to be chunked (required)
- `chunk_size`: Size of each chunk (optional, default: 1000)
- `chunk_overlap`: Overlap between chunks (optional, default: 200)

### 2. JSON Chunking Endpoint (`/chunk/json`)

Send a POST request with JSON content to split into chunks:

```bash
curl -X POST \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "document": {
      "text": "Your text content here",
      "metadata": {
        "language": "en",
        "filename": "example.txt"
      }
    }
  }' \
  "http://localhost:8000/chunk/json?chunk_size=1000&chunk_overlap=200"
```

Parameters:
- `document`: JSON object containing:
  - `text`: The text content to chunk (required)
  - `metadata`: Additional metadata (optional)
- `chunk_size`: Size of each chunk (optional, default: 1000)
- `chunk_overlap`: Overlap between chunks (optional, default: 200)

### 3. Test Endpoint (`/test`)

Basic endpoint to verify the service is running:

```bash
curl -X GET -H "X-API-Key: your_api_key" http://localhost:8000/test
```

## Response Format

All endpoints return JSON responses in the following format:

```json
{
  "status": "success",
  "chunks": [
    {
      "text": "chunk content",
      "metadata": {
        "chunk_index": 0,
        "total_chunks": 10,
        "language": "en",
        "filename": "example.txt"
      }
    }
  ],
  "num_chunks": 10
}
```

## Notes

- Ensure that the `API_KEY` environment variable is set before running the container
- The chunking service preserves metadata from the input throughout the chunking process
- Each chunk includes its index and the total number of chunks for easy reassembly
- The service supports both direct file uploads and JSON input for flexibility