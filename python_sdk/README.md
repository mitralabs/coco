# Coco Python SDK

## Installation (for development)

From **this directory** (`python_sdk`):

```bash
pip install -e .
```

This installs the package for development. When installing this way, code changes made in this directory are directly reflected in the package without reinstallation. Only if new dependencies are added to `pyproject.toml`, the installation has to be rerun.

## Configuration

The SDK can be initialized either through environment variables or by passing the configuration directly to the clients.

### Environment Variables

```bash
export COCO_CHUNK_URL_BASE="http://your-chunking-service"
export COCO_EMBEDDING_URL_BASE="http://your-embedding-service"
export COCO_DB_API_URL_BASE="http://your-db-api-service"
export COCO_TRANSCRIPTION_URL_BASE="http://your-transcription-service"
export COCO_API_KEY="your-api-key"
```

### Direct Initialization

Each client requires:

- `base_url`: The base URL of the respective service
- `api_key`: API key for authentication

Default service endpoints:

```python
chunking_base = "http://127.0.0.1:8001"
embedding_base = "http://127.0.0.1:8002"
db_api_base = "http://127.0.0.1:8003"
transcription_base = "http://127.0.0.1:8000"
```

## Usage

The SDK provides a main client class with specialized clients for different services:

```python
from coco import CocoClient

client = CocoClient(
    chunking_base="http://your-chunking-service",
    embedding_base="http://your-embedding-service",
    db_api_base="http://your-db-api-service",
    transcription_base="http://your-transcription-service",
    api_key="your-api-key"
)

# Access specialized clients
client.db       # Database operations
client.embed    # Embedding generation
client.chunk    # Text chunking
client.rag      # RAG queries
client.transcribe  # Audio transcription
```

### Database Operations

```python
# Get closest matches for a single embedding
ids, documents, metadatas, distances = client.db.get_closest(
    embedding,   # List[float]: The query embedding
    n_results=5  # int: Number of results to return
)

# Get closest matches for multiple embeddings
results = client.db.get_multiple_closest(
    embeddings,        # List[List[float]]: Query embeddings
    n_results=5,       # int: Results per query
    batch_size=20,     # int: Batch size for processing
    limit_parallel=10, # int: Max parallel batches
    show_progress=True # bool: Show progress bar
)

# Get full database contents
ids, documents, metadatas = client.db.get_full_database()

# Clear database
deleted_count = client.db.clear_database()

# Store documents in database
n_added, n_skipped = client.db.store_in_database(
    chunks,           # List[str]: Text chunks to store
    embeddings,       # List[List[float]]: Chunk embeddings
    language,         # str: Language code
    filename,         # str: Source filename
    batch_size=20,    # int: Batch size
    limit_parallel=10,# int: Max parallel batches
    show_progress=False
)
```

### Embedding Generation

```python
# Create embeddings for text chunks
embeddings = client.embed.create_embeddings(
    chunks,           # List[str]: Text chunks to embed
    batch_size=20,    # int: Batch size for processing
    limit_parallel=10,# int: Max parallel batches
    show_progress=False
)
```

### RAG Queries

```python
# Perform a RAG query
answer, tokens_per_second = client.rag.query(
    query,        # str: The query to answer
    verbose=False # bool: Whether to print retrieved documents and distances
)
```

### Text Chunking

```python
# Process text into semantic chunks
chunks = client.chunk.create_chunks(
    text,        # str: Text to chunk
    language     # str: Language of the text
)
```

### Audio Transcription

```python
# Transcribe audio file
text, language = client.transcribe.process_file(
    file_path,   # str: Path to audio file
    language     # str: Expected language (optional)
)
```

## Health Check

You can verify the connection to all services using:

```python
client.health_check()
```

This will test the connection to all services and raise an exception if any service is unavailable.
