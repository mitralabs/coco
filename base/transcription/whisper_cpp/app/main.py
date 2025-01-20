from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
import tempfile
import os
from pathlib import Path
import json
import subprocess

app = FastAPI()

# API Key Authentication
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")

# Setting the Model
GGML_MODEL = os.getenv("GGML_MODEL")
#GGML_MODEL = "ggml-large-v3-turbo" #For testing only, helps since the .env file is included during the build.
if not GGML_MODEL:
    raise ValueError("Model environment variable must be set")

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
        with open(json_path, 'r', encoding='utf-8') as f:
            transcription_data = json.load(f)
            
        return transcription_data
            
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    except Exception as e:
        raise Exception(f"Error processing JSON: {e}")



@app.post("/transcribe/")
async def transcribe_audio(audio_file: UploadFile = File(...), api_key: str = Depends(get_api_key)):
    try:
        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            content = await audio_file.read()
            temp_audio.write(content)
            temp_audio.flush()
            
            # Construct the absolute paths
            whisper_cpp_dir = Path.cwd().parent / "whisper.cpp"

            whisper_executable_paths = [
                whisper_cpp_dir / "main",
                whisper_cpp_dir / "build/bin/main"
            ]

            for path in whisper_executable_paths:
                if path.exists():
                    whisper_executable = str(path)
                    break
            else:
                raise FileNotFoundError(f"whisper.cpp main executable not found in {whisper_executable_paths}")

            model_path = whisper_cpp_dir / "models" / f"{GGML_MODEL}.bin"
            
            # Prepare the command
            command = [
                whisper_executable,
                "-m", model_path,
                "-f", temp_audio.name,
                "-l", "de",
                "-oj", "true",  # Output in JSON format
            ]
            
            # Execute the command and capture output
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                #print(result)
                #print(result.stdout)

                data = process_whisper_output(temp_audio.name)
                # Access transcription data
                transcription = data['transcription']  # Adjust based on actual JSON structure

                # Format the response to match your previous structure
                return JSONResponse(content={
                    "status": "success",
                    "document": {
                        "text": transcription,
                        "metadata": {
                            "language": "should be somewhere else in the JSON. Needs to be updated.",
                            "filename": audio_file.filename
                        }
                    }
                })
                
            except subprocess.CalledProcessError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Whisper.cpp execution failed: {e.stderr}"
                )
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to parse whisper.cpp output: {str(e)}"
                )
            finally:
                # Clean up the temporary file
                os.unlink(temp_audio.name)
                
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e)
            }
        )

@app.get("/")
async def read_root():
    return {"status": "success", "message": "Whisper.cpp Transcription Service"}