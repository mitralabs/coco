# Coco MCP Database Server

An MCP server that provides SQL query and semantic search capabilities for the Coco database. This server exposes:

1. **Schema information** as resources (via `coco_db://schema/{table_name}`)
2. **Query execution** as a tool (via `execute_pgvector_query`)

## Features

- Retrieve database schema information
- Execute standard SQL queries
- Execute semantic vector searches using the pgvector extension

## Configuration

**Persistent Logs:** 
The server writes JSON logs to `/_data/mcp_logs` within this repository. The directory is mounted during the compose process.


## Usage with Claude Desktop

To configure Claude Desktop to use this MCP server, add the following to your `claude_desktop_config.json` file:

```json
"coco-db-mcp-server": {
    "command": "bash",
    "args": [
      "-c",
      "docker attach coco_mcp_server"
      ]
  }
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