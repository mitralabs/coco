from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi import status, HTTPException

import aiofiles
import logging
import threading
import httpx
import asyncio

import os
import sys


from coco import CocoClient
from utils import PathManager

# Add threading for thread-safe counter
active_tasks = 0
task_lock = threading.Lock()


# Environment variables configuration
API_KEY = os.getenv("API_KEY")
CHUNKING_BASE = os.getenv("COCO_CHUNK_URL_BASE")
DB_API_BASE = os.getenv("COCO_DB_API_URL_BASE")
TRANSCRIPTION_BASE = os.getenv("COCO_TRANSCRIPTION_URL_BASE")
EMBEDDING_MODEL = os.getenv("COCO_EMBEDDING_MODEL")

if not all([API_KEY, CHUNKING_BASE, DB_API_BASE, TRANSCRIPTION_BASE, EMBEDDING_MODEL]):
    raise ValueError(
        "API_KEY, CHUNKING_BASE, DB_API_BASE, TRANSCRIPTION_BASE, and EMBEDDING_MODEL must all be set"
    )

# With Defaults
OPENAI_BASE = os.getenv("COCO_OPENAI_URL_BASE", "")
OLLAMA_BASE = os.getenv("COCO_OLLAMA_URL_BASE", "http://host.docker.internal:11434")
EMBEDDING_API = os.getenv("COCO_EMBEDDING_API", "ollama")
LLM_API = os.getenv("COCO_LLM_API", "ollama")


# Initialize CocoClient
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

# API Key security
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

        # Try to combine this audio file with adjacent ones
        snippet_path = PathManager.combine_audio_files(audio_path)
        audio_path = snippet_path

        if not audio_path:
            return False

        # Get previous transcript as context if available
        prompt = PathManager.get_prompt(audio_path)
        if prompt:
            logger.info(f"Using previous transcript as context for {audio_path}")
        # Hard coded as long as the transcription quality is too low
        prompt = None

        # Get date.
        date_time = PathManager.get_datetime(audio_path)
        session_id, index = PathManager.get_session_id_and_index(audio_path)

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
                cc.embed_and_store(
                    text=text,
                    filename=filename,
                    date_time=date_time,
                    session_id=session_id,
                    chunk_index=index,
                )
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
MAX_CONCURRENT_TASKS = 1
# Get the transcription test endpoint from environment variables
TRANSCRIPTION_BASE_URL = os.getenv(
    "COCO_TRANSCRIPTION_URL_BASE", "http://host.docker.internal:8000"
)


async def is_transcription_available():
    """
    Check if the transcription service is available

    Returns:
        bool: True if available, False otherwise
    """
    try:
        test_url = f"{TRANSCRIPTION_BASE_URL}/test"
        logger.info(f"Testing transcription service availability at: {test_url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                test_url, headers={"X-API-Key": API_KEY}, timeout=5.0
            )

        if response.status_code == 200:
            logger.info("Transcription service is available")
            return True
        else:
            logger.error(
                f"Transcription service returned status code: {response.status_code}"
            )
            return False
    except Exception as e:
        logger.error(f"Failed to connect to transcription service: {str(e)}")
        return False


# Route to upload audio data
@app.post("/uploadAudio")
async def upload_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
):
    try:
        # Check if transcription service is available
        if not await is_transcription_available():
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Transcription service is not available. Please try again later.",
                },
                status_code=503,  # Service Unavailable
            )

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
