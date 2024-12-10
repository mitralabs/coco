# Text Chunking Service

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

The service provides two endpoints:

### 1. Chunk Text Endpoint

Send a POST request to `/chunk` with a text file to split it into chunks:
