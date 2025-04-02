# Building and Testing an MCP Server: SSE vs Stdio

This guide details how to create, run, test, and deploy a simple MCP test server using two different communication methods: HTTP/SSE (Server-Sent Events) and Stdio (Standard Input/Output). You'll learn how to:

1.  Implement a basic MCP server script.
2.  Run and test the server locally using both SSE (with `uvicorn`) and stdio (with `mcp run`).
3.  Test both setups using the `mcp dev` Inspector tool.
4.  Containerize the server using Docker for both SSE and stdio configurations.
5.  Run and test the Docker containers.
6.  Configure Claude Desktop to connect to both Dockerized versions.
7.  Troubleshoot common issues like port conflicts.

## Prerequisites

-   Python 3.8+ installed
-   [uv](https://docs.astral.sh/uv/) for package management (recommended)
-   Docker installed
-   Claude Desktop application installed
-   Basic familiarity with Python, Docker, and command-line operations

## Part 1: Creating the Server Script

### Step 1.1: Set Up Project Directory

```bash
# Create project directory (if not already done)
mkdir -p ~/mcp-server-builder
cd ~/mcp-server-builder

# Initialize uv project (if not already done)
uv init

# Create virtual environment and activate it (if not already done)
uv venv
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```

### Step 1.2: Define Dependencies (`pyproject.toml`)

Ensure your `pyproject.toml` includes the necessary dependencies. Create or update it:

```toml
[project]
name = "mcp-server-builder"
version = "0.1.0"
description = "MCP Test Server Example"
readme = "README.md"
requires-python = ">=3.13" # Match this with your desired Python version
dependencies = [
    "mcp[cli]>=1.6.0",
    "starlette>=0.46.1",
    "uvicorn[standard]>=0.34.0",
    # Add other dependencies like httpx if your tools need them
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Install/update dependencies using `uv`:

```bash
uv sync
```

### Step 1.3: Create Server Script (`test_server_script.py`)

Create a file named `test_server_script.py`. **Crucially, do not add an `if __name__ == "__main__":` block that runs `uvicorn` yet.**

```python
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

# Create an MCP server instance
mcp = FastMCP("mcp-test-server")

# Add a simple tool that echoes the query
@mcp.tool()
def echo_query(client_query: str) -> str:
    """Echo the query sent by the client

    Args:
        client_query: The query to echo back
    """
    return f"Hello, you successfully sent a query to this test mcp server! Your query was: {client_query}"

# --- For SSE Setup ---
# Create a Starlette ASGI application that mounts the MCP server's SSE app
# This 'app' object is what uvicorn will serve for SSE.
app = Starlette(
    routes=[
        Mount('/', app=mcp.sse_app()),
    ]
)

# --- For Stdio Setup ---
# No extra code needed here. When run via 'mcp run', the library
# will automatically use the 'mcp' instance with stdio if 'app' isn't run by uvicorn.
```

This script defines:
1.  An `mcp` instance with one tool.
2.  A Starlette `app` object specifically for the SSE transport.

## Part 2: Local Testing - SSE (HTTP)

This method runs the server as a web service listening on a port.

### Step 2.1: Run the Server with Uvicorn

Use `uvicorn` to run the `app` object defined in your script:

```bash
uvicorn test_server_script:app --host 0.0.0.0 --port 8765 --reload
```

-   `test_server_script:app`: Tells uvicorn to find the `app` object in the `test_server_script.py` file.
-   `--host 0.0.0.0`: Makes the server accessible from outside localhost (important for Docker later).
-   `--port 8765`: Specifies the listening port.
-   `--reload`: Automatically restarts the server when code changes (useful for development).

The server is now running and listening for HTTP/SSE connections on port 8765.

### Step 2.2: Test with MCP Inspector (SSE Mode)

1.  **Create a dummy script:** Since `mcp dev` requires a file argument, create a minimal empty file, e.g., `mock_script.py`.
    ```bash
    touch mock_script.py
    ```
2.  **Run `mcp dev`:** Launch the Inspector UI, pointing it at the dummy script (this command *will* try and fail to connect via stdio to `mock_script.py`, but the UI will still launch):
    ```bash
    mcp dev mock_script.py
    ```
3.  **Connect in UI:**
    *   In the Inspector web UI that opens, select **SSE** as the Transport Type.
    *   Enter the URL: `http://localhost:8765` (or `http://localhost:8765/sse` if needed).
    *   Click **Connect**.

You should now be connected to your running Uvicorn server via SSE and can test the `echo_query` tool.

## Part 3: Local Testing - Stdio

This method runs the server communicating via standard input/output, often used for direct integration with tools like Claude Desktop or the Inspector's default mode.

### Step 3.1: Run the Server with `mcp run`

Use the `mcp run` command (provided by `mcp[cli]`) which defaults to stdio:

```bash
# Ensure you are in the activated virtual environment (.venv)
mcp run test_server_script.py
```

-   `mcp run` loads the script, finds the `mcp` instance, and runs it using the stdio transport.
-   The terminal will likely appear to hang – this is normal, as the server is waiting for input on stdin.

### Step 3.2: Test with MCP Inspector (Stdio Mode)

1.  **Stop** any previous `mcp run` process (`Ctrl+C`).
2.  **Run `mcp dev`:** Launch the Inspector, telling it to manage the script directly via stdio:
    ```bash
    mcp dev test_server_script.py
    ```
3.  **Automatic Connection:** The Inspector UI will open, and it should automatically connect to the server process it launched using the stdio transport.

You can now test the `echo_query` tool via the Inspector's default stdio connection.

## Part 4: Containerizing with Docker - SSE Setup

This creates a Docker image that runs the server using Uvicorn and listens on a port.

### Step 4.1: Create SSE Dockerfile (`Dockerfile.sse`)

Create a file named `Dockerfile.sse`:

```dockerfile
# ---- Builder Stage ----
FROM python:3.13-slim AS builder # Use Python version >= requires-python
WORKDIR /app

# Install curl for downloading uv
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv using the recommended script
SHELL ["/bin/bash", "-c"]
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Create a virtual environment
RUN . /root/.local/bin/env && uv venv .venv --seed
ENV PATH="/app/.venv/bin:${PATH}" # Add venv bin to PATH for builder stage

# Copy project configuration and lock file
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync (installs mcp, uvicorn, starlette, etc.)
RUN . /root/.local/bin/env && uv sync --no-cache

# ---- Runtime Stage ----
FROM python:3.13-slim AS runtime # Use Python version >= requires-python
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Set PYTHONPATH to use packages from the copied venv
ENV PYTHONPATH="/app/.venv/lib/python3.13/site-packages"

# Copy the application script
COPY test_server_script.py .

# Expose the port the uvicorn server will listen on
EXPOSE 8765

# Run uvicorn module using the base image's python, with PYTHONPATH set
CMD ["/usr/local/bin/python3.13", "-m", "uvicorn", "test_server_script:app", "--host", "0.0.0.0", "--port", "8765"]
```

### Step 4.2: Build the SSE Image

```bash
docker build -t mcp-test-server-sse:latest -f Dockerfile.sse .
```

### Step 4.3: Run and Test the SSE Container

1.  **Run Container with Port Mapping:**
    ```bash
    docker run -p 8765:8765 --rm --name mcp-sse-test mcp-test-server-sse:latest
    ```
    - `-p 8765:8765`: Maps host port 8765 to container port 8765. **Essential for SSE.**
    - `--rm`: Removes the container when it stops.
    - `--name mcp-sse-test`: Assigns a name for easy management.
2.  **Test with Inspector:** Follow the same steps as in **Step 2.2** (run `mcp dev mock_script.py`, connect via SSE to `http://localhost:8765`).

## Part 5: Containerizing with Docker - Stdio Setup

This creates a Docker image that runs the server using `mcp run` for stdio communication.

### Step 5.1: Create Stdio Dockerfile (`Dockerfile.stdio`)

Create a file named `Dockerfile.stdio`:

```dockerfile
# ---- Builder Stage ----
FROM python:3.13-slim AS builder # Use Python version >= requires-python
WORKDIR /app

# Install curl for downloading uv
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv using the recommended script
SHELL ["/bin/bash", "-c"]
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Create a virtual environment
RUN . /root/.local/bin/env && uv venv .venv --seed
ENV PATH="/app/.venv/bin:${PATH}" # Add venv bin to PATH for builder stage

# Copy project configuration and lock file
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync (installs mcp[cli], starlette, uvicorn, etc.)
RUN . /root/.local/bin/env && uv sync --no-cache

# ---- Runtime Stage ----
FROM python:3.13-slim AS runtime # Use Python version >= requires-python
WORKDIR /app

# Install uv using the recommended script (needed for uv run)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
SHELL ["/bin/bash", "-c"]
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}" # Ensure system uv is findable

# Copy the virtual environment from the builder stage (contains dependencies + mcp command)
COPY --from=builder /app/.venv ./.venv

# Set path to use the virtual environment's commands
ENV PATH="/app/.venv/bin:${PATH}"

# Copy the application script
COPY test_server_script.py .

# No EXPOSE needed for stdio

# Run the script using 'mcp run' via 'uv run' for stdio
CMD uv run mcp run test_server_script.py
```

*Note: We install `uv` in runtime because `uv run` is used in the CMD. `mcp[cli]` gets installed via `uv sync`.*

### Step 5.2: Build the Stdio Image

```bash
docker build -t mcp-test-server-stdio:latest -f Dockerfile.stdio .
```

### Step 5.3: Run and Test the Stdio Container

1.  **Run Container Interactively:**
    ```bash
    docker run -i --rm --name mcp-stdio-test mcp-test-server-stdio:latest
    ```
    - `-i`: Attaches your terminal's stdin. **Essential for stdio.**
    - `--rm`: Removes the container when it stops.
    - **No `-p` port mapping.**
    - The terminal will appear to hang, waiting for MCP commands on stdin.
2.  **Test with Inspector (Difficult):** Directly connecting the Inspector UI to a running stdio container's streams is not straightforward. The primary test method for this setup is integration with a client like Claude Desktop.
3.  **Test Manually (Advanced):** You could manually send the `initialize` JSON-RPC message via stdin to the running container, but this is cumbersome.

## Part 6: Connecting Claude Desktop

Claude Desktop can connect using either method, but the configuration differs.

### Step 6.1: Configure Claude Desktop (`claude_desktop_config.json`)

Open `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows).

**Option A: Connecting to the SSE Docker Container**

```json
{
  "mcpServers": {
    "mcp-test-server-sse": {
      "command": "docker",
      "args": [
        "run",
        "-i",       // Optional but harmless
        "--rm",
        "-p",       // Port mapping is REQUIRED
        "8765:8765",
        "mcp-test-server-sse:latest" // Use the SSE image
      ]
    }
    // ... other servers
  }
}
```

**Option B: Connecting to the Stdio Docker Container**

```json
{
  "mcpServers": {
    "mcp-test-server-stdio": {
      "command": "docker",
      "args": [
        "run",
        "-i",       // Interactive flag is REQUIRED
        "--rm",
        // NO port mapping '-p'
        "mcp-test-server-stdio:latest" // Use the Stdio image
      ]
    }
    // ... other servers
  }
}
```

Choose **only one** option for your test server to avoid conflicts.

### Step 6.2: Restart Claude Desktop

Close and reopen Claude Desktop to apply the changes.

### Step 6.3: Verify and Test

1.  Check the MCP logs in Claude Desktop (`~/Library/Logs/Claude/mcp-server-SERVERNAME.log`) for errors.
2.  Look for the hammer icon <img src="https://mintlify.s3.us-west-1.amazonaws.com/mcp/images/claude-desktop-mcp-hammer-icon.svg" style="display: inline; margin: 0; height: 1.3em;" />.
3.  Click the icon to verify the `echo_query` tool is listed.
4.  Ask Claude to use the tool: `Use echo_query with the message "Testing Claude Desktop"`

## Part 7: Troubleshooting

### "Port is already allocated" Error (SSE Setup)

-   **Cause:** Another process (like a leftover local server, a previous container, or Claude Desktop launching the config twice) is already using host port 8765.
-   **Solution:**
    1.  Stop any local `uvicorn` processes.
    2.  Stop/remove existing Docker containers using the port (`docker ps`, `docker stop <id>`, `docker rm <id>`).
    3.  Check if other apps use the port (`lsof -i :8765` or `netstat -ano | findstr :8765`).
    4.  If using Claude Desktop, be aware it might launch Docker configs twice; the error might be from the second attempt, while the first succeeded. Verify functionality in Claude despite the log error. If it persists and blocks functionality, consider the stdio approach.

### Container Exits Immediately / No Connection (Stdio Setup)

-   **Cause:** The `mcp run` command might be erroring, or the client (Claude Desktop) isn't connecting correctly via stdio.
-   **Solution:**
    1.  Check Claude Desktop logs (`mcp-server-SERVERNAME.log`) for errors from within the container. Add `print("debug", file=sys.stderr)` statements to your Python script to trace execution.
    2.  Ensure the `-i` flag is present in the `docker run` command within `claude_desktop_config.json`.
    3.  Verify the `CMD` in `Dockerfile.stdio` is correct (`uv run mcp run ...`).

### `mcp dev` Fails to Connect / Inspector Issues

-   Remember `mcp dev script.py` defaults to stdio. Use this only for testing the stdio setup (Part 3).
-   For testing SSE (Part 2 & Part 4), run `uvicorn` separately, launch `mcp dev mock_script.py`, and connect manually via SSE in the UI.

## Conclusion

You now have two distinct methods (SSE and Stdio) for running your MCP server, both locally and containerized with Docker, along with ways to test them using the Inspector and integrate them with Claude Desktop. The SSE method is typical for web-accessible services, while the stdio method aligns closely with the default behavior of `mcp dev` and some client integrations like the `postgres` example. Choose the method that best suits your deployment and testing needs.
