# Introduction to the Coco MCP Database Server

## What is the Model Context Protocol (MCP)?

The Model Context Protocol (MCP) is a standardized protocol that enables communication between Large Language Models (LLMs) and external services. It defines a structured way for applications to provide context, tools, and resources to LLMs, allowing them to perform actions that would be impossible with just a text-based interface.

MCP follows a client-server architecture:
- **Hosts**: LLM applications like Claude Desktop, Cursor, or other AI-powered tools
- **Clients**: Components within the hosts that initiate and maintain connections to MCP servers
- **Servers**: Independent services that expose data and functionality to LLMs through standardized interfaces

MCP supports two primary transport methods:
1. **Stdio (Standard Input/Output)**: Simple, process-based communication where the client spawns the server process and communicates via stdin/stdout. Best for local tools and Claude Desktop integration.
2. **HTTP/SSE (Server-Sent Events)**: Web-based communication where the server listens on a port and clients connect via HTTP. Better for remote or networked scenarios.

The protocol defines three core primitives:
- **Resources**: Read-only data sources (like GET endpoints) that provide contextual information to the LLM
- **Tools**: Functions or methods that perform actions (like POST endpoints) when invoked by the LLM
- **Prompts**: Pre-defined interaction templates that help guide LLM responses

## The Coco Project Overview

Coco is a project that facilitates storage, retrieval, and semantic search of text data. From examining the codebase, we understand it consists of several key components:

1. **Database API Service** (`services/db_api`): A FastAPI service that manages a PostgreSQL database with pgvector extension for storing and searching vector embeddings.
   - The database stores text documents along with their vector embeddings and metadata.
   - It provides endpoints for adding documents, retrieving documents by similarity, filtering by date, etc.

2. **Python SDK** (`python_sdk/src/coco`): A Python library that provides high-level access to various services including:
   - `LanguageModelClient` (`lm.py`): Handles embedding generation using either Ollama or OpenAI
   - `DbApiClient` (`db_api.py`): Client for interacting with the Database API
   - `ToolsClient` (`tools.py`): Defines tools for semantic search and other operations
   - Various other utilities for chunking, transcription, etc.

3. **Other Services**: The project includes additional services for text chunking, transcription, and orchestration based on the docker-compose file.

## Purpose of the Coco MCP Database Server

We're implementing an MCP server for Coco to expose the project's database and semantic search capabilities to LLMs through the MCP protocol. This will allow tools like Claude Desktop to directly:

1. Query the PostgreSQL database with standard SQL
2. Perform semantic vector searches using embeddings

This integration enables more powerful AI workflows, where the LLM can explore and analyze data stored in the Coco system. By bridging Coco's existing capabilities with LLM applications that support MCP, we create a powerful interface for AI-assisted data exploration and analysis.

## Reference Implementations

Our implementation will be based on two key reference sources:

1. **TypeScript PostgreSQL MCP Server** (`mcp-materials/postgres-mcp-server-reference-implementation-ts/index.ts`):
   - Provides a complete implementation of an MCP server for PostgreSQL
   - Exposes table schemas as resources (`postgres://host/table/schema`)
   - Contains an `execute_pgvector_query` tool that handles both standard and semantic queries by:
     - Accepting a SQL query, with an optional `semantic_string` parameter
     - Optionally getting an embedding for the semantic string via OpenAI's API (when provided)
     - Substituting the embedding into the query (if placeholder `$1` exists) and executing it
   - Uses stdio transport for compatibility with Claude Desktop

2. **Python MCP Test Server** (`mcp-materials/test-mcp-server`):
   - Demonstrates how to set up a Python-based MCP server
   - Provides a working Dockerfile and configuration for stdio transport
   - Shows how to structure the project with `uv` for dependency management

## Relevant Coco Components for Integration

Our implementation will integrate the following components from the Coco project:

1. **Vector Embedding Generation** (`python_sdk/src/coco/lm.py`):
   - The `LanguageModelClient` class (lines 19-565) provides methods for generating embeddings
   - Most importantly, the `embed` method (lines 133-142) which creates embeddings from text
   - This will replace the direct OpenAI API call in the reference implementation

2. **Semantic Search Tool** (`python_sdk/src/coco/tools.py`):
   - The `semantic_query` method (lines 236-293) demonstrates how to use the embedding with the database
   - Shows parameter handling, error handling, and result formatting

3. **Database Client** (`python_sdk/src/coco/db_api.py`):
   - The `get_closest` method (lines 41-49) shows how to query the database with embeddings
   - While we'll use direct database connections instead of this client, it provides useful reference for query structure

4. **Database Schema** (`services/db_api/app/models.py`):
   - The `Document` model shows how data is stored in the PostgreSQL database
   - Includes the vector embedding column that uses pgvector for similarity searches

## Technical Architecture

Our implementation will:

1. Use the FastMCP Python library to create a server with stdio transport for integration with Claude Desktop
2. Connect directly to the PostgreSQL database using asyncpg instead of going through the DB API service
3. Use the Coco SDK's embedding generation logic by mounting the SDK code into the container
4. Expose a single versatile query tool:
   - `execute_pgvector_query`: For executing both standard SQL queries and queries with embedded vector search (matching the reference implementation)
5. Expose schema information as resources to help the LLM understand the database structure

## Implementation Approach

We will use a Docker-based approach where:
1. The server container has access to the mounted Coco Python SDK
2. Environment variables provide configuration for database connection and embedding generation
3. The server will run using stdio transport via the `mcp run` command
4. Users can integrate with Claude Desktop by adding an entry to their configuration

## Design Decisions & Tradeoffs

1. **FastMCP vs Low-level MCP**: We're using FastMCP for rapid development and cleaner code, though this comes with some constraints compared to a fully custom implementation.

2. **Direct Database Access vs API Client**: We're accessing the PostgreSQL database directly rather than going through the DB API service. This is more efficient but creates a tighter coupling to the database schema.

