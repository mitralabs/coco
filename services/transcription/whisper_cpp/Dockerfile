# Use Python slim as the base image
FROM python:3.9-slim-bullseye

RUN apt-get update
RUN apt-get install -y ffmpeg
RUN apt-get install -y build-essential
RUN apt-get install -y cmake
RUN apt-get install -y git
RUN apt-get install -y curl

# Clone the whisper.cpp repository
RUN git clone https://github.com/ggerganov/whisper.cpp.git

# Set the working directory
WORKDIR /whisper.cpp

# Commit that was successfully tested
RUN git checkout 6aa1d7b89216dc6d9c41fc1536fae59adb214024

# Build the project
RUN make

# CD to the root directory
WORKDIR /

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]