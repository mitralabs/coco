import json
import logging

from .utils import call_api
from .constants import API_KEY

logger = logging.getLogger(__name__)

CHUNK_URL_BASE = "http://127.0.0.1:8001"
CHUNK_URL = CHUNK_URL_BASE


def chunk_text(document):
    """Chunk the transcribed text using the chunking service with a timeout."""
    logger.info("Starting text chunking...")

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({"document": document})
    chunk_response = call_api(
        CHUNK_URL,
        "/chunk/json?chunk_size=1000&chunk_overlap=200",  # These defaults can be parameterized
        method="POST",
        headers=headers,
        data=data,
    )
    # print(f"Chunking response: {chunk_response}")  # Print the chunking response

    if not chunk_response:
        logger.error("Chunking failed (check previous errors)")
        return None

    if chunk_response.get("status") == "success":
        logger.info("Chunking successful.")
        return chunk_response
    else:
        logger.error(f"Chunking failed: {chunk_response.get('error')}")
        return None
