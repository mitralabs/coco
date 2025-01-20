from typing import Tuple, List
import logging
import json

from .utils import call_api
from .constants import API_KEY

logger = logging.getLogger(__name__)

DATABASE_URL_BASE = "http://127.0.0.1:8003"
DATABASE_URL = DATABASE_URL_BASE


# New function to query the database
def query_database(
    query_text: str, n_results: int = 5
) -> Tuple[List[str], List[str], List[str], List[float]]:
    """Retrieve the top n most similar results from the database service.

    Args:
        query_text (str): The query text to search for.
        n_results (int, optional): The number of results to return. Defaults to 5.

    Returns:
        Tuple[List[str], List[str], List[Dict], List[float]]: (ids, documents, metadatas, distances)
        metadata dict:
            - language: str (the chunk's language)
            - filename: str (the audio filename the chunk was extracted from)
            - chunk_index: int (the index of the chunk in the audio file)
            - total_chunks: int (the total number of chunks of the audio file)
    """
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({"text": query_text, "n_results": n_results})
    database_response = call_api(
        DATABASE_URL, "/query", method="POST", headers=headers, data=data
    )

    if not database_response.get("status") == "success":
        logger.error(f"Database query failed: {database_response['error']}")

    results = database_response["results"]
    ids = [result["id"] for result in results]
    documents = [result["document"] for result in results]
    metadatas = [result["metadata"] for result in results]
    distances = [result["distance"] for result in results]

    return ids, documents, metadatas, distances


def store_in_database(
    chunks: List[str], embeddings: List[List[float]], language: str, filename: str
):
    assert len(chunks) == len(
        embeddings
    ), "Number of chunks must match number of embeddings"

    n_chunks = len(chunks)
    documents = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        documents.append(
            {
                "text": chunk,
                "embedding": embedding,
                "metadata": {
                    "language": language,
                    "filename": filename,
                    "chunk_index": i,
                    "total_chunks": n_chunks,
                },
            }
        )

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({"documents": documents})
    database_response = call_api(
        DATABASE_URL, "/add", method="POST", headers=headers, data=data
    )

    if not database_response.get("status") == "success":
        logger.error(f"Database storage failed: {database_response['error']}")


def clear_database():
    headers = {"X-API-Key": API_KEY}
    response = call_api(DATABASE_URL, "/delete_all", method="DELETE", headers=headers)

    if not response.get("status") == "success":
        logger.error(f"Database clear failed: {response['error']}")


if __name__ == "__main__":
    query_database("Was weißt du?")
