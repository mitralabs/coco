FROM python:3.9-slim

# Install system dependencies for Whisper
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y curl

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the main.py file directly into the working directory
COPY app/main.py main.py

# Create directory for models
RUN mkdir -p /data/models

# Run the FastAPI application with the correct module path
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]