3. **Stdio Transport**: We're using stdio transport because it's simpler for local integration and works well with Claude Desktop. However, this means the service won't be directly accessible over the network (though this could be added later).

4. **Code Mounting vs Package Integration**: We're mounting the Coco SDK code directly rather than packaging it, which simplifies development but creates a deployment dependency.

5. **Single Query Tool**: Following the reference implementation, we're using a single `execute_pgvector_query` tool that handles both standard SQL and semantic queries, avoiding redundancy and providing a cleaner interface for the LLM.

Now, let's proceed with the detailed implementation plan.

# Coco MCP Database Server Implementation Plan

Based on the requirements, reference implementations, Coco SDK structure, and MCP documentation, this plan outlines the steps to create an MCP server for the Coco project.

## Phase 1: Project Setup and Dependencies

1.  **Create Project Structure:**
    
    **What:** Create the main directory `services/mcp_coco_db_server/app` to hold the server code. Inside this directory, create the main server file, let's call it `coco_db_mcp_server.py`.
    
    **Why:** This organizes the server code within the existing `services` structure and separates it from configuration files like `pyproject.toml` and `Dockerfile` which will reside in the parent `mcp_coco_db_server` directory.
    
    *   [x] Create the main directory `services/mcp_coco_db_server/app`.
    *   [x] Create the main server file `services/mcp_coco_db_server/app/coco_db_mcp_server.py`.

2.  **Initialize `pyproject.toml`:**
    
    **What:** Create `services/mcp_coco_db_server/pyproject.toml`. Define the project name (e.g., `mcp-coco-db-server`), version, and dependencies.
    
    **Required Dependencies:**
    *   `mcp[cli]`: The core MCP Python SDK and its command-line tools (like `mcp run`).
    *   `asyncpg`: An efficient, asynchronous PostgreSQL driver suitable for use with `asyncio` and `FastMCP`.
    *   `python-dotenv`: (Optional but recommended) To load environment variables during development/testing.
    
    **Why:** `pyproject.toml` is standard for modern Python projects and essential for `uv` to manage dependencies during the Docker build process. `asyncpg` is chosen for compatibility with the async nature of MCP.
    
    *   [x] Create `services/mcp_coco_db_server/pyproject.toml`.
    *   [x] Define project metadata (name: `mcp-coco-db-server`, version, etc.).
    *   [x] Add `mcp[cli]` to dependencies.
    *   [x] Add `asyncpg` to dependencies.
    *   [x] Add `python-dotenv` to dependencies.

3.  **✓ CORRECTION: No Local Virtual Environment Setup**
    
    **What:** We will **NOT** create a local virtual environment or install dependencies locally. Instead, dependency installation will happen automatically during the Docker build process.
    
    **Why:** Since we've decided to test only in the Docker environment (not locally), there's no need to set up a local virtual environment. The Docker build process will handle dependency installation within the container.
    
    *   [x] ~~Navigate to `services/mcp_coco_db_server` directory.~~ (Not needed)
    *   [x] ~~Run `uv venv` (if needed).~~ (Will happen in Docker)
    *   [x] ~~Run `uv sync` to install dependencies and generate `uv.lock`.~~ (Will happen in Docker)

## Phase 2: Implement MCP Server Logic (`coco_db_mcp_server.py`)

1.  **Import Necessary Modules:**
    
    **What:** Import `FastMCP`, `Context` from `mcp.server.fastmcp`, `asyncpg`, `os` (for environment variables), `json`, `sys` (to modify path for SDK import), and relevant classes from the Coco SDK (e.g., `LanguageModelClient` - likely need to import from `/python_sdk/src`).
    
    **Why:** Brings in the required classes and functions for building the server, interacting with the database, handling environment variables, and using the Coco SDK.
    
    *   [x] Import `FastMCP`, `Context` from `mcp.server.fastmcp`.
    *   [x] Import `asyncpg`.
    *   [x] Import `os`.
    *   [x] Import `json`.
    *   [x] Import `sys`.
    *   [x] Import necessary classes from `/python_sdk/src` (e.g., `LanguageModelClient`).

2.  **Handle Python SDK Import:**
    
    **What:** Since the `python_sdk` directory will be mounted at `/python_sdk` inside the Docker container, add logic at the beginning of the script to ensure Python can find it. A simple approach is `sys.path.insert(0, '/python_sdk/src')`.
    
    **Why:** Allows the MCP server code to import modules from the mounted Coco SDK volume.
    
    *   [x] Add `sys.path.insert(0, '/python_sdk/src')` at the beginning of the script.

3.  **Instantiate `FastMCP`:**
    
    **What:** Create an instance: `mcp = FastMCP("coco-db-mcp-server")`.
    
    **Why:** This is the main object representing our MCP server.
    
    *   [x] Create server instance: `mcp = FastMCP("coco-db-mcp-server")`.

4.  **Implement Database Connection Lifespan:**
    
    **What:** Define an `asynccontextmanager` function (e.g., `db_lifespan`) similar to the examples in the MCP SDK docs.
    * Inside the manager, read the `DATABASE_URL` from the environment (`os.getenv`).
    * Use `asyncpg.create_pool(DATABASE_URL)` to establish a connection pool when the server starts.
    * `yield` a context dictionary containing the pool (e.g., `{'db_pool': pool}`).
    * In a `finally` block, call `pool.close()` to clean up when the server shuts down.
    * Pass this lifespan manager to the `FastMCP` instance: `mcp = FastMCP("coco-db-mcp-server", lifespan=db_lifespan)`.
    
    **Why:** This efficiently manages the database connection pool, making it available to all tool/resource requests via the `Context` object (`ctx.lifespan_context['db_pool']`) without reconnecting each time. It ensures proper setup and teardown.
    
    *   [x] Define an `asynccontextmanager` function `db_lifespan(server: FastMCP)`.
    *   [x] Read `DATABASE_URL` from `os.getenv`.
    *   [x] Create `asyncpg` pool: `pool = await asyncpg.create_pool(DATABASE_URL)`.
    *   [x] `yield {'db_pool': pool, ...}` (will add coco_client later).
    *   [x] Add `finally` block with `await pool.close()`.
    *   [x] Pass the lifespan manager to `FastMCP` initialization.

