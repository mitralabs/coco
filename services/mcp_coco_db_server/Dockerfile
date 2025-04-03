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
ENV PATH="/app/.venv/bin:${PATH}" 

# Copy project configuration
COPY pyproject.toml ./

# Install dependencies using uv sync with --no-install-project to avoid building the package
RUN . /root/.local/bin/env && uv sync --no-cache --no-install-project

# ---- Runtime Stage ----
FROM python:3.13-slim AS runtime
WORKDIR /app

# Install uv using the recommended script (needed for uv run)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
SHELL ["/bin/bash", "-c"]
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Set path to use the virtual environment's commands
ENV PATH="/app/.venv/bin:${PATH}"

# Set PYTHONPATH to include mounted SDK and app directory
ENV PYTHONPATH="/app:/python_sdk/src"

# Copy server script directly to /app
COPY app/*.py ./

# Run the script using 'mcp run' via 'uv run' for stdio
CMD uv run mcp run coco_db_mcp_server.py 