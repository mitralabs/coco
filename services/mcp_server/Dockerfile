FROM python:3.13-slim

RUN apt-get update

# Copy project configuration
# COPY mcp_server/pyproject.toml ./

# Install dependencies directly using pip
# RUN pip install -e .

COPY mcp_server/requirements.txt .
RUN pip install -r requirements.txt

# Copy the entrypoint script from the orchestrator
COPY python_sdk_entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app

# Use the entrypoint script and then run the server directly
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "run.py"]

# Expose the SSE port
EXPOSE 8000
