# Coco MCP Database Server

An MCP server that provides SQL query and semantic search capabilities for the Coco database. This server exposes:

1. **Schema information** as resources (via `coco_db://schema/{table_name}`)
2. **Query execution** as a tool (via `execute_pgvector_query`)

## Features

- Retrieve database schema information
- Execute standard SQL queries
- Execute semantic vector searches using the pgvector extension
- Utilizes the Coco SDK for embedding generation

## Configuration

### Environment Variables

The server requires the following environment variables:

| Environment Variable | Description | Required | Example |
|---------------------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Yes | `postgresql://user:pass@host:5432/dbname` |
| `COCO_EMBEDDING_API` | Which embedding API to use (`ollama` or `openai`) | Yes | `openai` |
| `COCO_LLM_API` | Which LLM API to use (`ollama` or `openai`) | Yes | `openai` |
| `COCO_OLLAMA_URL_BASE` | Base URL for Ollama API | Only if using Ollama | `http://host.docker.internal:11434` |
| `COCO_OPENAI_URL_BASE` | Base URL for OpenAI API | Only if using OpenAI | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | API key for OpenAI | Only if using OpenAI | `sk-...` |
| `COCO_EMBEDDING_MODEL` | Model to use for embeddings | Recommended | `BAAI/bge-m3` |
| `COCO_API_KEY` | API key for Coco services | Optional | |

### Volume Mount

The server requires the Coco Python SDK to be mounted to the `/python_sdk` directory in the container. When running with Docker, use the `-v` flag:

```bash
-v /path/to/host/python_sdk:/python_sdk
```

Where `/path/to/host/python_sdk` is the absolute path to the Python SDK on your host machine.

## Usage with Claude Desktop

To configure Claude Desktop to use this MCP server, add the following to your `claude_desktop_config.json` file:

```json
"coco-db-mcp-server": {
  "command": "docker",
  "args": [
    "run",
    "-i",
    "--rm",
    "-e", "DATABASE_URL=postgresql://user:pass@host.docker.internal:5432/dbname",
    "-e", "COCO_EMBEDDING_API=openai",
    "-e", "COCO_LLM_API=openai",
    "-e", "COCO_OPENAI_URL_BASE=https://api.openai.com/v1",
    "-e", "OPENAI_API_KEY=your_openai_api_key",
    "-e", "COCO_EMBEDDING_MODEL=BAAI/bge-m3",
    "-v", "/absolute/path/to/python_sdk:/python_sdk",
    "coco/mcp-coco-db-server:latest"
  ]
}
```

### Using with Ollama

If you're using Ollama for embeddings instead of OpenAI, adjust your configuration:

```json
"coco-db-mcp-server": {
  "command": "docker",
  "args": [
    "run",
    "-i",
    "--rm",
    "-e", "DATABASE_URL=postgresql://user:pass@host.docker.internal:5432/dbname",
    "-e", "COCO_EMBEDDING_API=ollama",
    "-e", "COCO_LLM_API=ollama",
    "-e", "COCO_OLLAMA_URL_BASE=http://host.docker.internal:11434",
    "-e", "COCO_EMBEDDING_MODEL=BAAI/bge-m3",
    "-v", "/absolute/path/to/python_sdk:/python_sdk",
    "coco/mcp-coco-db-server:latest"
  ]
}
```

Note: `host.docker.internal` is used to access services running on the host from within Docker containers.

## Building

To build the Docker image:

```bash
docker build -t coco/mcp-coco-db-server:latest -f Dockerfile .
```

## Example Queries

Once the server is running and connected to Claude Desktop, you can execute queries like:

```
# Standard SQL query
execute_pgvector_query(sql_query="SELECT * FROM documents LIMIT 5")

# Semantic vector search
execute_pgvector_query(
  sql_query="SELECT * FROM documents ORDER BY embedding <-> $1 LIMIT 5",
  semantic_string="Tell me about machine learning"
) 