# Base Services

This directory contains all services running on the base station.

## Services

- **Transcription**: A FastAPI-based service that transcribes audio files into text using the Whisper model.
- **Chunking**: Provides text chunking functionality using LangChain.
- **Database**: Offers vector database functionality using ChromaDB for storing embeddings and metadata.
- **Orchestrator**: Coordinates the transcription, chunking, and database services, managing the overall data flow.
- **Docker Template**: A boilerplate FastAPI service for creating new services, including basic API key authentication.

## Initial Usage (first time setup)
1. Open a terminal, within this (coco/services) Directory.
2. Create a virtual environment, by following the later steps:
  - `python3 -m venv venv-coco`
  - `source venv-coco/bin/activate` (-> this should suffice in the services directory)
  - `pip install --upgrade pip`
  - `pip install -r transcription/requirements.txt` (is it possible to include a path? should be...)
3. Now have a look at the .env.template file. First remove the ".template" from the file name so that it's name is ".env". Then you have to exchange the two paths `PATH_TO_EXECUTABLE`and `PATH_TO_MODEL`, within that file.<br>
Find the file named `whisper-cli` within the /whisper.cpp Directory. It is most likely under the path /whisper.cpp/build/bin. Copy the absolute path of the file. You can output the absolute path of a folder on your system by opening a terminal within that folder (right click, and open terminal) and typing `pwd`. This will probably output something like this `/Users/coco/path/to/whisper.cpp/build/bin`. Don't forget to append `whisper-cli`at the end. Do the same for the model-file which is probably under the /whisper.cpp/models/ directory and named `ggml-*.bin`.

## Usage
From **this directory**:

```
nohup python -m uvicorn transcription.app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug > transcription/uvicorn.log 2>&1 &
```
>Note: To show all background tasks, run `ps aux | grep uvicorn` <br> 
And to stop it: `kill <PID>`

This will run the whisper in a hidden process in the background on port 8000 of your machine, and further save the logs to /transcription/uvicorn.log

Then:
```sh
docker compose up -d --wait
```

This will:

- build the docker images if not present
- spin up all containers
- wait until container health checks pass
  (meaning the `/test` endpoints actually return status 200)

(You can omit the `--wait` flag to not wait for the health check, but then containers might return no reply yet.)

If Dockerfiles were changed, force an image rebuild:

```sh
docker compose up -d --wait --build
```