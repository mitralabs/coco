# DB API Service

A vector database service for document storage and retrieval using semantic similarity search.

## Overview

The DB API service provides a REST API for storing documents with vector embeddings and retrieving them based on semantic similarity. It uses PostgreSQL with the pgvector extension for efficient vector similarity search.

## Authentication

All endpoints require API key authentication. The API key must be provided in the request header:

```
X-API-Key: your_api_key
```

## API Endpoints

### Test Endpoint

Basic endpoint to test if the service is running.

- **URL**: `/test`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "success",
    "message": "Database service: Test endpoint accessed successfully"
  }
  ```

### Add Documents

Add documents with embeddings to the database.

- **URL**: `/add`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "documents": [
      {
        "text": "Document text content",
        "embedding": [0.1, 0.2, ...],
        "metadata": {
          "language": "en",
          "filename": "example.txt",
          "chunk_index": 0,
          "total_chunks": 10
        }
      }
    ]
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "added": 5,
    "skipped": 2
  }
  ```
- **Notes**:
  - Documents with text that already exists in the database will be skipped
  - Embeddings will be padded with zeros if they are smaller than the maximum embedding dimension

### Get Closest Documents

Retrieve documents closest to a given vector embedding.

- **URL**: `/get_closest`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "embedding": [0.1, 0.2, ...],
    "n_results": 5
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "count": 5,
    "results": [
      {
        "id": 1,
        "document": "Document text content",
        "metadata": {
          "language": "en",
          "filename": "example.txt",
          "chunk_index": 0,
          "total_chunks": 10
        },
        "distance": 0.123
      }
    ]
  }
  ```

### Get Multiple Closest Documents

Retrieve documents closest to multiple query embeddings in a single request.

- **URL**: `/get_multiple_closest`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "embeddings": [
      [0.1, 0.2, ...],
      [0.3, 0.4, ...]
    ],
    "n_results": 5
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "embedding_count": 2,
    "docs_per_embedding_count": 5,
    "results": [
      [
        {
          "id": 1,
          "document": "Document text content",
          "metadata": {
            "language": "en",
            "filename": "example.txt",
            "chunk_index": 0,
            "total_chunks": 10
          },
          "distance": 0.123
        }
      ]
    ]
  }
  ```

### Get All Documents

Retrieve all documents stored in the database.

- **URL**: `/get_all`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "success",
    "count": 100,
    "results": [
      {
        "id": 1,
        "document": "Document text content",
        "metadata": {
          "language": "en",
          "filename": "example.txt",
          "chunk_index": 0,
          "total_chunks": 10
        }
      }
    ]
  }
  ```

### Delete All Documents

Remove all documents from the database.

- **URL**: `/delete_all`
- **Method**: `DELETE`
- **Response**:
  ```json
  {
    "status": "success",
    "count": 100
  }
  ```

### Get Maximum Embedding Dimension

Get the maximum embedding dimension supported by the database.

- **URL**: `/max_embedding_dim`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "success",
    "max_embedding_dim": 768
  }
  ```

## Data Models

### Document

- `id`: Unique identifier (auto-generated)
- `text`: Document content (must be unique)
- `embedding`: Vector representation of document content
- `language`: Document language code
- `filename`: Source filename
- `chunk_index`: Index of chunk within the file
- `total_chunks`: Total number of chunks in the file

## Environment Variables

- `API_KEY`: Required. Authentication key for API access
- `EMBEDDING_DIM`: Dimension of the vector embeddings (default: 768)

## Usage Notes

- The service automatically pads embeddings that are smaller than the maximum dimension
- Documents with identical text content will be skipped during insertion
- The API uses cosine similarity for finding semantically similar documents

## Database Migrations

The DB API service uses Alembic for database migrations. All database models are defined in `app/models.py` and migrations are managed through Docker. Follow these steps to modify the database schema:

### Making Changes to Database Models

1. **Modify the models.py file**:
   Edit `app/models.py` to add, remove, or modify database columns or tables.

   Example:

   ```python
   # Adding a new column to the Document model
   class Document(Base):
       # ... existing columns ...
       new_column = Column(String, nullable=True)
   ```

2. **Generate a migration script**:
   Run the following command to auto-generate a migration script:

   ```bash
   docker compose run --rm db-api alembic revision --autogenerate -m "description of your change"
   ```

   This will create a new file in `app/migrations/versions/` with upgrade and downgrade functions.

   Note that Alembic generates the migration script from the difference between the (new) database schema defined in `models.py` and the current state of the actual database. So make sure the database is in appropriate state (all previous migrations applied).

3. **Apply the migration**:
   Run the following command to apply the migration:

   ```bash
   docker compose run --rm db-api alembic upgrade head
   ```

   This will update the database schema to the latest version.

4. **Verify the changes**:
   You can check the current database state with:
   ```bash
   docker compose run --rm db-api alembic current
   ```

### Common Alembic Commands

- **View migration history**:

  ```bash
  docker compose run --rm db-api alembic history
  ```

- **Downgrade to a specific version**:

  ```bash
  docker compose run --rm db-api alembic downgrade <revision_id>
  ```

- **Downgrade one version**:
  ```bash
  docker compose run --rm db-api alembic downgrade -1
  ```
