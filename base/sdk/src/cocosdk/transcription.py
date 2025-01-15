import logging

from .utils import call_api
from .constants import API_KEY

logger = logging.getLogger(__name__)

TRANSCRIPTION_URL_BASE = "http://127.0.0.1:8000"
TRANSCRIPTION_URL = TRANSCRIPTION_URL_BASE


def transcribe_audio(audio_file_path):
    """Transcribe an audio file using the transcription service with a timeout."""
    logger.info("Starting audio transcription...")
    logger.info(f"using api key {API_KEY}")

    headers = {"X-API-Key": API_KEY}

    try:
        with open(audio_file_path, "rb") as audio_file:
            files = {"audio_file": audio_file}
            transcription_response = call_api(
                TRANSCRIPTION_URL,
                "/transcribe/",
                method="POST",
                headers=headers,
                files=files,
            )
            # print(f"Transcription response: {transcription_response}")  # Print the transcription response

    except FileNotFoundError:
        logger.error(f"Error: Audio file not found at '{audio_file_path}'")
        return None

    if not transcription_response:
        logger.error("Transcription failed (check previous errors)")
        return None

    if transcription_response.get("status") == "success":
        logger.info("Transcription successful.")
        return transcription_response.get("document")
    else:
        logger.error(f"Transcription failed: {transcription_response.get('error')}")
        return None
