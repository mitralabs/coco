from typing import List
import logging
import httpx

logger = logging.getLogger(__name__)


class ChunkingClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    def chunk_text(
        self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200
    ) -> List[str]:
        """Chunk text using the chunking service.

        Args:
            text (str): Text to chunk.
            chunk_size (int, optional): Size of each chunk. Defaults to 1000.
            chunk_overlap (int, optional): Overlap between chunks. Defaults to 200.

        Raises:
            Exception: If service does not return a success status.

        Returns:
            List[str]: List of chunks.
        """
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/chunk/json",
                json={
                    "text": text,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                },
                headers=headers,
                timeout=100,
            )
            response.raise_for_status()
            chunk_response = response.json()

        if not chunk_response["status"] == "success":
            raise Exception(f"Chunking failed: {chunk_response['error']}")

        chunks = chunk_response["chunks"]
        return chunks
