# CoCo Frontend Service

A Gradio-based web interface for the CoCo application that provides RAG (Retrieval-Augmented Generation) capabilities and audio file processing.

## Features

- Interactive chat interface with RAG context display
- Audio file upload and processing (.wav files)
- Real-time conversation history
- Integration with CoCo services (transcription, chunking, db-api)

## Development Setup

The frontend service is configured to use Docker with volume mounting for development:

1. The `/app` directory is mounted as a volume, enabling hot-reloading during development
2. Python dependencies are managed through `requirements.txt`
3. Environment variables are loaded from `.env` file

### Directory Structure
```
frontend/
├── app/
│   └── main.py          # Main Gradio application
├── Dockerfile           # Container configuration
├── requirements.txt     # Python dependencies
├── start.sh            # Container startup script
└── .env                # Environment variables
```

## Running the Service

### Using Docker Compose (Recommended)
```bash
# From the services directory
docker compose up frontend

# To rebuild the container
docker compose up --build frontend
```

The service will be available at `http://localhost:8002`

## Environment Variables

- `GRADIO_SERVER_NAME`: Set to "0.0.0.0" for Docker networking
- Additional environment variables can be configured in the `.env` file