5.  **Implement Coco SDK Client Initialization:**
    
    **What:** Initialize the `LanguageModelClient` alongside the DB pool in the `db_lifespan` manager.
    * Read all necessary `COCO_*` environment variables within the lifespan manager.
    * Instantiate `coco_client = LanguageModelClient(...)` using these variables.
    * Yield `{'db_pool': pool, 'coco_client': coco_client}`.
    
    **Why:** Initializing in the lifespan makes the configured client readily available to any tool/resource that might need it via the context, similar to the DB pool, and centralizes the reading of environment variables.
    
    *   [x] Update `db_lifespan` manager.
    *   [x] Read required `COCO_*` and other related environment variables (e.g., `OPENAI_API_KEY`).
    *   [x] Add checks to ensure necessary environment variables are set.
    *   [x] Instantiate `coco_client = LanguageModelClient(...)` using environment variables.
    *   [x] Update the yielded context to `yield {'db_pool': pool, 'coco_client': coco_client}`.

6.  **Implement Resource: Get Schema:**
    
    **What:** Replicate the logic from `index.ts`.
    * Define a resource handler using `@mcp.resource("coco_db://schema/{table_name}")`.
    * The handler function (e.g., `get_table_schema(table_name: str, ctx: Context)`) will:
        * Get the DB pool: `pool = ctx.lifespan_context['db_pool']`.
        * Acquire a connection from the pool: `async with pool.acquire() as conn:`.
        * Execute the query `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1` using `conn.fetch(query, table_name)`.
        * Format the results as a JSON string.
        * Return the JSON string. Handle cases where the table doesn't exist.
    
    **Why:** Provides schema information to the LLM client, mirroring the reference implementation's functionality using asyncpg.
    
    *   [x] Define resource handler `@mcp.resource("coco_db://schema/{table_name}")` function `get_table_schema(table_name: str, ctx: Context)`.
    *   [x] Get DB pool from `ctx.lifespan_context`.
    *   [x] Acquire connection `async with pool.acquire() as conn:`.
    *   [x] Execute schema query (`SELECT column_name, data_type...`) using `conn.fetch()`.
    *   [x] Format results as JSON string.
    *   [x] Handle potential errors (e.g., table not found).
    *   [x] Return JSON string.

