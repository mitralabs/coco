# Coco Python SDK

The Coco Python SDK provides a unified interface to interact with various Coco services for text processing, embedding generation, database operations, and RAG (Retrieval Augmented Generation) capabilities.

## Installation

Clone the repository and install in development mode:

```bash
cd python_sdk
pip install -e .
```

## Quick Start

```python
from coco import CocoClient

# Initialize client with service endpoints
client = CocoClient(
    chunking_base="http://localhost:8001",
    embedding_base="http://localhost:8002",
    db_api_base="http://localhost:8003",
    transcription_base="http://localhost:8000",
    ollama_base="http://localhost:11434",
    api_key="your-api-key"
)

# Verify services are running
client.health_check()
```

## Configuration

The client can be configured either through constructor arguments or environment variables:

| Parameter          | Environment Variable        | Description                            |
| ------------------ | --------------------------- | -------------------------------------- |
| chunking_base      | COCO_CHUNK_URL_BASE         | Base URL for the chunking service      |
| embedding_base     | COCO_EMBEDDING_URL_BASE     | Base URL for the embedding service     |
| db_api_base        | COCO_DB_API_URL_BASE        | Base URL for the database API          |
| transcription_base | COCO_TRANSCRIPTION_URL_BASE | Base URL for the transcription service |
| ollama_base        | COCO_OLLAMA_URL_BASE        | Base URL for the Ollama service        |
| api_key            | COCO_API_KEY                | API key for authentication             |

Constructor arguments take precedence over environment variables.

## Service Modules

### Transcription

Convert audio files to text:

```python
text, language, filename = client.transcription.transcribe_audio("audio.mp3")
```

### Chunking

Split text into semantic chunks:

```python
chunks = client.chunking.chunk_text(
    text="Long text to chunk...",
    chunk_size=1000,
    chunk_overlap=200
)
```

### Embeddings

Generate embeddings for text chunks:

```python
embeddings = client.embedding.create_embeddings(
    chunks=["text chunk 1", "text chunk 2"],
    batch_size=20,
    limit_parallel=10,
    show_progress=True
)
```

### Database Operations

Store and retrieve chunks:

```python
# Store chunks with embeddings
n_added, n_skipped = client.db_api.store_in_database(
    chunks=chunks,
    embeddings=embeddings,
    language="en",
    filename="example.txt"
)

# Retrieve similar chunks
ids, documents, metadatas, distances = client.db_api.get_closest(
    embedding=query_embedding,
    n_results=5
)

# Clear database
deleted_count = client.db_api.clear_database()
```

### RAG (Retrieval Augmented Generation)

Perform end-to-end RAG operations:

```python
# Retrieve relevant chunks
results = client.retrieve_chunks(
    query_texts=["What is the capital of France?"],
    n_results=5
)

# Generate answers using retrieved context
answers, token_speeds = client.rag.generate_answers(
    queries=["What is the capital of France?"],
    context_chunks=[["Paris is the capital of France.", "Other context..."]],
    ollama_model="llama3.2:1b",
    pull_model=True
)
```

## Development Utilities

### Batched Parallel Processing

The SDK includes a powerful utility for processing large batches of data in parallel. The `batched_parallel` wrapper handles:

- Automatic batching of list arguments
- Parallel processing with concurrency limits
- Progress tracking
- Result aggregation

Requirements for the wrapped function:

1. Must be an async function
2. All list arguments must have the same length
3. Must return either:
   - A single list where element i corresponds to the result of processing input elements i
   - A tuple of lists where each list follows the same pattern

Example usage:

```python
from coco.async_utils import batched_parallel

# Define an async function that processes a batch of inputs
async def async_process_function(texts: List[str], metadata: List[Dict]):
    # Both inputs must have the same length
    assert len(texts) == len(metadata)
    # Process each pair of inputs
    results = []
    for text, meta in zip(texts, metadata):
        result = await process_single_item(text, meta)
        results.append(result)
    return results

# The wrapper converts the async function into a synchronous one
# that handles batching and parallel execution internally
batched_process = batched_parallel(
    function=async_process_function,
    batch_size=20,
    limit_parallel=10,
    show_progress=True,
    description="Processing items"
)

# All list arguments must have the same length
texts = ["text1", "text2", "text3"]
metadata = [{"id": 1}, {"id": 2}, {"id": 3}]

# Call like a normal function - batching and async execution are handled internally
results = batched_process(texts, metadata)
# results[i] contains the processed result for texts[i] and metadata[i]
```

This pattern is used throughout the SDK for efficient processing of large datasets. For example, in the RAG module:

```python
# Internal async function that processes batches
async def _generate_answers(
    self,
    queries: List[str],
    context_chunks: List[List[str]],
    ...
) -> Tuple[List[str], List[float]]:
    # Process each query with its context chunks
    answers, tok_ss = [], []
    for query, chunks in zip(queries, context_chunks):
        answer = await generate_single_answer(query, chunks)
        token_speed = compute_token_speed(answer)
        answers.append(answer)
        tok_ss.append(token_speed)
    # Return tuple of lists where each list[i] corresponds to queries[i]
    return answers, tok_ss

# Wrapped for parallel processing
answers, token_speeds = client.rag.generate_answers(
    queries=many_queries,          # List[str]
    context_chunks=many_contexts,  # List[List[str]] (same length as queries)
    batch_size=5,
    limit_parallel=10
)
# answers[i] is the answer for queries[i] using context_chunks[i]
# token_speeds[i] is the generation speed for queries[i]
```

### Utility Functions

The SDK provides several utility functions for common operations:

```python
# Embed and store chunks in one operation
n_added, n_skipped = client.embed_and_store(
    chunks=chunks,
    language="en",
    filename="example.txt",
    batch_size=20,
    limit_parallel=10,
    show_progress=True
)
```

## Error Handling

The SDK raises exceptions with descriptive messages when:

- Service endpoints are not configured
- API calls fail
- Invalid parameters are provided
- Services return error responses

Example:

```python
try:
    client.health_check()
except Exception as e:
    print(f"Service health check failed: {e}")
```

## Examples

For complete examples of using the SDK, check out the test/rag directory which demonstrates:

- Loading and preprocessing datasets
- Storing documents in the vector database
- Performing semantic search
- Generating answers using RAG
