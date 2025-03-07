from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi import status, HTTPException

import time
import aiofiles
import logging

import os
import sys

from pydub import AudioSegment
import re

from coco import CocoClient

CHUNKING_BASE = os.getenv("COCO_CHUNK_URL_BASE")
DB_API_BASE = os.getenv("COCO_DB_API_URL_BASE")
TRANSCRIPTION_BASE = os.getenv("COCO_TRANSCRIPTION_URL_BASE")
OLLAMA_BASE = os.getenv("COCO_OLLAMA_URL_BASE")
OPENAI_BASE = os.getenv("COCO_OPENAI_URL_BASE")
API_KEY = os.getenv("COCO_API_KEY")
EMBEDDING_API = os.getenv("COCO_EMBEDDING_API")
LLM_API = os.getenv("COCO_LLM_API")
# Default models from environment variables or fallback to defaults
EMBEDDING_MODEL = os.getenv("COCO_EMBEDDING_MODEL", "nomic-embed-text")

cc = CocoClient(
    chunking_base=CHUNKING_BASE,
    db_api_base=DB_API_BASE,
    transcription_base=TRANSCRIPTION_BASE,
    ollama_base=OLLAMA_BASE,
    openai_base=OPENAI_BASE,
    embedding_api=EMBEDDING_API,
    llm_api=LLM_API,
    api_key=API_KEY,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],  # Output to console
)
logger = logging.getLogger(__name__)


if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")
api_key_header = APIKeyHeader(name="X-API-Key")


def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key


app = FastAPI()


def append_audio(session: str):
    """
    Append all audio files in a directory and save as audio_full.wav

    Args:
        directory_path (str): Path to directory containing audio files
    """
    print(f"\nProcessing directory: {session}")

    directory_path = f"/data/{session}"

    # Get all wav files matching audio_* pattern
    audio_files = sorted(
        [
            f
            for f in os.listdir(directory_path)
            if f.endswith(".wav")
            and f.startswith("audio_")
            and not f.startswith("audio_full")
        ]
    )

    # Sort according to ID number
    audio_files.sort(key=lambda f: int(re.search(r"audio_(\d+)\.wav", f).group(1)))

    logger.info(f"Found audio files: {audio_files}")

    if not audio_files:
        return False, None

    # Combine audio files
    combined = AudioSegment.from_wav(os.path.join(directory_path, audio_files[0]))
    for audio_file in audio_files[1:]:
        audio_path = os.path.join(directory_path, audio_file)
        audio = AudioSegment.from_wav(audio_path)
        combined += audio

    # Save combined audio in same directory
    output_path = os.path.join(directory_path, f"{session}.wav")
    combined.export(output_path, format="wav")
    return True, output_path


def kick_off_processing(audio_path: str, store_in_db: bool = True):
    """
    Kick off the processing pipeline for a session

    Args:
        session_id (str): ID of the session to process
    """
    logger.info(f"Processing audio file: {audio_path}")

    try:
        if store_in_db:
            cc.transcribe_and_store(audio_path, embedding_model=EMBEDDING_MODEL)

            logger.info("Full Orchestration completed successfully.")
            return True
        else:
            text, language, filename = cc.transcription.transcribe_audio(audio_path)
            # Store the transcription in the folder
            with open(f"{audio_path[:-4]}.txt", "w") as f:
                f.write(text)
            logger.info("Transcription completed successfully.")
            return True

    except Exception as e:
        logger.error(f"Error processing session: {str(e)}")
        return False


# Route to check if the server is running
@app.get("/")
async def read_root():
    print("Root path accessed. Server is running.")
    return {"status": "success", "message": "Server is running"}, 200


# Route to upload audio data
@app.post("/uploadAudio")
async def upload_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
):
    try:
        # Get the raw body content
        body = await request.body()
        print("Audio data received successfully.")

        # Extract filename from headers
        filename = (
            request.headers.get("Content-Disposition", "")
            .split("filename=")[-1]
            .strip('"')
        )

        print(f"Filename: {filename}")

        # Parse filename to get recording_session and increment
        if filename.startswith("audio_"):
            parts = filename.split("_")
            if len(parts) == 3:
                recording_session = int(parts[1])
                # Extract .wav from increment, which is the last part of the filename
                increment = int(parts[2].split(".")[0])
            else:
                raise ValueError(
                    "Invalid filename format. Expected format: audio_<recording_session>_<increment>"
                )
        else:
            raise ValueError("Invalid filename. Expected prefix: 'audio_'")

        # Function to generate a timestamp, if needed.
        timestamp = int(time.time())

        # Check if a folder with the recording_session exists in /data directory, if not create it.
        if not os.path.exists(f"/data/session_{recording_session}"):
            os.makedirs(f"/data/session_{recording_session}")

        audio_path = f"/data/session_{recording_session}/audio_{increment}.wav"

        # Function to save the file to local storage
        async with aiofiles.open(audio_path, "wb") as f:
            await f.write(body)
        print(f"Audio {recording_session}_{increment} saved successfully.")

        background_tasks.add_task(kick_off_processing, audio_path, store_in_db=False)
        logger.info(f"Background task added for file: {audio_path}")

        return JSONResponse(
            content={"status": "success", "message": ".wav successfully received"},
            status_code=200,
        )

    except Exception as e:
        return JSONResponse(
            content={"status": "error", "message": str(e)}, status_code=500
        )


@app.get("/TransferComplete")
async def transfer_complete_endpoint(
    recording_session: int,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
):
    # Add logging to track execution
    logger.info(f"Transfer complete received for session: {recording_session}")

    # Append audio file paths and save to same directory.
    success, audio_path = append_audio(f"session_{recording_session}")

    if not success:
        logger.error("Error processing session: No audio files found.")
    else:
        logger.info("Audio files appended successfully.")
        # Call the next service async without waiting for a response
        background_tasks.add_task(kick_off_processing, audio_path)
        logger.info(f"Background task added for {audio_path}")

    # Return Success
    return JSONResponse(
        content={"status": "success", "message": "Transfer Complete"},
        status_code=200,
    )


# Keep the test endpoint for basic connectivity testing
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Orchestrator service: Test endpoint accessed successfully",
    }
