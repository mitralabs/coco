import os
import httpx

from .chunking import ChunkingClient
from .embeddings import EmbeddingClient
from .db_api import DbApiClient
from .transcription import TranscriptionClient


class CocoClient:
    def __init__(
        self,
        chunking_base: str = None,
        embedding_base: str = None,
        db_api_base: str = None,
        transcription_base: str = None,
        api_key: str = None,
    ):
        self.chunking_base = chunking_base
        self.embedding_base = embedding_base
        self.db_api_base = db_api_base
        self.transcription_base = transcription_base
        self.api_key = api_key

        if not self.chunking_base:
            self.chunking_base = os.getenv("COCO_CHUNK_URL_BASE")
        if not self.embedding_base:
            self.embedding_base = os.getenv("COCO_EMBEDDING_URL_BASE")
        if not self.db_api_base:
            self.db_api_base = os.getenv("COCO_DB_API_URL_BASE")
        if not self.transcription_base:
            self.transcription_base = os.getenv("COCO_TRANSCRIPTION_URL_BASE")
        if not self.api_key:
            self.api_key = os.getenv("COCO_API_KEY")

        assert self.chunking_base, "Chunking base URL is not set"
        assert self.embedding_base, "Embedding base URL is not set"
        assert self.db_api_base, "DB API base URL is not set"
        assert self.transcription_base, "Transcription base URL is not set"
        assert self.api_key, "API key is not set"

        self.chunking = ChunkingClient(self.chunking_base, self.api_key)
        self.embedding = EmbeddingClient(self.embedding_base, self.api_key)
        self.db_api = DbApiClient(self.db_api_base, self.api_key)
        self.transcription = TranscriptionClient(self.transcription_base, self.api_key)

    def health_check(self):
        services = {
            "transcription": self.transcription_base,
            "chunking": self.chunking_base,
            "embedding": self.embedding_base,
            "database": self.db_api_base,
        }
        for service_name, url in services.items():
            with httpx.Client() as client:
                response = client.get(
                    f"{url}/test", headers={"X-API-Key": self.api_key}, timeout=10
                )
                response.raise_for_status()
                test_response = response.json()
            if not test_response.get("status") == "success":
                raise Exception(f"{service_name} service test failed: {test_response}")
