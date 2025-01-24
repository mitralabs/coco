from typing import Tuple, List
import logging
import httpx


logger = logging.getLogger(__name__)


class DbApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    def query_database(
        self, query_text: str, n_results: int = 5
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
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/query",
                json={"text": query_text, "n_results": n_results},
                headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            database_response = response.json()

        if not database_response.get("status") == "success":
            logger.error(f"Database query failed: {database_response['error']}")

        results = database_response["results"]
        ids = [result["id"] for result in results]
        documents = [result["document"] for result in results]
        metadatas = [result["metadata"] for result in results]
        distances = [result["distance"] for result in results]

        return ids, documents, metadatas, distances

    def get_full_database(self):
        with httpx.Client() as client:
            response = client.get(
                f"{self.base_url}/get_all",
                headers={"X-API-Key": self.api_key},
            )
            response.raise_for_status()
            all_response = response.json()

        if not all_response.get("status") == "success":
            logger.error(f"Database get failed: {all_response['error']}")

        results = all_response["results"]
        ids = [result["id"] for result in results]
        documents = [result["document"] for result in results]
        metadatas = [result["metadata"] for result in results]

        return ids, documents, metadatas

    def store_in_database(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        language: str,
        filename: str,
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

        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/add",
                json={"documents": documents},
                headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            add_response = response.json()

        if not add_response.get("status") == "success":
            logger.error(f"Database storage failed: {add_response['error']}")

    def clear_database(self):
        with httpx.Client() as client:
            response = client.delete(
                f"{self.base_url}/delete_all",
                headers={"X-API-Key": self.api_key},
            )
            response.raise_for_status()
            del_response = response.json()

        if not del_response.get("status") == "success":
            logger.error(f"Database clear failed: {del_response['error']}")
