from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi import status, HTTPException

import aiofiles
import logging

import os
import sys

import time
import re

from coco import CocoClient
from utils import get_path, post_process_audio, process_transcription

cc = CocoClient(
    chunking_base="http://chunking:8000",
    db_api_base="http://db-api:8000",
    transcription_base="http://host.docker.internal:8000",
    ollama_base="http://host.docker.internal:11434",
    embedding_api="ollama",
    llm_api="ollama",
    api_key="test",
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],  # Output to console
)
logger = logging.getLogger(__name__)

# API Key Authentication
API_KEY = os.getenv("API_KEY", "test")

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


def kick_off_processing(audio_path: str, store_in_db: bool = True):
    """
    Kick off the processing pipeline for a session

    Args:
        session_id (str): ID of the session to process
    """
    logger.info(f"Processing audio file: {audio_path}")

    # Prepare Files for transcription. Returns a list of audio_paths to transcribe
    audio_paths = post_process_audio(audio_path)

    # Check if audio_paths is an empty list
    if not audio_paths:
        # This is a fine behavior postprocessing is probably waiting for more audio files
        logger.info("No audio files to transcribe.")
        return False

    for audio_path in audio_paths:
        # Transcribe the audio
        try:
            text, language, filename = cc.transcription.transcribe_audio(audio_path)

            if not text:
                logger.info("No text returned from transcription.")
                return False

            # Saves the transcription
            process_transcription(text, audio_path)

            if store_in_db:
                cc.chunk_and_store(text, language, filename)
                logger.info("Transcription saved successfully and stored in database.")
            else:
                logger.info("Transcription saved successfully.")
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
        logger.info("Audio file received")

        # Extract filename from headers
        filename = (
            request.headers.get("Content-Disposition", "")
            .split("filename=")[-1]
            .strip('"')
        )

        if not get_path(filename=filename):
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Invalid filename, expected format: int_int_YY-DD-MM_HH-MM-SS_suffix.wav, suffix in ['start', 'end', 'middle']",
                },
                status_code=400,
            )
        else:
            audio_path = get_path(filename=filename)

        # Function to save the file to local storage
        async with aiofiles.open(audio_path, "wb") as f:
            await f.write(body)
        logger.info(f"File saved to: {audio_path}")

        background_tasks.add_task(kick_off_processing, audio_path, store_in_db=True)
        logger.info(f"Background task added for file: {audio_path}")

        return JSONResponse(
            content={"status": "success", "message": ".wav successfully received"},
            status_code=200,
        )

    except Exception as e:
        return JSONResponse(
            content={"status": "error", "message": str(e)}, status_code=500
        )


# Keep the test endpoint for basic connectivity testing
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Orchestrator service: Test endpoint accessed successfully",
    }
