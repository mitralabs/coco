from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import whisper
import tempfile
import os

app = FastAPI()

# Load the Whisper model (you can change "base" to other model sizes like "small", "medium", "large")
model = whisper.load_model("tiny")

@app.post("/transcribe/")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    try:
        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            # Write the uploaded file content to temporary file
            content = await audio_file.read()
            temp_audio.write(content)
            temp_audio.flush()
            
            # Transcribe the audio using Whisper
            result = model.transcribe(temp_audio.name)
            
            # Clean up the temporary file
            os.unlink(temp_audio.name)
            
            return JSONResponse(content={
                "text": result["text"],
                "language": result["language"]
            })
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# Keep the root endpoint for health checks
@app.get("/")
async def read_root():
    return "Whisper Transcription Service"