from typing import Tuple
import httpx


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
        with open(audio_file_path, "rb") as audio_file:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/transcribe/",
                    headers={"X-API-Key": self.api_key},
                    files={"audio_file": audio_file},
                )
                response.raise_for_status()
                transcription_response = response.json()

        if not transcription_response["status"] == "success":
            raise Exception(f"Transcription failed: {transcription_response['error']}")

        document = transcription_response["document"]
        text = document["text"]
        language = document["metadata"]["language"]
        filename = document["metadata"]["filename"]
        return text, language, filename
