# ---- Builder Stage ----
FROM python:3.13-slim AS builder

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
# Add venv bin to PATH for builder stage
ENV PATH="/app/.venv/bin:${PATH}"

# Uvicorn/Starlette and mcp will be installed via uv sync from pyproject.toml

# Copy project configuration and lock file
# Ensure your pyproject.toml lists 'mcp', uvicorn, and starlette as dependencies
COPY pyproject.toml uv.lock ./

# Install dependencies into the virtual environment using the lock file
RUN . /root/.local/bin/env && uv sync --no-cache

# ---- Runtime Stage ----
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install uv using the recommended script in the runtime stage (needed for uv run)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
SHELL ["/bin/bash", "-c"]
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy the virtual environment from the builder stage (contains dependencies + mcp[cli])
COPY --from=builder /app/.venv ./.venv

# Set path to use the virtual environment's commands
ENV PATH="/app/.venv/bin:${PATH}"

# Copy the application script (the one WITHOUT the main block)
COPY test_server_script.py .

# ** REVISED CMD ** Run the script using 'mcp run' via 'uv run'
# 'mcp run' will load the script and use stdio transport by default
# 'uv run' ensures it runs within the venv context
CMD uv run mcp run test_server_script.py