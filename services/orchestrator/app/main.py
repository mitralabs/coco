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

cc = CocoClient(
    chunking_base="http://chunking:8000",
    db_api_base="http://db-api:8000",
    transcription_base="http://transcription:8000",
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


def append_audio(directory_path):
    """
    Append all audio files in a directory and save as audio_full.wav

    Args:
        directory_path (str): Path to directory containing audio files
    """
    print(f"\nProcessing directory: {directory_path}")

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

    print(f"Found audio files: {audio_files}")

    if not audio_files:
        return False, None

    # Combine audio files
    combined = AudioSegment.from_wav(os.path.join(directory_path, audio_files[0]))
    for audio_file in audio_files[1:]:
        audio_path = os.path.join(directory_path, audio_file)
        audio = AudioSegment.from_wav(audio_path)
        combined += audio

    # Save combined audio in same directory
    output_path = os.path.join(directory_path, "audio_full.wav")
    combined.export(output_path, format="wav")
    print(f"Created: {output_path}")
    return True, output_path


def kick_off_processing(session_id):
    """
    Kick off the processing pipeline for a session

    Args:
        session_id (str): ID of the session to process
    """
    print(f"Kicking off processing for session: {session_id}")

    try:
        file_path = f"/data/session_{session_id}"
        # Append audio file paths and save to same directory.

        success, audio_path = append_audio(file_path)

        if not success:
            logger.error("Error processing session: No audio files found.")
            return False

        cc.transcribe_and_store(audio_path)

        logger.info("Orchestration completed successfully.")
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
async def upload_audio(request: Request, api_key: str = Depends(get_api_key)):
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

        # Function to save the file to local storage
        async with aiofiles.open(
            f"/data/session_{recording_session}/audio_{increment}.wav", "wb"
        ) as f:
            await f.write(body)
        print(f"Audio {recording_session}_{increment} saved successfully.")

        return JSONResponse(
            content={"status": "success", "message": ".wav successfully received"},
            status_code=200,
        )

        # return {"status": "success", "message": ".wav successfully received"}, 200

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

    # Call the next service async without waiting for a response
    background_tasks.add_task(kick_off_processing, recording_session)
    logger.info(f"Background task added for session: {recording_session}")

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
