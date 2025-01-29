from typing import Tuple, List
import logging
import httpx

from .async_utils import batched_parallel


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

    def clear_database(self) -> int:
        """Clear the database.

        Returns:
            int: The number of documents deleted.
        """
        with httpx.Client() as client:
            response = client.delete(
                f"{self.base_url}/delete_all",
                headers={"X-API-Key": self.api_key},
            )
            response.raise_for_status()
            del_response = response.json()

        if not del_response.get("status") == "success":
            logger.error(f"Database clear failed: {del_response['error']}")

        deleted_count = del_response["count"]
        return deleted_count

    async def _store_in_database(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        language: str,
        filename: str,
    ) -> Tuple[List[int], List[int]]:
        documents = []
        n_chunks = len(chunks)
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
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/add",
                json={"documents": documents},
                headers=headers,
            )
            response.raise_for_status()
            add_response = response.json()

        if not add_response.get("status") == "success":
            raise Exception(f"Database storage failed: {add_response['error']}")

        n_added, n_skipped = add_response["added"], add_response["skipped"]
        return [n_added], [n_skipped]

    def store_in_database(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        language: str,
        filename: str,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = False,
    ) -> Tuple[int, int]:
        """Store documents in the database.

        Args:
            chunks (List[str]): The chunks to store.
            embeddings (List[List[float]]): The embeddings of the chunks.
            language (str): The language of the chunks.
            filename (str): The filename of the chunks.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to False.

        Returns:
            Tuple[int, int]: The number of documents added and skipped.
        """

        batched_store_in_database = batched_parallel(
            function=self._store_in_database,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Storing in database",
        )
        ns_added, ns_skipped = batched_store_in_database(
            chunks, embeddings, language, filename
        )
        return sum(ns_added), sum(ns_skipped)

    async def _query_database_async(
        self, query_texts: List[str], n_results: int = 5
    ) -> Tuple[List[str], List[str], List[str], List[float]]:
        """Async version of query_database."""
        ids, documents, metadatas, distances = [], [], [], []
        async with httpx.AsyncClient(timeout=300.0) as client:
            for query_text in query_texts:
                response = await client.post(
                    f"{self.base_url}/query",
                    json={"text": query_text, "n_results": n_results},
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                database_response = response.json()

            if not database_response.get("status") == "success":
                logger.error(f"Database query failed: {database_response['error']}")

            results = database_response["results"]
            ids.append([result["id"] for result in results])
            documents.append([result["document"] for result in results])
            metadatas.append([result["metadata"] for result in results])
            distances.append([result["distance"] for result in results])

        return ids, documents, metadatas, distances

    def query_database_batch(
        self,
        query_texts: List[str],
        n_results: int = 5,
        show_progress: bool = False,
    ) -> Tuple[List[str], List[str], List[str], List[float]]:
        """Query multiple texts in parallel batches.

        Args:
            query_texts (List[str]): List of query texts to search for.
            n_results (int, optional): Number of results to return per query. Defaults to 5.
            batch_size (int, optional): Size of each batch. Defaults to 20.
            limit_parallel (int, optional): Maximum number of parallel tasks. Defaults to 10.
            show_progress (bool, optional): Whether to show progress bar. Defaults to False.

        Returns:
            Tuple[List[str], List[str], List[Dict], List[float]]: (ids, documents, metadatas, distances)
            Each element in the tuple is a list of results, one per input query.
        """
        batched_query = batched_parallel(
            function=self._query_database_async,
            batch_size=50,
            limit_parallel=20,
            show_progress=show_progress,
            description="Querying database",
        )

        ids, documents, metadatas, distances = batched_query(query_texts, n_results)
        return ids, documents, metadatas, distances
