from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi import status, HTTPException

import aiofiles
import logging
import threading

import os
import sys


from coco import CocoClient
from utils import PathManager

# Add threading for thread-safe counter
active_tasks = 0
task_lock = threading.Lock()


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
    global active_tasks

    try:
        with task_lock:
            active_tasks += 1
            current_tasks = active_tasks

        logger.info(
            f"Processing audio file: {audio_path} (Active tasks: {current_tasks})"
        )

        # Get previous transcript as context if available
        prompt = PathManager.get_prompt(audio_path)
        if prompt:
            logger.info(f"Using previous transcript as context for {audio_path}")

        # Get date.
        date = PathManager.get_date(audio_path)
        logger.info(f"Date: {date}, type: {type(date)}")

        # Transcribe the audio
        try:
            text, language, filename = cc.transcription.transcribe_audio(
                audio_path, prompt
            )

            if not text:
                logger.info("No text returned from transcription.")
                return False

            # Saves the transcription
            PathManager.save_transcription(text, audio_path)

            if store_in_db and text not in ["", " ", "."]:
                cc.chunk_and_store(text, language, filename, date)
                logger.info("Transcription saved successfully and stored in database.")
            else:
                logger.info("Transcription saved successfully.")
            return True

        except Exception as e:
            logger.error(f"Error processing session: {str(e)}")
            return False

        # Saves the transcription
        PathManager.save_transcription(text, audio_path)

        if store_in_db:
            cc.chunk_and_store(text, language, audio_path, date)
            logger.info("Transcription saved successfully and stored in database.")
        else:
            logger.info("Transcription saved successfully.")
        return True

    except Exception as e:
        logger.error(f"Error processing session: {str(e)}")
        return False

    finally:
        # Always decrement counter when done
        with task_lock:
            active_tasks -= 1
            logger.info(
                f"Finished processing for {audio_path} (Active tasks: {active_tasks})"
            )


# Route to check if the server is running
@app.get("/")
async def read_root():
    print("Root path accessed. Server is running.")
    return {"status": "success", "message": "Server is running"}, 200


# Add a constant for max concurrent tasks
MAX_CONCURRENT_TASKS = 4


# Route to upload audio data
@app.post("/uploadAudio")
async def upload_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
):
    try:
        # Check if system is at capacity
        with task_lock:
            if active_tasks >= MAX_CONCURRENT_TASKS:
                return JSONResponse(
                    content={
                        "status": "busy",
                        "message": "Server is currently at capacity. Please try again later.",
                    },
                    status_code=503,  # Service Unavailable
                )

        # Get the raw body content
        body = await request.body()
        logger.info("Audio file received")

        # Extract filename from headers
        filename = (
            request.headers.get("Content-Disposition", "")
            .split("filename=")[-1]
            .strip('"')
        )

        audio_path = PathManager.get_raw_path(filename)
        if not audio_path:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Invalid filename, expected format: int_int_YY-DD-MM_HH-MM-SS_suffix.wav, suffix in ['start', 'end', 'middle']",
                },
                status_code=400,
            )

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


@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Orchestrator service: Test endpoint accessed successfully",
    }


@app.get("/status")
async def get_system_status(api_key: str = Depends(get_api_key)):
    with task_lock:
        current_tasks = active_tasks

    return {
        "status": "success",
        "active_tasks": current_tasks,
        "max_tasks": MAX_CONCURRENT_TASKS,
        "available_capacity": MAX_CONCURRENT_TASKS - current_tasks,
    }
