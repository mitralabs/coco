# Base Services

This directory contains all services running on the base station.

## Services

- **Transcription**: A FastAPI-based service that transcribes audio files into text using the Whisper model.
- **Chunking**: Provides text chunking functionality using LangChain.
- **Database**: Offers vector database functionality using Postgres for storing embeddings and metadata.
- **Orchestrator**: Is the bridge between the coco hardware device and the backend.
- **Frontend**: A simple gradio frontend, which provides a chat interface.

## Usage
1. Duplicate the `.env.template`file and rename it to `.env`
2. Feel free to choose another [whisper model](https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md).
3. *Instructions for the Openai API* will come later.
4. Run the `backend_start.sh`script. It will do the following:
  - Download the whisper.cpp repository, and remove git from it.
  - Compile whisper for your machine.
  - Download the whisper model of your choice
  - Create a virtual environment for the packages needed for the transcription service.
  - Start a FastAPI App in the Background as Transcription Service.
  - Kick off the Build Process for all other services as Docker Containers.


**Regarding Docker Compose**
```sh
docker compose up -d --wait
```

This will:

- build the docker images if not present
- spin up all containers
- wait until container health checks pass
  (meaning the `/test` endpoints actually return status 200)
- if a container is unhealthy, it most likely means that another container didn't spin up as supposed. E.g. when the orchestrator is unhealthy, make sure that the transcription service is running.

(You can omit the `--wait` flag to not wait for the health check, but then containers might return no reply yet.)

If Dockerfiles were changed, force an image rebuild:

```sh
docker compose up -d --wait --build
```

## Notes:
- It is currently not implemented, that transcription is not done locally. But it's definitely possible to change that, since our approach follows the openai transcription standard.
- If you want to see if the transcription process is running in the background use the command `ps aux | grep uvicorn`, which will show the uvicorn processes on your machine. If you further want to kill a process, use `kill <PID>` where <PID> is the Process ID.