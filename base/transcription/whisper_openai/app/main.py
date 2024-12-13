from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
import whisper
import tempfile
import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=dotenv_path)

app = FastAPI()

# Load the Whisper model
model = whisper.load_model("tiny", download_root="/data/models")

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
            
            # Transcribe the audio using Whisper
            result = model.transcribe(temp_audio.name)
            
            # Clean up the temporary file
            os.unlink(temp_audio.name)
            
            # Format the response as a JSON document that can be directly used by the chunking service
            return JSONResponse(content={
                "status": "success",
                "document": {
                    "text": result["text"],
                    "metadata": {
                        "language": result["language"],
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

# Keep the endpoint for health checks
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {"status": "success", "message": "Test endpoint accessed successfully"}