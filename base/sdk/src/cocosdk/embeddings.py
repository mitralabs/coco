import logging
import json

from .utils import call_api
from .constants import API_KEY

logger = logging.getLogger(__name__)

EMBEDDING_URL_BASE = "http://127.0.0.1:8002"
EMBEDDING_URL = EMBEDDING_URL_BASE


def create_embeddings(chunks):
    """Create embeddings for the text chunks using the embedding service."""
    logger.info("Starting embedding creation...")

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({"status": "success", "chunks": chunks})

    embedding_response = call_api(
        EMBEDDING_URL, "/embed", method="POST", headers=headers, data=data
    )
    # print(f"Embedding response: {embedding_response}")  # Print the embedding response

    if not embedding_response:
        logger.error("Embedding creation failed (check previous errors)")
        return None

    if embedding_response.get("status") == "success":
        logger.info("Embedding creation successful.")
        return embedding_response.get("chunks")
    else:
        logger.error(f"Embedding creation failed: {embedding_response}")
        return None
