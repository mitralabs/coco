# Coco Python SDK

## Installation (for development)

From **this directory** (`python_sdk`):

```bash
pip install -e .
```

(Note that this installs the package for development.
When installing this way, code changes made in this
directory are directly reflected in the package
without reinstallation. Only if new dependencies
are added to `pyproject.toml`, the installation
has to be rerun.)

## Initialization

The SDK can be initialized either through environment variables or by passing the configuration directly to the client:

### Environment Variables

```bash
export COCO_CHUNK_URL_BASE="http://your-chunking-service"
export COCO_EMBEDDING_URL_BASE="http://your-embedding-service"
export COCO_DB_API_URL_BASE="http://your-db-api-service"
export COCO_TRANSCRIPTION_URL_BASE="http://your-transcription-service"
export COCO_API_KEY="your-api-key"
```

### Direct Initialization

```python
from coco import CocoClient

client = CocoClient(
    chunking_base="http://your-chunking-service",
    embedding_base="http://your-embedding-service",
    db_api_base="http://your-db-api-service",
    transcription_base="http://your-transcription-service",
    api_key="your-api-key"
)
```

### Combination

You can also set URLs partially as client arguments
and partially via environment variables.
Not that **for API key and URLs,
client arguments take precedence over environment
variables**.

## Available Modules

The SDK provides several specialized clients for different services:

### Transcription Client

- Handles audio file transcription
- Converts audio files to text with language detection
- Returns transcribed text, detected language, and filename

### Chunking Client

- Processes text into semantic chunks
- Configurable chunk size and overlap
- Optimized for maintaining context and meaning

### Embedding Client

- Creates vector embeddings from text chunks
- Supports batch processing with progress tracking
- Handles large-scale embedding generation efficiently

### DB API Client

- Manages vector database operations
- Supports similarity search queries
- Stores and retrieves embeddings with metadata
- Provides database management functions (clear, get all)

### RAG (Retrieval-Augmented Generation)

- Implements RAG query functionality
- Combines vector search with LLM generation
- Provides context-aware responses in German

## Health Check

You can verify the connection to all services using:

```python
client.health_check()
```

This will test the connection to all services and raise an exception if any service is unavailable.
