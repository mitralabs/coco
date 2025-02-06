# Coco Python SDK

The Coco Python SDK provides a unified interface for text processing, database operations, and RAG (Retrieval Augmented Generation) with integrated LM capabilities through Ollama and OpenAI-compatible APIs.

## Key Changes

- Removed separate embedding service - embeddings now handled directly by LM module
- Added dual LM support with `embedding_api`/`llm_api` configuration
- Integrated batched processing for all RAG operations
- Simplified service dependencies

## Installation

Clone the repository and install in development mode:

```bash
cd python_sdk
pip install -e .
```

## Quick Start

```python
from coco import CocoClient

# Initialize with LM API selection
client = CocoClient(
    chunking_base="http://localhost:8001",
    db_api_base="http://localhost:8003",
    transcription_base="http://localhost:8000",
    ollama_base="http://localhost:11434",  # For Ollama models
    openai_base="https://api.openai.com/v1",  # For OpenAI-compatible APIs
    embedding_api="ollama",  # Choose embedding provider
    llm_api="openai",        # Choose generation provider
    api_key="your-api-key"
)

# Health check verifies core services (excluding removed embedding service)
client.health_check()
```

## Updated Configuration

| Parameter     | Environment Variable | Description                         |
| ------------- | -------------------- | ----------------------------------- |
| embedding_api | COCO_EMBEDDING_API   | "ollama" or "openai" for embeddings |
| llm_api       | COCO_LLM_API         | "ollama" or "openai" for generation |

## Integrated LM Operations

```python
# Generate embeddings using configured provider
embeddings = client.lm.embed(
    chunks=["text chunk 1", "text chunk 2"],
    model="nomic-embed-text"  # Model specific to chosen API
)

# Generate text with configured provider
answers, speeds = client.rag.generate_answers(
    queries=["What is the capital of France?"],
    context_chunks=[["Paris is the capital..."]],
    model="llama3.2:1b"  # Model specific to chosen API
)
```

## RAG Pipeline Changes

- Embedding generation moved to LM module
- Added automatic model management:

  ```python
  # Auto-pull missing Ollama models
  client.rag.generate_answers(..., pull_model=True)

  # List available models
  ollama_models = client.lm.list_ollama_models()
  ```

## Configuration

The client can be configured either through constructor arguments or environment variables:

| Parameter          | Environment Variable        | Description                            |
| ------------------ | --------------------------- | -------------------------------------- |
| chunking_base      | COCO_CHUNK_URL_BASE         | Base URL for the chunking service      |
| db_api_base        | COCO_DB_API_URL_BASE        | Base URL for the database API          |
| transcription_base | COCO_TRANSCRIPTION_URL_BASE | Base URL for the transcription service |
| ollama_base        | COCO_OLLAMA_URL_BASE        | Base URL for Ollama service            |
| openai_base        | COCO_OPENAI_URL_BASE        | Base URL for OpenAI-compatible API     |
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

### Language Models

Generate embeddings and interact directly with Ollama models:

```python
# Generate embeddings using integrated Ollama
embeddings = client.lm.create_embeddings(
    chunks=["text chunk 1", "text chunk 2"],
    model="nomic-embed-text"
)

# List available Ollama models
models = client.lm.list_ollama_models()
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
```

### RAG (Retrieval Augmented Generation)

End-to-end RAG with direct model access:

```python
# Retrieve relevant chunks
results = client.retrieve_chunks(
    query_texts=["What is the capital of France?"],
    n_results=5
)

# Generate answers using integrated models
answers, token_speeds = client.rag.generate_answers(
    queries=["What is the capital of France?"],
    context_chunks=[["Paris is the capital...", "Other context..."]],
    model="llama3.2:1b",
    pull_model=True  # Auto-download missing models
)
```

Key changes from previous version:

- Removed separate embedding service configuration
- Direct Ollama model integration through `LanguageModelClient`
- Simplified configuration by removing embedding-specific parameters
- Integrated embedding generation directly into LM module
- Added model management capabilities (list/pull models)

The rest of the documentation (batched processing, error handling, examples) remains valid with the updated integration.

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
