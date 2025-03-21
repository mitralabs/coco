import datetime
import os
import httpx
from typing import List, Literal, Optional
import logging

from .async_utils import batched_parallel
from .chunking import ChunkingClient
from .db_api import DbApiClient
from .transcription import TranscriptionClient
from .lm import LanguageModelClient
from .tools import ToolsClient
from .rag import RagClient
from .agent import AgentClient


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

        # Initialize the clients in the correct order to avoid circular dependencies
        self.chunking = ChunkingClient(self.chunking_base, self.api_key)
        self.db_api = DbApiClient(self.db_api_base, self.api_key)
        self.transcription = TranscriptionClient(self.transcription_base, self.api_key)
        self.lm = LanguageModelClient(
            self.ollama_base, self.openai_base, self.embedding_api, self.llm_api
        )
        self.rag = RagClient(db_api=self.db_api, lm=self.lm)

        self._tools_client = ToolsClient(lm=self.lm, db_api=self.db_api)
        self.agent = AgentClient(
            lm=self.lm, tools_client=self._tools_client, llm_api=self.llm_api
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

    async def _embed_and_store_multiple(
        self,
        chunks: List[str],
        language: str,
        filename: str,
        session_id: int,
        date_times: List[Optional[datetime.datetime]] = None,
        model: str = "nomic-embed-text",
        chunk_indices: List[int] = None,
    ):
        embeddings = await self.lm._embed_multiple(chunks, model)
        ns_added, ns_skipped = await self.db_api._store_multiple(
            chunks,
            embeddings,
            language,
            filename,
            session_id,
            date_times,
            chunk_indices,
        )
        return ns_added, ns_skipped

    def embed_and_store_multiple(
        self,
        chunks: List[str],
        language: str,
        filename: str,
        session_id: int,
        date_times: List[Optional[datetime.datetime]] = None,
        model: str = "nomic-embed-text",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
        chunk_indices: List[int] = None,
    ):
        """Util function to embed and store chunks in the database.
        Just a wrapper around the `embedding.create_embeddings` and `db_api._store_in_database` functions.

        Args:
            chunks (List[str]): The chunks to embed and store.
            language (str): The language of the chunks.
            filename (str): The filename of the chunks.
            date_times (List[Optional[datetime.datetime]], optional): The dates of the chunks. Defaults to None.
            model (str, optional): The embedding model to use. Defaults to "nomic-embed-text".
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.
            session_id (int): The session ID to associate with the chunks.
            chunk_indices (List[int], optional): The indices of the chunks. Defaults to None (will use array indices).

        Returns:
            Tuple[int, int]: The number of documents added and skipped.
        """
        batched_embed_and_store = batched_parallel(
            function=self._embed_and_store_multiple,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Embedding and storing",
        )
        n_added, n_skipped = batched_embed_and_store(
            chunks, language, filename, session_id, date_times, model, chunk_indices
        )
        return sum(n_added), sum(n_skipped)

    def async_embed_and_store_multiple(
        self,
        chunks: List[str],
        language: str,
        filename: str,
        session_id: int,
        date_times: List[Optional[datetime.datetime]] = None,
        model: str = "nomic-embed-text",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
        chunk_indices: List[int] = None,
    ):
        async_batched_embed_and_store = batched_parallel(
            function=self._embed_and_store_multiple,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Embedding and storing",
            return_async_wrapper=True,
        )
        return async_batched_embed_and_store(
            chunks, language, filename, session_id, date_times, model, chunk_indices
        )

    def transcribe_and_store(
        self,
        audio_file: str,
        session_id: int,
        prompt: str = None,
        date_time: Optional[datetime.datetime] = None,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
        embedding_model: str = "nomic-embed-text",
        chunk_indices: List[int] = None,
    ):
        """Transcribe an audio file and store the chunks in the database.

        Args:
            audio_file (str): The path to the audio file.
            prompt (str, optional): A prompt to guide the transcription. Defaults to None.
            date_time (Optional[datetime.datetime], optional): The date of the audio file. Defaults to None.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.
            embedding_model (str, optional): The embedding model to use. Defaults to "nomic-embed-text".
            session_id (int): The session ID to associate with the chunks.
            chunk_indices (List[int], optional): The indices of the chunks. Defaults to None (will use array indices).

        Returns:
            Tuple[int, int]: The number of documents added and skipped.
        """
        text, language, filename = self.transcription.transcribe_audio(
            audio_file, prompt=prompt
        )

        # Store the transcription text next to the audio
        with open(f"{audio_file[:-4]}.txt", "w") as f:
            f.write(text)

        chunks = self.chunking.chunk_text(text=text)
        return self.embed_and_store_multiple(
            chunks=chunks,
            language=language,
            filename=filename,
            date_times=[date_time] * len(chunks),
            model=embedding_model,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            session_id=session_id,
            chunk_indices=chunk_indices,
        )

    def embed_and_store(
        self,
        text: str,
        session_id: int,
        language: str = "",
        filename: str = "",
        date_time: Optional[datetime.datetime] = None,
        embedding_model: str = "nomic-embed-text",
        chunk_index: int = None,
    ):
        """Chunk a text and store the chunks in the database.

        Args:
            text (str): The text to chunk.
            language (str, optional): The language of the text. Defaults to "".
            filename (str, optional): The filename of the text. Defaults to "".
            date_time (Optional[datetime.datetime], optional): The date of the text. Defaults to None.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.
            embedding_model (str, optional): The embedding model to use. Defaults to "nomic-embed-text".
            session_id (int): The session ID to associate with the chunks.
            chunk_index (int, optional): The indices of the chunks. Defaults to None (will use array indices).

        Returns:
            Tuple[int, int]: The number of documents added and skipped.
        """

        return self.embed_and_store_multiple(
            chunks=[text],
            language=language,
            filename=filename,
            date_times=[date_time],
            model=embedding_model,
            session_id=session_id,
            chunk_indices=[chunk_index],
        )
