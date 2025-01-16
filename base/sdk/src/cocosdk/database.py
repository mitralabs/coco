import logging
import json

from .utils import call_api
from .constants import API_KEY

logger = logging.getLogger(__name__)

DATABASE_URL_BASE = "http://127.0.0.1:8003"
DATABASE_URL = DATABASE_URL_BASE


def store_in_database(chunks):
    logger.info("Storing documents in database...")

    # Convert chunks to documents format expected by database
    documents = []
    for chunk in chunks:
        documents.append(
            {
                "text": chunk["text"],
                "metadata": chunk["metadata"],
                "embeddings": chunk["embedding"],
            }
        )

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({"status": "success", "documents": documents})

    database_response = call_api(
        DATABASE_URL, "/add", method="POST", headers=headers, data=data
    )
    # print(f"Database response: {database_response}")  # Print the database response

    if not database_response:
        logger.error("Database storage failed (check previous errors)")
        return None

    if database_response.get("status") == "success":
        logger.info("Database storage successful.")
        return database_response
    else:
        logger.error(f"Database storage failed: {database_response}")
        return None
