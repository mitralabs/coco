from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
import tempfile
import os
from pathlib import Path
from dotenv import load_dotenv
import json
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the directory of the script
BASE_DIR = Path() #.resolve().parent.parent.parent  # Adjust based on depth

# Load .env file from the directory where Uvicorn is executed
load_dotenv(BASE_DIR / ".env")

# API Key Authentication and Model Settings
API_KEY = os.getenv("API_KEY") 
if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")

PATH_TO_MODEL = os.getenv("PATH_TO_MODEL")
if not PATH_TO_MODEL:
    raise ValueError("Model environment variable must be set")

PATH_TO_EXECUTABLE = os.getenv("PATH_TO_EXECUTABLE")
if not PATH_TO_EXECUTABLE:
    raise ValueError("Executable environment variable must be set")



app = FastAPI()

api_key_header = APIKeyHeader(name="X-API-Key")

def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key


def process_whisper_output(audio_path):
    # Construct JSON path from audio path
    json_path = f"{audio_path}.json"

    # Check if JSON exists
    if not Path(json_path).exists():
        raise FileNotFoundError(f"JSON output not found at {json_path}")

    # Read and parse JSON
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            transcription_data = json.load(f)

        return transcription_data

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    except Exception as e:
        raise Exception(f"Error processing JSON: {e}")


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), api_key: str = Depends(get_api_key)):
    # Create a temporary file to store the uploaded audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        content = await file.read()
        temp_audio.write(content)
        temp_audio.flush()

        whisper_executable = str(Path(PATH_TO_EXECUTABLE))
        model_path = Path(PATH_TO_MODEL)

        command = [
            whisper_executable,
            "-m",
            model_path,
            "-f",
            temp_audio.name,
            "-l",
            "de",
            "-oj",
            "true",  # Output in JSON format
        ]
        result = subprocess.run(
            [str(i) for i in command], capture_output=True, text=True, check=True
        )
        print("Whisper.cpp output:")
        print(result.stdout)

        # print(result)
        # print(result.stdout)

        data = process_whisper_output(temp_audio.name)
        # Access transcription data
        transcription = data["transcription"]  # Adjust based on actual JSON structure

        # Format the response to match your previous structure
        print(type(transcription), transcription)
        text = " ".join([i["text"] for i in transcription])
        return JSONResponse(
            content={
                "status": "success",
                "document": {
                    "text": text,
                    "metadata": {
                        "language": "should be somewhere else in the JSON. Needs to be updated.",
                    },
                },
            }
        )


@app.get("/test")
async def test():
    return {"status": "success", "message": "Whisper.cpp Transcription Service"}