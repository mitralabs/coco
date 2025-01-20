from typing import Tuple

from .utils import call_api
from .constants import API_KEY


TRANSCRIPTION_URL_BASE = "http://127.0.0.1:8000"
TRANSCRIPTION_URL = TRANSCRIPTION_URL_BASE


def transcribe_audio(audio_file_path: str) -> Tuple[str, str, str]:
    """Transcribe audio file using the transcription service.

    Args:
        audio_file_path (str): Path to the audio file to transcribe.

    Returns:
        Tuple[str, str, str]: (text, language, filename)
    """
    headers = {"X-API-Key": API_KEY}
    with open(audio_file_path, "rb") as audio_file:
        files = {"audio_file": audio_file}
        transcription_response = call_api(
            TRANSCRIPTION_URL,
            "/transcribe/",
            method="POST",
            headers=headers,
            files=files,
        )

    if not transcription_response["status"] == "success":
        raise Exception(f"Transcription failed: {transcription_response['error']}")

    document = transcription_response["document"]
    text = document["text"]
    language = document["metadata"]["language"]
    filename = document["metadata"]["filename"]
    return text, language, filename
