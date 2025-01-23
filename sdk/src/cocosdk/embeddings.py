from typing import List
import json

from .utils import call_api
from .constants import API_KEY


EMBEDDING_URL_BASE = "http://127.0.0.1:8002"
EMBEDDING_URL = EMBEDDING_URL_BASE


def create_embeddings(chunks: List[str], batch_size: int = 25) -> List[List[float]]:
    """Create embeddings for a list of chunks using the embedding service.

    Args:
        chunks (List[str]): The chunks to embed.

    Raises:
        Exception: If the embedding service returns an error.

    Returns:
        List[List[float]]: The embeddings of the chunks.
    """
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        data = json.dumps({"chunks": batch})
        embedding_response = call_api(
            EMBEDDING_URL,
            "/embed_chunks",
            method="POST",
            headers=headers,
            data=data,
        )
        if not embedding_response["status"] == "success":
            raise Exception(f"Chunking failed: {embedding_response}")
        embeddings += embedding_response["embeddings"]
    return embeddings
