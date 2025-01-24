from typing import List
import json
import logging

from .utils import call_api
from .constants import API_KEY

logger = logging.getLogger(__name__)

CHUNK_URL_BASE = "http://127.0.0.1:8001"
CHUNK_URL = CHUNK_URL_BASE


def chunk_text(
    text: str, chunk_size: int = 1000, chunk_overlap: int = 200
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
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps(
        {"text": text, "chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
    )
    chunk_response = call_api(
        CHUNK_URL,
        "/chunk/json",
        method="POST",
        headers=headers,
        data=data,
    )

    if not chunk_response["status"] == "success":
        raise Exception(f"Chunking failed: {chunk_response['error']}")

    chunks = chunk_response["chunks"]
    return chunks
