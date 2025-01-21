# Use Python slim as the base image
FROM python:3.9-slim-bullseye

# Install necessary apt packages
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    cmake \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install curl for health checks
RUN apt-get update && apt-get install -y curl

# Clone the whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# Set the working directory
WORKDIR /whisper.cpp

# Build the project
RUN make

# CD to the root directory
WORKDIR /

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]