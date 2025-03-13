from typing import Tuple
import httpx
from pathlib import Path

import elevenlabs

class TranscriptionClient:
    def __init__(self, base_url: str, api_key: str, elevenlabs_api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.elevenlabs_api_key = elevenlabs_api_key
        
        # Set ElevenLabs API key if provided
        if self.elevenlabs_api_key:
            elevenlabs.api_key = self.elevenlabs_api_key

    def transcribe_audio(
        self, audio_file_path: str, prompt: str = None
    ) -> Tuple[str, str, str]:
        """Transcribe audio file using the transcription service.

        Args:
            audio_file_path (str): Path to the audio file to transcribe.
            prompt (str, optional): Optional prompt to guide the transcription. Defaults to None.

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

        # Prepare parameters
        params = {}
        if prompt:
            params["prompt"] = prompt

        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{self.base_url}/transcribe",
                headers={"X-API-Key": self.api_key},
                files=files,
                params=params,
            )
            response.raise_for_status()
            transcription_response = response.json()

        if not transcription_response["status"] == "success":
            raise Exception(f"Transcription failed: {transcription_response['error']}")

        document = transcription_response["document"]
        text = document["text"]
        language = document["metadata"]["language"]
        return text, language, file.name

    def transcribe_audio_elevenlabs(
        self, audio_file_path: str, prompt: str = None
    ) -> Tuple[str, str, str]:
        """Transcribe audio file using the ElevenLabs transcription service.

        Args:
            audio_file_path (str): Path to the audio file to transcribe.
            prompt (str, optional): Optional prompt to guide the transcription. Defaults to None.

        Returns:
            Tuple[str, str, str]: (text, language, filename)
        """

        file = Path(audio_file_path)

        # Use ElevenLabs API to transcribe the audio
        with open(file, "rb") as audio_file:
            transcription_response = elevenlabs.transcribe(audio_file)

        # Extract text from the response
        text = transcription_response["text"]
        
        # ElevenLabs might not provide language info, so we'll use a default
        language = transcription_response.get("language", "en")
        
        return text, language, file.name
