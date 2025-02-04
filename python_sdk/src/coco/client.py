import os
import httpx
from typing import List

from .async_utils import batched_parallel
from .chunking import ChunkingClient
from .embeddings import EmbeddingClient
from .db_api import DbApiClient
from .rag import RagClient
from .transcription import TranscriptionClient


class CocoClient:
    def __init__(
        self,
        chunking_base: str = None,
        embedding_base: str = None,
        db_api_base: str = None,
        transcription_base: str = None,
        ollama_base: str = None,
        ionos_base: str = None,
        ionos_api_key: str = None,
        api_key: str = None,
    ):
        self.chunking_base = chunking_base
        self.embedding_base = embedding_base
        self.db_api_base = db_api_base
        self.transcription_base = transcription_base
        self.ollama_base = ollama_base
        self.ionos_base = ionos_base
        self.ionos_api_key = ionos_api_key
        self.api_key = api_key

        if not self.chunking_base:
            self.chunking_base = os.getenv("COCO_CHUNK_URL_BASE")
        if not self.embedding_base:
            self.embedding_base = os.getenv("COCO_EMBEDDING_URL_BASE")
        if not self.db_api_base:
            self.db_api_base = os.getenv("COCO_DB_API_URL_BASE")
        if not self.transcription_base:
            self.transcription_base = os.getenv("COCO_TRANSCRIPTION_URL_BASE")
        if not self.ollama_base:
            self.ollama_base = os.getenv("COCO_OLLAMA_URL_BASE")
        if not self.ionos_base:
            self.ionos_base = os.getenv("COCO_IONOS_URL_BASE")
        if not self.ionos_api_key:
            self.ionos_api_key = os.getenv("COCO_IONOS_API_KEY")
        if not self.api_key:
            self.api_key = os.getenv("COCO_API_KEY")

        assert self.chunking_base, "Chunking base URL is not set"
        assert self.embedding_base, "Embedding base URL is not set"
        assert self.db_api_base, "DB API base URL is not set"
        assert self.transcription_base, "Transcription base URL is not set"
        assert (
            self.ollama_base or self.ionos_base
        ), "Ollama and Ionos base URL are not set"
        assert not (
            self.ollama_base and self.ionos_base
        ), "Ollama and Ionos base URL are both set"
        assert self.api_key, "API key is not set"

        self.chunking = ChunkingClient(self.chunking_base, self.api_key)
        self.embedding = EmbeddingClient(self.embedding_base, self.api_key)
        self.db_api = DbApiClient(self.db_api_base, self.api_key)
        self.transcription = TranscriptionClient(self.transcription_base, self.api_key)
        self.rag = RagClient(
            self.ollama_base,
            self.ionos_base,
            self.ionos_api_key,
            self.db_api,
            self.embedding,
        )

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

    async def _embed_and_store(self, chunks, language, filename):
        embeddings = await self.embedding._create_embeddings(chunks)
        ns_added, ns_skipped = await self.db_api._store_in_database(
            chunks, embeddings, language, filename
        )
        return ns_added, ns_skipped

    def embed_and_store(
        self,
        chunks: List[str],
        language: str,
        filename: str,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
    ):
        """Util function to embed and store chunks in the database.
        Just a wrapper around the `embedding.create_embeddings` and `db_api._store_in_database` functions.

        Args:
            chunks (List[str]): The chunks to embed and store.
            language (str): The language of the chunks.
            filename (str): The filename of the chunks.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.

        Returns:
            Tuple[int, int]: The number of documents added and skipped.
        """
        batched_embed_and_store = batched_parallel(
            function=self._embed_and_store,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Embedding and storing",
        )
        n_added, n_skipped = batched_embed_and_store(chunks, language, filename)
        return sum(n_added), sum(n_skipped)