7.  **Implement Tool: Execute PgVector Query:**
    
    **What:** This is the core tool, directly matching the reference implementation. Combine the TS reference structure with Coco SDK embedding.
    * Define a tool handler: `@mcp.tool(name="execute_pgvector_query", description="Executes a read-only SQL query, optionally including vector similarity. Use $1 as the placeholder for the embedding vector if semantic_string is provided.")`.
    * Define parameters: `sql_query: str`, `semantic_string: Optional[str] = None`.
    * The handler function (e.g., `execute_pgvector_query(sql_query: str, semantic_string: Optional[str], ctx: Context)`) will:
        * **Input Validation:** Check if `$1` is in `sql_query`. If yes, `semantic_string` must be provided. If `semantic_string` is provided but `$1` is missing, log a warning but proceed.
        * **Get Embedding (if needed):**
            * If `semantic_string` is provided and `$1` is present:
                * Get the Coco client: `coco_client = ctx.lifespan_context['coco_client']`.
                * Generate embedding: `embedding_vector = coco_client.lm.embed(semantic_string)` (Note: `embed` might need to be made async or use `asyncio.to_thread` if it's synchronous).
                * Prepare `query_params = [embedding_vector]`.
            * Else:
                * `query_params = []`.
        * **Database Query:**
            * Get DB pool: `pool = ctx.lifespan_context['db_pool']`.
            * Acquire connection: `async with pool.acquire() as conn:`.
            * Start transaction: `async with conn.transaction(readonly=True, isolation='read_committed'):`.
            * Execute query: `results = await conn.fetch(sql_query, *query_params)`.
            * Format results to JSON string.
            * Return JSON string. Catch errors from embedding generation or database execution.
    
    **Why:** This tool provides a unified interface for both standard SQL queries and semantic vector searches, integrating the project's existing embedding infrastructure (`CocoClient`/`LanguageModelClient`) instead of directly calling OpenAI's API as in the reference implementation.
    
    *   [x] Define tool handler `@mcp.tool(name="execute_pgvector_query", ...)` function `execute_pgvector_query(sql_query: str, semantic_string: Optional[str], ctx: Context)`.
    *   [x] Add parameter type hints (`sql_query: str`, `semantic_string: Optional[str] = None`, `ctx: Context`).
    *   [x] Perform input validation (check `$1` vs `semantic_string` presence).
    *   [x] **If embedding needed:**
        *   [x] Get `coco_client` from `ctx.lifespan_context`.
        *   [x] Call `embedding_vector = coco_client.lm.embed(semantic_string)` (handle sync/async if needed, e.g., with `asyncio.to_thread`).
        *   [x] Prepare `query_params = [embedding_vector]`.
    *   [x] **Else:**
        *   [x] Set `query_params = []`.
    *   [x] **Database Query:**
        *   [x] Get DB pool from `ctx.lifespan_context`.
        *   [x] Acquire connection `async with pool.acquire() as conn:`.
        *   [x] Start read-only transaction `async with conn.transaction(readonly=True, ...):`.
        *   [x] Execute `sql_query` with `*query_params` using `conn.fetch()`.
        *   [x] Format results as JSON string.
        *   [x] Catch errors from embedding or DB query.
        *   [x] Return JSON string.

## Phase 3: Dockerization and Configuration

1.  **Create Dockerfile:**
    
    **What:** Create `services/mcp_coco_db_server/Dockerfile`. Use the stdio `Dockerfile` from `mcp-materials/test-mcp-server` as a template.
    * Use a Python base image (e.g., `python:3.13-slim`).
    * Use a multi-stage build.
    * **Builder Stage:** Install `uv`, copy `pyproject.toml` and `uv.lock`, run `uv sync` to install dependencies into a virtual environment (`.venv`).
    * **Runtime Stage:** Install `uv`, copy the `.venv` from the builder, copy the `coco_db_mcp_server.py` script (from `app/`), set `ENV PATH="/app/.venv/bin:${PATH}"` and `ENV PYTHONPATH="/app:/python_sdk/src"` (assuming server script is at `/app/coco_db_mcp_server.py` and SDK at `/python_sdk`).
    * Set the `CMD` to `["uv", "run", "mcp", "run", "app/coco_db_mcp_server.py"]`.
    
    **Why:** Creates a container image based on the test server example, ensuring `uv` is used for dependencies and the server is started using `mcp run` for stdio communication. Setting `PYTHONPATH` ensures imports from the base app directory and the mounted SDK work.
    
    *   [x] Create `services/mcp_coco_db_server/Dockerfile`.
    *   [x] Use `python:3.13-slim` (or chosen version) base image.
    *   [x] Implement multi-stage build.
    *   [x] **Builder Stage:** Install `uv`, copy `pyproject.toml`/`uv.lock`, run `uv sync` into `.venv`.
    *   [x] **Runtime Stage:** Install `uv`, copy `.venv`, copy `app/coco_db_mcp_server.py` to `/app/`.
    *   [x] Set `ENV PATH="/app/.venv/bin:${PATH}"`.
    *   [x] Set `ENV PYTHONPATH="/app:/python_sdk/src"`.
    *   [x] Set `CMD ["uv", "run", "mcp", "run", "app/coco_db_mcp_server.py"]`.

2.  **Implement Lifecycle Management:**
    
    **What:** Add proper process lifecycle management to ensure the container properly terminates when the client (e.g., Claude Desktop) exits.
    * Implement signal handlers for SIGTERM and SIGINT.
    * Add a watchdog process that detects when the parent process (stdin) closes.
    * Ensure all database connections and resources are properly closed on shutdown.
    
    **Why:** Currently, containers remain running when Claude Desktop quits, which should not be the case. Proper lifecycle management ensures resources are cleaned up properly.
    
    *   [ ] Add signal handlers for SIGTERM and SIGINT in the server script.
    *   [ ] Implement a watchdog process or mechanism to detect when the parent process terminates.
    *   [ ] Add proper shutdown sequence to close all connections and resources.
    *   [ ] Test that containers terminate when Claude Desktop exits.

3.  **Create `.dockerignore`:**
    
    **What:** Create `services/mcp_coco_db_server/.dockerignore`. Add entries like `.venv`, `__pycache__`, `.git`, etc.
    
    **Why:** Prevents unnecessary files from being copied into the Docker build context, speeding up builds and reducing image size.
    
    *   [x] Create `services/mcp_coco_db_server/.dockerignore`.
    *   [x] Add `.venv`, `__pycache__`, `.git`, etc.

4.  **Define Environment Variables:**
    
    **What:** Document the list of *all* environment variables needed by the container at runtime:
    * `DATABASE_URL`
    * `OPENAI_API_KEY` (or other relevant keys depending on `COCO_EMBEDDING_API`)
    * `COCO_CHUNK_URL_BASE` (if needed by CocoClient initialization/features used)
    * `COCO_DB_API_URL_BASE` (if needed...)
    * `COCO_TRANSCRIPTION_URL_BASE` (if needed...)
    * `COCO_OLLAMA_URL_BASE`
    * `COCO_OPENAI_URL_BASE`
    * `COCO_EMBEDDING_API`
    * `COCO_LLM_API`
    * `COCO_API_KEY`
    * `COCO_EMBEDDING_MODEL`
    
    **Why:** Makes configuration explicit and ensures all necessary secrets and connection details are provided when running the container.
    
    *   [x] List `DATABASE_URL`.
    *   [x] List `OPENAI_API_KEY` (and/or others based on `COCO_EMBEDDING_API`).
    *   [x] List all required `COCO_*` variables.
    *   [x] Add this list to a README or documentation file.

5.  **Define Volume Mount:**
    
    **What:** Document that the `python_sdk` directory from the host must be mounted to `/python_sdk` inside the container.
    
    **Why:** Provides the necessary Coco SDK code to the MCP server running inside the container.
    
    *   [x] Document the requirement to mount the host `python_sdk` directory to `/python_sdk` in the container.
    *   [x] Add this to a README or documentation file.

## Phase 4: Testing and Integration

1.  **Docker Build:**
    
    **What:** Build the image: `docker build -t coco/mcp-coco-db-server:latest -f Dockerfile .` (run from `services/mcp_coco_db_server`).
    
    **Why:** Creates the container image.
    
    *   [x] Run `docker build -t coco/mcp-coco-db-server:latest -f Dockerfile .` from `services/mcp_coco_db_server`.
    *   [x] Verify the build completes successfully.

2.  **Connection Stability Investigation and Improvement:**
    
    **What:** Investigate and fix the intermittent connection issues occurring with the database.
    * Implement proper connection pooling with optimal settings.
    * Add robust error handling and retry mechanisms for failed connections.
    * Implement proper connection recovery after network interruptions.
    * Add detailed logging for connection-related events to help diagnose issues.
    
    **Why:** The server connection currently is not stable and sometimes returns connection errors during queries. We need to find the root cause and make the connection to the Coco database more robust.
    
    *   [ ] Implement comprehensive connection error logging.
    *   [ ] Optimize connection pool settings (max connections, timeouts, etc.).
    *   [ ] Add connection health checks and automatic recovery.
    *   [ ] Implement exponential backoff retry mechanisms for failed queries.
    *   [ ] Test connection stability under various network conditions.

3.  **Enhance Tool Documentation:**
    
    **What:** Improve the documentation of the tools to help LLMs like Claude better understand when to use different query types.
    * Expand the tool description to clearly explain when to use:
        * Standard SQL queries only
        * Semantic queries only
        * Combined SQL and semantic queries
    * Include examples for each use case in the tool description.
    * Add detailed parameter descriptions with examples.
    
    **Why:** Better documentation helps Claude make more intelligent decisions about when to use each type of query, resulting in more efficient and accurate database interactions.
    
    *   [ ] Rewrite the tool description with clearer explanations of query types.
    *   [ ] Add specific examples for each query type in the tool description.
    *   [ ] Include detailed parameter descriptions with examples.
    *   [ ] Test the improved descriptions with Claude to verify understanding.

4.  **Add MCP Schema Resources:**
    
    **What:** Implement additional MCP resources to provide easy access to database schema information.
    * Implement `coco_db://tables` resource to list all tables.
    * Enhance the existing `coco_db://schema/{table_name}` resource.
    * Add a `coco_db://search/schema/{search_term}` resource to find tables/columns matching a search term.
    * Add a `coco_db://table/{table_name}/sample` resource to get sample data.
    
    **Why:** These resources will allow Claude to easily retrieve schema information without having to write SQL statements, making database exploration more efficient.
    
    *   [ ] Implement `coco_db://tables` resource.
    *   [ ] Enhance `coco_db://schema/{table_name}` resource.
    *   [ ] Add `coco_db://search/schema/{search_term}` resource.
    *   [ ] Add `coco_db://table/{table_name}/sample` resource.
    *   [ ] Test all resources with Claude to verify they provide useful information.

5.  **Docker Run & Claude Desktop Integration:**
    
    **What:** Configure `claude_desktop_config.json` similar to the example provided:
    ```json
    "coco-db-mcp-server": {
      "command": "docker",
      "args": [
        "run",
        "-i",                   // Essential for stdio
        "--rm",
        "-e", "DATABASE_URL=postgresql://user:pass@host:port/db",
        "-e", "OPENAI_API_KEY=...",
        "-e", "COCO_OLLAMA_URL_BASE=http://host.docker.internal:11434", // Example
        "-e", "COCO_OPENAI_URL_BASE=...",
        "-e", "COCO_EMBEDDING_API=...",
        // ... other COCO_ env vars ...
        "-v", "/path/to/host/python_sdk:/python_sdk", // Mount the SDK
        "coco/mcp-coco-db-server:latest"
      ]
    }
    ```
    Replace placeholders with actual values. Ensure the path to `python_sdk` on the host is correct.
    
    **Why:** This defines how Claude Desktop will launch and interact with the containerized MCP server, providing all necessary configuration and code via environment variables and volume mounts.
    
    *   [x] Create/update the `coco-db-mcp-server` entry in `claude_desktop_config.json`.
        *   Use `command: "docker"`.
        *   Include `run`, `-i`, `--rm`.
        *   Add all required `-e VAR=value` flags for environment variables.
        *   Add the `-v /path/to/host/python_sdk:/python_sdk` volume mount.
        *   Specify the image `coco/mcp-coco-db-server:latest`.
    *   [x] Restart Claude Desktop.
    *   [x] Check Claude Desktop MCP logs for errors.
    *   [x] Verify the server connects and the `execute_pgvector_query` tool appears.
    *   [x] Test executing both standard SQL and semantic vector queries via Claude chat.

## Phase 5: Implement Structured Persistent Logging

**Goal:** Implement a robust, structured, persistent logging system using Python's standard `logging` library, outputting JSON logs to rotating files for easier analysis, debugging, and potential integration with log analysis tools or databases.

1.  **✓ Add Logging Dependencies:**
    *   **What:** Add `python-json-logger` to the dependencies in `services/mcp_coco_db_server/pyproject.toml`.
    *   **Why:** Provides a standard way to format log records as JSON strings.
    *   **Action:**
        *   [x] Edit `pyproject.toml`.
        *   [x] Add `"python-json-logger"` under `[project.dependencies]`.
        *   [x] Note: Docker build will need to be re-run to include this dependency via `uv sync`.

2.  **✓ Configure Logging Setup:**
    *   **What:** Replace the basic `logging.basicConfig` call with `logging.dictConfig`. Define a configuration dictionary that sets up a root logger, a JSON formatter, and a rotating file handler. Ensure console logging (to stderr) is still available for basic runtime feedback, perhaps with a simpler format.
    *   **Why:** `dictConfig` provides a more structured and flexible way to configure logging compared to basicConfig. Separating file and console handlers allows for different formatting and levels. JSON formatting makes logs machine-readable. Rotating files prevent logs from consuming excessive disk space.
    *   **Action:**
        *   [x] In `coco_db_mcp_server.py`, remove the `logging.basicConfig` call.
        *   [x] Import `logging.config`, `logging.handlers`.
        *   [x] Define a `LOGGING_CONFIG` dictionary.
            *   [x] Define `version: 1`.
            *   [x] Define `disable_existing_loggers: False`.
            *   [x] Define a `formatters` section:
                *   [x] `json_formatter`: Uses `pythonjsonlogger.jsonlogger.JsonFormatter`, defining the desired standard fields (e.g., `%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d %(funcName)s`) and potentially custom fields if needed later. Use ISO 8601 format for timestamps (`datefmt='iso8601'`).
                *   [x] `simple_formatter`: A standard `logging.Formatter` for console output (e.g., `%(asctime)s - %(levelname)s - %(name)s - %(message)s`).
            *   [x] Define a `handlers` section:
                *   [x] `stderr_handler`: A `logging.StreamHandler` using `sys.stderr` and `simple_formatter`. Set level (e.g., `INFO` or `ERROR`).
                *   [x] `rotating_file_handler`: A `logging.handlers.TimedRotatingFileHandler`. Configure `filename` (e.g., `/app/logs/mcp_server.log` - ensure the directory exists or is created), `maxBytes`, `backupCount`, `encoding='utf-8'`, and use `json_formatter`. Set level (e.g., `INFO` or `DEBUG`).
            *   [x] Define a `loggers` section for specific loggers if needed (e.g., `asyncpg`), setting their levels.
            *   [x] Define the `root` logger configuration: Set `level` (e.g., `INFO`), add both `stderr_handler` and `rotating_file_handler` to `handlers`.
        *   [x] Call `logging.config.dictConfig(LOGGING_CONFIG)` early in the script's execution (e.g., near the top).
        *   [x] Ensure the log directory (e.g., `/app/logs`) is created in the Dockerfile or handled appropriately.

3.  **Update Logging Calls:**
    *   **What:** Review all existing `logger.error(...)` calls. Change them to use appropriate levels (`logger.info`, `logger.warning`, `logger.error`, `logger.debug`). Pass structured data using the `extra` dictionary parameter where appropriate.
    *   **Why:** Using correct log levels improves filtering and understanding. Passing data via `extra` allows the JSON formatter to automatically include custom fields defined in the format string.
    *   **Action:**
        *   [ ] Review every `logger.*` call in `coco_db_mcp_server.py`.
        *   [ ] Change levels where appropriate (e.g., successful operations become `INFO`, potential issues `WARNING`, actual errors `ERROR`).
        *   [ ] For key events (tool start/end, DB query start/end, embedding start/end), add structured information via `extra`.
            *   Example Tool Start: `logger.info("Starting tool execution", extra={"event_type": "tool_call_start", "tool_name": "execute_pgvector_query", "tool_input": {"sql_query": sql_query, "semantic_string_present": bool(semantic_string)}})`
            *   Example Tool Error: `logger.error("Tool execution failed", extra={"event_type": "tool_call_error", "tool_name": "execute_pgvector_query", "error_details": {"type": type(e).__name__, "message": str(e)}, "tool_input": {...}})`
            *   Example Tool Success: `logger.info("Tool execution successful", extra={"event_type": "tool_call_success", "tool_name": "execute_pgvector_query", "result_summary": {"row_count": len(formatted_results)}, "duration_ms": ...})` (Calculate duration).
        *   [x] Add `try...except...finally` blocks around key operations (like the main tool execution logic) to capture start time, calculate duration, and log success/failure consistently.
        *   **Progress:** Logging updated for `handle_terminate`, `db_lifespan`, `get_table_schema`, and `execute_pgvector_query`.

4.  **Refine Logged Information:**
    *   **What:** Ensure sensitive information (like full API keys, potentially sensitive data in query results) is not logged directly in plain text. Log summaries or indicators instead where appropriate (e.g., log `"api_key_present": True` instead of the key itself). Ensure the structured error details captured (especially for SQL errors) include the necessary components (error message, query, hints) for the RAG use case.
    *   **Why:** Prevents accidental exposure of sensitive data in logs while still providing enough context for debugging and analysis. Ensures the logs fulfill the requirements for the error analysis use case.
    *   **Action:**
        *   [ ] Review all data being passed to `logger.*` calls and the `extra` dictionary.
        *   [ ] Mask or summarize sensitive data (API keys, potentially large query results).
        *   [ ] Verify that the `error_details` structure for SQL errors includes `type`, `message`, `query`, and `hints`.
        *   [ ] Ensure inputs (`tool_input`) are logged comprehensively on error.

5.  **Docker Volume for Logs:**
    *   **What:** Document the need for users to mount a volume to the log directory (e.g., `-v /path/to/host/logs:/app/logs`) when running the container if they want logs to persist outside the container lifecycle. Update the example `docker run` command in the documentation/README.
    *   **Why:** Allows logs to be collected and analyzed even after the container stops.
    *   **Action:**
        *   [ ] Add documentation explaining the log file location (`/app/logs/mcp_server.log`) inside the container.
        *   [ ] Add instructions and an example for mounting a host directory to `/app/logs` using `docker run -v ...`.
        *   [ ] Update the example `claude_desktop_config.json` snippet to include the volume mount for logs.

6.  **Testing:**
    *   **What:** Rebuild the Docker image. Run the container integrated with Claude Desktop. Trigger various scenarios: successful queries (SQL and semantic), schema requests, queries with syntax errors, queries causing other database errors, configuration errors (if possible). Check both `stderr` output and the content/structure of the JSON log file(s) created in the mounted volume.
    *   **Why:** Verifies that the logging configuration works as expected, captures the necessary information in the correct format, rotates files, and handles errors correctly.
    *   **Action:**
        *   [ ] Rebuild the Docker image (`docker build ...`).
        *   [ ] Run the container using the updated `docker run` command (or Claude Desktop config) including the log volume mount.
        *   [ ] Perform test interactions using Claude Desktop.
        *   [ ] Verify `stderr` output shows simplified logs.
        *   [ ] Inspect the JSON log file(s) in the host directory.
        *   [ ] Validate the JSON structure, content, log levels, and file rotation.

## Phase 6: Integration with Coco Agents and Production Deployment

1.  **Create MCPToolsAdapter Class:**
    
    **What:** Create a new file `python_sdk/src/coco/mcp_client.py` that implements an adapter between MCP servers and the Coco tools system. This adapter should provide:
    * An `MCPConnection` class to manage connections to MCP servers (supporting both stdio and HTTP/SSE transports)
    * An `MCPToolsAdapter` class to discover and convert MCP tools into Coco-compatible tools
    * A tool execution proxy that routes tool calls from `ToolsClient` to the appropriate MCP server
    
    **Why:** This adapter allows the Coco agent system to seamlessly use tools provided by MCP servers. By abstracting the connection and protocol details, we can provide a unified interface for local and MCP-based tools.
    
    *   [x] Create `python_sdk/src/coco/mcp_client.py` file.
    *   [x] Implement `MCPConnection` class with support for stdio and HTTP/SSE transports.
    *   [x] Implement connection error handling with automatic reconnection.
    *   [x] Implement `MCPToolsAdapter` class with tool discovery and conversion.
    *   [x] Add tool execution proxy with proper error propagation.
    *   [x] Add configurable connection timeouts and retry settings.
    *   [x] Add proper resource cleanup on shutdown.

2.  **Extend ToolsClient to Support MCP Tools:**
    
    **What:** Modify `python_sdk/src/coco/tools.py` to integrate with the MCPToolsAdapter. This involves:
    * Updating the `ToolsClient` constructor to accept an optional `mcp_adapter` parameter
    * Adding a new `_register_mcp_tools()` method to discover and register MCP tools
    * Extending `get_tools()` to combine locally defined tools with MCP-provided tools
    * Modifying `execute_tool()` to route calls to either local methods or the MCP adapter based on the tool's origin
    
    **Why:** By extending the existing `ToolsClient` class, we maintain backward compatibility while adding MCP capabilities. This provides a unified interface for tool discovery and execution, abstracting the source of the tools from the agent.
    
    *   [ ] Update `ToolsClient.__init__()` to accept an optional `mcp_adapter` parameter.
    *   [ ] Implement `_register_mcp_tools()` method for tool discovery and registration.
    *   [ ] Extend `get_tools()` to include both local and MCP tools.
    *   [ ] Update `execute_tool()` to route calls to the appropriate handler.
    *   [ ] Add tool conversion logic to transform between MCP and Coco formats.
    *   [ ] Implement tool priority/conflict resolution when tools with the same name exist.

3.  **Implement Comprehensive Error Handling:**
    
    **What:** Create robust error handling for MCP tool execution, focusing on reliability and informative error messages. This involves:
    * Creating a configurable `RetryPolicy` class that implements exponential backoff
    * Adding proper exception hierarchies for different types of failures (connection, execution, timeout)
    * Implementing detailed error logging with context about the failed operation
    * Adding retry logic for recoverable errors like network timeouts or rate limits
    
    **Why:** Robust error handling is essential for production use, especially when dealing with network operations and external API calls. By properly categorizing and handling different error types, we can improve reliability and provide better diagnostics.
    
    *   [ ] Create a configurable `RetryPolicy` class with exponential backoff.
    *   [ ] Define exception hierarchies for different error categories.
    *   [ ] Implement error handling with context-specific error messages.
    *   [ ] Add retry logic for transient failures (network, rate limits).
    *   [ ] Integrate error handling with the existing logging system.
    *   [ ] Add error details propagation to agents for better diagnostics.

4.  **Implement Asynchronous Execution Support:**
    
    **What:** Add proper asynchronous execution support to both the MCPToolsAdapter and ToolsClient. This includes:
    * Implementing an `async_execute_tool()` method in ToolsClient that mirrors `execute_tool()`
    * Adding concurrent execution capabilities to handle multiple tool calls
    * Ensuring proper error propagation in asynchronous contexts
    * Integrating with `async_chat()` in AgentClient for seamless async operation
    
    **Why:** Asynchronous execution is crucial for maintaining responsiveness, especially when dealing with potentially slow operations like embedding generation. Proper async support allows the agent to work efficiently with long-running tool calls.
    
    *   [ ] Add `async_execute_tool()` method to `ToolsClient`.
    *   [ ] Implement proper async/await patterns throughout the execution path.
    *   [ ] Add timeout handling for async operations.
    *   [ ] Ensure compatibility with `AgentClient.async_chat()`.
    *   [ ] Add error handling specific to asynchronous execution.

5.  **Implement Concurrency Control:**
    
    **What:** Create concurrency control mechanisms to manage parallel tool executions. This involves:
    * Implementing a `SemaphoreManager` class to limit concurrent operations
    * Adding a configurable global limit for all concurrent requests
    * Supporting per-service limits for different types of operations (API calls, database queries)
    * Integrating with the existing batched parallel execution system
    
    **Why:** Controlled concurrency is essential for reliable operation, preventing resource exhaustion and API rate limit violations. A well-designed concurrency system allows efficient parallel execution while maintaining system stability.
    
    *   [ ] Create a `SemaphoreManager` class for concurrency control.
    *   [ ] Add global and per-service concurrency limits.
    *   [ ] Integrate with `batched_parallel()` in `async_utils.py`.
    *   [ ] Implement proper queuing for requests that exceed concurrency limits.
    *   [ ] Add monitoring of active/pending requests.

6.  **Add Configuration Framework:**
    
    **What:** Create a unified configuration system for all MCP and agent-related settings. This includes:
    * Implementing a central configuration module that handles various setting sources
    * Supporting environment variables, config files, and programmatic settings
    * Adding type validation for all configuration settings
    * Providing sensible defaults and documentation for all options
    
    **Why:** A centralized configuration system ensures consistent settings across components, simplifies deployment, and makes it easier to customize behavior. Proper validation prevents misconfiguration and improves reliability.
    
    *   [ ] Create a centralized configuration module.
    *   [ ] Define settings schemas with proper type annotations.
    *   [ ] Add support for multiple configuration sources.
    *   [ ] Implement validation and helpful error messages.
    *   [ ] Add documentation for all configuration options.

7.  **Integrate MCP Tools with AgentClient:**
    
    **What:** Update `AgentClient` to seamlessly work with MCP-provided tools. This involves:
    * Modifying `AgentClient.__init__()` to accept MCP configuration options
    * Adding initialization logic to set up MCP connections when needed
    * Ensuring compatibility between MCP tools and the language model's tool-calling capabilities
    * Supporting batch execution of MCP tools in `chat_multiple()`
    
    **Why:** Seamless integration with AgentClient ensures that MCP tools can be used in any agent-based workflow without requiring special handling. This maintains the simplicity of the API while adding powerful capabilities.
    
    *   [ ] Update `AgentClient.__init__()` to support MCP options.
    *   [ ] Add initialization logic for MCP connections.
    *   [ ] Ensure MCP tools work with `chat()`, `async_chat()`, and tool-calling.
    *   [ ] Support batch execution of MCP tools in `chat_multiple()`.
    *   [ ] Add proper cleanup of MCP resources in the agent lifecycle.

8.  **Add MCP Server to Docker Compose:**
    
    **What:** Integrate the MCP server container into the Coco services docker-compose setup to make it available for both human users and automated agents.
    * Add a new service definition to the `docker-compose.yml` file
    * Configure environment variables, dependencies, and volume mounts
    * Add health checks and appropriate restart policies
    * Configure networking to allow the container to communicate with both external clients and internal services
    
    **Why:** Including the MCP server in the standard docker-compose setup ensures it's always available when Coco services are running, simplifying deployment and ensuring consistent availability.
    
    *   [ ] Add MCP server service to `docker-compose.yml`.
    *   [ ] Configure environment variables and dependencies.
    *   [ ] Set up volume mounts for the Python SDK.
    *   [ ] Add health checks and restart policies.
    *   [ ] Configure networking for both external and internal access.

9.  **Create Integration Tests:**
    
    **What:** Develop comprehensive tests to verify the integration between Coco agents and the MCP server.
    * Write unit tests for MCPToolsAdapter and extended ToolsClient
    * Create integration tests that verify end-to-end operation
    * Add tests for error handling, retries, and connection recovery
    * Create performance tests to validate concurrency controls
    
    **Why:** Thorough testing ensures the reliability of the integration, verifies error handling mechanisms, and establishes performance characteristics. This is essential for confident production deployment.
    
    *   [ ] Write unit tests for `MCPToolsAdapter` and updated `ToolsClient`.
    *   [ ] Create integration tests for end-to-end operation.
    *   [ ] Add specific tests for error handling and recovery.
    *   [ ] Implement performance tests for concurrent execution.
    *   [ ] Add tests for configuration validation.

10. **Create Documentation and Examples:**
    
    **What:** Prepare comprehensive documentation and examples for using the MCP integration.
    * Update the SDK documentation to describe MCP integration
    * Create example scripts demonstrating common usage patterns
    * Document all configuration options and their effects
    * Provide troubleshooting guides for common issues
    
    **Why:** Good documentation is essential for adoption, helping users understand how to effectively use the MCP integration. Examples demonstrate best practices and common patterns, accelerating development.
    
    *   [ ] Update SDK documentation with MCP integration details.
    *   [ ] Create example scripts for common usage patterns.
    *   [ ] Document configuration options and their effects.
    *   [ ] Provide troubleshooting guides for common issues.
    *   [ ] Add API reference documentation for all new classes and methods.

## Implementation Findings and Challenges

During the implementation of the Coco MCP Database Server, we encountered several challenges and made important discoveries that might be useful for future MCP server implementations:

1. **Dependency Management Challenges**:
   - **Missing Dependencies**: The initial dependency list was incomplete - we needed to add `tqdm`, `ollama`, and `numpy`, which are used by the Coco SDK for embedding generation and vector handling.
   - **Build Process Issues**: We encountered problems with the Docker build process when it tried to build our package. This was resolved by adding the `--no-install-project` flag to the `uv sync` command, which installs dependencies without trying to build the package itself (avoiding the need for a README.md file).

2. **MCP Resource Implementation**:
   - **URI Parameter Matching**: We discovered that MCP resource handlers are very strict about parameter matching - the function parameters must exactly match the URI parameters. This means we couldn't directly access the context in resource handlers.
   - **Context Access Patterns**: For tools, we must use `ctx.request_context.lifespan_context` pattern to access resources from the lifespan, not simply `ctx.lifespan_context`.
   - **Different Patterns for Resources vs Tools**: Due to these limitations, we implemented different access patterns:
     - For tools: Use context-based access to shared resources (connection pool, embedding client)
     - For resources: Create direct database connections for each request

3. **Vector Database Integration**:
   - **pgvector Syntax**: The specific database implementation required PostgreSQL's type-casting syntax (`$1::vector`) rather than a function-call syntax (`vector($1)`).
   - **Database-Specific Vector Operations**: Vector operations can vary significantly between different PostgreSQL deployments with pgvector. We needed to adapt our implementation to use the specific syntax supported by our database.
   - **Type Handling**: We implemented a custom vector type codec to properly handle vector data between Python and PostgreSQL.

4. **LLM-Database Interaction Design**:
   - **Error Messaging**: We significantly improved error handling to provide Claude with detailed, educational error messages that help it learn the correct syntax.
   - **Tool Description**: We found that providing detailed examples in the tool description is much more effective than trying to parse and modify SQL on the backend. This leverages Claude's natural language understanding.
   - **Parameter Passing**: The most reliable way to pass vector embeddings to the database was to let asyncpg handle the conversion with proper type hints.

5. **Process Lifecycle Management**:
   - **Process Monitoring**: We implemented a watchdog process that detects when Claude Desktop quits and initiates proper server shutdown.
   - **Signal Handling**: We added proper signal handlers for SIGTERM and SIGINT to ensure the server shuts down gracefully.
   - **Cleanup Logic**: We enhanced the cleanup logic to ensure all resources are properly released on shutdown.

6. **Debugging and Logging**:
   - **MCP Protocol Constraints**: We learned that all logging must be done to stderr (not stdout) as stdout is reserved for MCP protocol messages.
   - **Enhanced Logging**: Detailed structured logging was essential for debugging interactions between Claude, the MCP server, and the database.

These findings highlight that implementing MCP servers requires careful attention to the interaction between LLMs, the protocol specifications, and the underlying systems being integrated. The most successful approach focused on making the tool intuitive for Claude to use, with robust error handling that facilitates learning, rather than trying to anticipate and handle all possible query variations in the backend code.

By providing Claude with clear guidance on correct syntax and detailed error messages when mistakes occur, we created a learning feedback loop that improves the quality of queries over time. This approach leverages Claude's natural language understanding capabilities while working within the technical constraints of the underlying systems.
