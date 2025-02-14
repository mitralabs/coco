import os
import httpx
from typing import List, Literal
import logging

from .async_utils import batched_parallel
from .chunking import ChunkingClient
from .db_api import DbApiClient
from .rag import RagClient
from .transcription import TranscriptionClient
from .lm import LanguageModelClient


logger = logging.getLogger(__name__)


class CocoClient:
    def __init__(
        self,
        chunking_base: str = None,
        db_api_base: str = None,
        transcription_base: str = None,
        ollama_base: str = None,
        openai_base: str = None,
        embedding_api: Literal["ollama", "openai"] = "ollama",
        llm_api: Literal["ollama", "openai"] = "ollama",
        api_key: str = None,
    ):
        self.chunking_base = chunking_base
        self.db_api_base = db_api_base
        self.transcription_base = transcription_base
        self.ollama_base = ollama_base
        self.openai_base = openai_base
        self.embedding_api = embedding_api
        self.llm_api = llm_api
        self.api_key = api_key

        if not self.chunking_base:
            self.chunking_base = os.getenv("COCO_CHUNK_URL_BASE")
        if not self.db_api_base:
            self.db_api_base = os.getenv("COCO_DB_API_URL_BASE")
        if not self.transcription_base:
            self.transcription_base = os.getenv("COCO_TRANSCRIPTION_URL_BASE")
        if not self.ollama_base:
            self.ollama_base = os.getenv("COCO_OLLAMA_URL_BASE")
        if not self.openai_base:
            self.openai_base = os.getenv("COCO_OPENAI_URL_BASE")
        if not self.api_key:
            self.api_key = os.getenv("COCO_API_KEY")

        assert self.chunking_base, "Chunking base URL is not set"
        assert self.db_api_base, "DB API base URL is not set"
        assert self.transcription_base, "Transcription base URL is not set"
        if self.embedding_api == "ollama" or self.llm_api == "ollama":
            assert self.ollama_base, "Ollama base URL is not set"
        if self.embedding_api == "openai" or self.llm_api == "openai":
            assert self.openai_base, "OpenAI base URL is not set"
        assert self.api_key, "API key is not set"

        self.chunking = ChunkingClient(self.chunking_base, self.api_key)
        self.db_api = DbApiClient(self.db_api_base, self.api_key)
        self.transcription = TranscriptionClient(self.transcription_base, self.api_key)
        self.lm = LanguageModelClient(
            self.ollama_base, self.openai_base, self.embedding_api, self.llm_api
        )
        self.rag = RagClient(
            self.db_api,
            self.lm,
        )

    def health_check(self, raise_on_error: bool = False):
        services = {
            "transcription": self.transcription_base,
            "chunking": self.chunking_base,
            "database": self.db_api_base,
        }
        for service_name, url in services.items():
            try:
                with httpx.Client() as client:
                    response = client.get(
                        f"{url}/test", headers={"X-API-Key": self.api_key}, timeout=10
                    )
                    response.raise_for_status()
                    test_response = response.json()
                if not test_response.get("status") == "success":
                    raise Exception(
                        f"{service_name} service test failed: {test_response}"
                    )
                logger.info(
                    f"Health check: {service_name} service healthy and reachable"
                )
            except Exception as e:
                logger.warning(f"Health check: {service_name} service failed")
                if raise_on_error:
                    raise e
        if self.embedding_api == "ollama" or self.llm_api == "ollama":
            try:
                with httpx.Client() as client:
                    response = client.get(f"{self.ollama_base}")
                    response.raise_for_status()
                logger.info("Health check: Ollama service healthy and reachable")
            except Exception as e:
                logger.warning("Health check: Ollama service failed")
                if raise_on_error:
                    raise e
        if self.embedding_api == "openai" or self.llm_api == "openai":
            try:
                with httpx.Client() as client:
                    response = client.get(
                        url=f"{self.openai_base}/models",
                        headers={
                            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}"
                        },
                    )
                    response.raise_for_status()
                logger.info("Health check: OpenAI service healthy and reachable")
            except Exception as e:
                logger.warning("Health check: OpenAI service failed")
                if raise_on_error:
                    raise e

    async def _embed_and_store(
        self, chunks, language, filename, model="nomic-embed-text"
    ):
        embeddings = await self.lm._embed(chunks, model)
        ns_added, ns_skipped = await self.db_api._store_in_database(
            chunks, embeddings, language, filename
        )
        return ns_added, ns_skipped

    def embed_and_store(
        self,
        chunks: List[str],
        language: str,
        filename: str,
        model: str = "nomic-embed-text",
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
        n_added, n_skipped = batched_embed_and_store(chunks, language, filename, model)
        return sum(n_added), sum(n_skipped)

    def transcribe_and_store(
        self,
        audio_file: str,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
    ):
        """Transcribe, chunk, embed and store.

        Args:
            audio_file (str): The audio file to transcribe.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.

        Returns:
            Tuple[int, int]: The number of documents added and skipped.
        """
        text, language, filename = self.transcription.transcribe_audio(audio_file)

        # Store the transcription text next to the audio
        with open(f"{audio_file[:-4]}.txt", "w") as f:
            f.write(text)

        chunks = self.chunking.chunk_text(text=text)
        return self.embed_and_store(
            chunks=chunks,
            language=language,
            filename=filename,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
        )
