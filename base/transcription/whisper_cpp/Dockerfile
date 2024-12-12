FROM ghcr.io/ggerganov/whisper.cpp:main

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory to /whisper.cpp
WORKDIR /whisper.cpp

# Create models directory and download script directly from the repository
RUN mkdir -p /models && \
    wget -O /models/download-ggml-model.sh https://raw.githubusercontent.com/ggerganov/whisper.cpp/master/models/download-ggml-model.sh && \
    chmod +x /models/download-ggml-model.sh && \
    /models/download-ggml-model.sh base /models

# Set working directory for the application
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/main.py .
COPY app/.env .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV WHISPER_BIN="/whisper.cpp/main"
ENV MODEL_PATH="/models/ggml-base.bin"

# Create directory for temporary files
RUN mkdir -p /data

# Expose port 8000
EXPOSE 8000

# Run the FastAPI application
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]