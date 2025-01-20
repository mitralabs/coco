import logging
import json

from .utils import call_api
from .constants import API_KEY

logger = logging.getLogger(__name__)

DATABASE_URL_BASE = "http://127.0.0.1:8003"
DATABASE_URL = DATABASE_URL_BASE

# New function to query the database
def query_database(query_text, n_results=5):
    logger.info("Querying documents from database...")

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({"query_text": query_text, "n_results": n_results})

    database_response = call_api(
        DATABASE_URL, "/query", method="POST", headers=headers, data=data
    )

    if not database_response:
        logger.error("Database query failed (check previous errors)")
        return None

    if database_response.get("status") == "success":
        logger.info("Database query successful.")
        return database_response.get("results")  # Return the chunks
    else:
        logger.error(f"Database query failed: {database_response}")
        return None

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

if __name__ == "__main__":
    query_database("Was weißt du?")