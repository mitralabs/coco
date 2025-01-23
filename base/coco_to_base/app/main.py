import sqlite3

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi import status, HTTPException

import uvicorn
import time
import aiofiles
from datetime import datetime
import logging

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # loads environment variables from.env file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# API Key Authentication
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")
api_key_header = APIKeyHeader(name="X-API-Key")

TO_DB = os.getenv("TO_DB", "False")


def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key


# Database file path
db_file = Path("/data/database.db")

if TO_DB.lower() in ("true"):
    # Check if SQLite database file exists
    if not db_file.exists():
        # Create a new SQLite database if it doesn't exist
        print("Database file not found. Creating a new database file.")
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE soundfiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                audio_data BLOB, 
                recording_session INTEGER, 
                increment INTEGER, 
                upload_datetime DATETIME
            )
        """
        )
        conn.commit()
        conn.close()
        print("Database file created successfully.")


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

        if TO_DB.lower() in ("true"):
            print("Saving audio data to database.")
            # Store the audio data in the SQLite database
            upload_datetime = datetime.now()
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO soundfiles (audio_data, recording_session, increment, upload_datetime) VALUES (?, ?, ?, ?)",
                (body, recording_session, increment, upload_datetime),
            )
            conn.commit()
            conn.close()
        else:
            print("Saving audio data to filesystem.")
            # Function to save the file to local storage
            async with aiofiles.open(f"/data/{filename}", "wb") as f:
                await f.write(body)
        print("Audio data saved successfully.")

        return JSONResponse(
            content={"status": "success", "message": ".wav successfully received"},
            status_code=200,
        )

        # return {"status": "success", "message": ".wav successfully received"}, 200

    except Exception as e:
        return JSONResponse(
            content={"status": "error", "message": str(e)}, status_code=500
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
