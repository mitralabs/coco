from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
import tempfile
import os
import json
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()  # loads environment variables from.env file

app = FastAPI()

# API Key Authentication
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")
# Setting the Model
GGML_MODEL = os.getenv("GGML_MODEL")
if not GGML_MODEL:
    raise ValueError("Model environment variable must be set")


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
            
            # Construct the absolute paths
            whisper_cpp_dir = os.path.join(os.path.dirname(os.getcwd()), "whisper.cpp")
            whisper_executable = os.path.join(whisper_cpp_dir, "build/bin/main")
            model_path = os.path.join(whisper_cpp_dir, f'models/{GGML_MODEL}.bin')
            
            # Prepare the command
            command = [
                whisper_executable,
                "-m", model_path,
                "-f", temp_audio.name,
                "-oj"  # Output in JSON format
            ]
            
            # Execute the command and capture output
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                print(result)

                print("-----------------")

                print(result.stdout)

                print(type(result.stdout))

                # Parse the JSON output
                #whisper_output = json.loads(result.stdout)
                

                # Format the response to match your previous structure
                return JSONResponse(content={
                    "status": "success",
                    "document": {
                        "text": result.stdout,
                        "metadata": {
                            "language": "not yet implemented",
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