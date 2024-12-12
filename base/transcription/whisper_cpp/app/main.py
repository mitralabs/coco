from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
import tempfile
import os
import subprocess
import json
from dotenv import load_dotenv

dotenv_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=dotenv_path)

app = FastAPI()

# API Key Authentication
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")
api_key_header = APIKeyHeader(name="X-API-Key")

def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key

@app.post("/transcribe/")
async def transcribe_audio(audio_file: UploadFile = File(...), api_key: str = Depends(get_api_key)):
    try:
        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            content = await audio_file.read()
            temp_audio.write(content)
            temp_audio.flush()
        
        # Run whisper.cpp transcription
        result = subprocess.run(
            [os.getenv('WHISPER_BIN', './main'), "-m", os.getenv('MODEL_PATH', '/models/ggml-base.bin'), "-f", temp_audio.name, "-ojson"],
            capture_output=True,
            text=True
        )
        
        # Clean up the temporary file
        os.unlink(temp_audio.name)
        
        if result.returncode != 0:
            raise Exception(f"Transcription failed: {result.stderr}")
        
        # Parse the JSON output
        transcription = json.loads(result.stdout)
        
        return JSONResponse(content={
            "status": "success",
            "document": {
                "text": transcription.get("text", ""),
                "metadata": {
                    "language": transcription.get("language", "unknown"),
                    "filename": audio_file.filename
                }
            }
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e)
            }
        )

# Health check endpoint
@app.get("/")
async def read_root():
    return {"status": "success", "message": "Whisper.cpp Transcription Service"}