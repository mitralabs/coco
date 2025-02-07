from typing import Tuple
import httpx
from pathlib import Path


class TranscriptionClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    def transcribe_audio(self, audio_file_path: str) -> Tuple[str, str, str]:
        """Transcribe audio file using the transcription service.

        Args:
            audio_file_path (str): Path to the audio file to transcribe.

        Returns:
            Tuple[str, str, str]: (text, language, filename)
        """
        file = Path(audio_file_path)

        # Open file in binary mode and create files dict with filename
        files = {
            "file": (
                file.name,
                file.open("rb"),
                "audio/wav",
            )  # Include filename and mime type
        }

        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{self.base_url}/transcribe",
                headers={"X-API-Key": self.api_key},
                files=files,
            )
            response.raise_for_status()
            transcription_response = response.json()

        if not transcription_response["status"] == "success":
            raise Exception(f"Transcription failed: {transcription_response['error']}")

        document = transcription_response["document"]
        text = document["text"]
        language = document["metadata"]["language"]
        return text, language, file.name
