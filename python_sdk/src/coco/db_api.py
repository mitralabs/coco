from typing import Tuple, List, Optional
import logging
import httpx
import datetime

from .async_utils import batched_parallel


logger = logging.getLogger(__name__)


class DbApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    def get_max_embedding_dim(self):
        """Returns the maximum supported vector dimension.

        Raises:
            Exception: If the database service returns an error.

        Returns:
            int: The maximum supported vector dimension.
        """
        with httpx.Client() as client:
            response = client.get(
                f"{self.base_url}/max_embedding_dim",
                headers={"X-API-Key": self.api_key},
            )
            response.raise_for_status()
            max_embedding_dim_response = response.json()

        if not max_embedding_dim_response.get("status") == "success":
            raise Exception(
                f"Database max embedding dim failed: {max_embedding_dim_response['error']}"
            )

        return max_embedding_dim_response["max_embedding_dim"]

    def get_closest(
        self,
        embedding: List[float],
        n_results: int = 5,
        start_date_time: Optional[datetime.datetime] = None,
        end_date_time: Optional[datetime.datetime] = None,
        session_id: Optional[int] = None,
        contains_substring: Optional[str] = None,
    ):
        """Retrieve the closest results from the database service.

        Args:
            embedding (List[float]): The embedding to search for.
            n_results (int, optional): The number of results to return. Defaults to 5.
            start_date_time (datetime.datetime, optional): Only return documents with a date greater than or equal to this. Defaults to None.
            end_date_time (datetime.datetime, optional): Only return documents with a date less than or equal to this. Defaults to None.
            session_id (int, optional): Only return documents with this session ID. Defaults to None.
            contains_substring (str, optional): Only return documents that contain this substring. Defaults to None.
        Returns:
            Tuple[List[str], List[str], List[Dict], List[float]]: (ids, documents, metadatas, distances)
            metadata dict:
                - language: str (the chunk's language)
                - filename: str (the audio filename the chunk was extracted from)
                - chunk_index: int (the index of the chunk in the audio file)
                - session_id: int (the session ID)
                - date_time: str (ISO format date string, or None if no date is present)
        """
        with httpx.Client() as client:
            request_data = {"embedding": embedding, "n_results": n_results}
            if start_date_time:
                request_data["start_date_time"] = start_date_time.isoformat()
            if end_date_time:
                request_data["end_date_time"] = end_date_time.isoformat()
            if session_id is not None:
                request_data["session_id"] = session_id
            if contains_substring:
                request_data["contains_substring"] = contains_substring
            response = client.post(
                f"{self.base_url}/get_closest",
                json=request_data,
                headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            closest_response = response.json()

        if not closest_response.get("status") == "success":
            logger.error(f"Database get closest failed: {closest_response['error']}")

        results = closest_response["results"]
        ids = [result["id"] for result in results]
        documents = [result["document"] for result in results]
        metadatas = [result["metadata"] for result in results]
        distances = [result["distance"] for result in results]

        return ids, documents, metadatas, distances

    async def _get_closest_multiple(
        self,
        embeddings: List[List[float]],
        n_results: int = 5,
        start_date_time: Optional[datetime.datetime] = None,
        end_date_time: Optional[datetime.datetime] = None,
        session_id: Optional[int] = None,
    ):
        """Internal async method to get closest results from the database.

        Args:
            embeddings: List of embeddings to search for
            n_results: Number of results to return per embedding
            start_date_time: Optional datetime object to filter results (inclusive)
            end_date_time: Optional datetime object to filter results (inclusive)
            session_id: Optional session ID to filter results

        Note:
            start_date_time and end_date_time must be datetime objects, not strings
        """
        async with httpx.AsyncClient(timeout=300.0) as client:
            request_data = {"embeddings": embeddings, "n_results": n_results}
            if start_date_time:
                request_data["start_date_time"] = start_date_time.isoformat()
            if end_date_time:
                request_data["end_date_time"] = end_date_time.isoformat()
            if session_id is not None:
                request_data["session_id"] = session_id

            response = await client.post(
                f"{self.base_url}/get_multiple_closest",
                json=request_data,
                headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            closest_response = response.json()

        if not closest_response.get("status") == "success":
            logger.error(
                f"Database get multiple closest failed: {closest_response['error']}"
            )

        all_formatted_results = closest_response["results"]
        query_answers = []
        for formatted_results in all_formatted_results:
            ids = [result["id"] for result in formatted_results]
            documents = [result["document"] for result in formatted_results]
            metadatas = [result["metadata"] for result in formatted_results]
            distances = [result["distance"] for result in formatted_results]
            query_answers.append((ids, documents, metadatas, distances))

        return query_answers

    def get_closest_multiple(
        self,
        embeddings: List[List[float]],
        n_results: int = 5,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
        start_date_time: Optional[datetime.datetime] = None,
        end_date_time: Optional[datetime.datetime] = None,
        session_id: Optional[int] = None,
    ):
        """Get the closest results from the database service for multiple embeddings.

        Args:
            embeddings (List[List[float]]): The embeddings to search for.
            n_results (int, optional): The number of results to return for each embedding. Defaults to 5.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.
            start_date_time (datetime.datetime, optional): Only return documents with a date greater than or equal to this. Defaults to None.
            end_date_time (datetime.datetime, optional): Only return documents with a date less than or equal to this. Defaults to None.
            session_id (int, optional): Only return documents with this session ID. Defaults to None.

        Returns:
            List[Tuple[List[str], List[str], List[Dict], List[float]]]: The closest results for each embedding.
            metadata dict:
                - language: str (the chunk's language)
                - filename: str (the audio filename the chunk was extracted from)
                - chunk_index: int (the index of the chunk in the audio file)
                - session_id: int (the session ID)
                - date_time: str (ISO format date string, or None if no date is present)
        """
        batched_get_multiple_closest = batched_parallel(
            function=self._get_closest_multiple,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Getting multiple closest",
        )
        return batched_get_multiple_closest(
            embeddings, n_results, start_date_time, end_date_time, session_id
        )

    def get_full_database(
        self,
        start_date_time: Optional[datetime.datetime] = None,
        end_date_time: Optional[datetime.datetime] = None,
    ):
        """Get all documents in the database.

        Args:
            start_date_time (datetime.datetime, optional): Only return documents with a date greater than or equal to this. Defaults to None.
            end_date_time (datetime.datetime, optional): Only return documents with a date less than or equal to this. Defaults to None.

        Returns:
            Tuple[List[str], List[str], List[Dict]]: (ids, documents, metadatas)
            metadata dict includes:
                - language: str (the chunk's language)
                - filename: str (the audio filename the chunk was extracted from)
                - chunk_index: int (the index of the chunk in the audio file)
                - session_id: int (the session ID)
                - date_time: str (ISO format date string, or None if no date is present)
        """
        with httpx.Client() as client:
            params = {}
            if start_date_time:
                params["start_date_time"] = start_date_time.isoformat()
            if end_date_time:
                params["end_date_time"] = end_date_time.isoformat()

            response = client.get(
                f"{self.base_url}/get_all",
                params=params,
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

    def get_by_session_id(self, session_id: str) -> dict:
        """Get all documents that belong to a specific session.

        Args:
            session_id (str): The session ID to search for

        Returns:
            dict: Response containing the documents and their metadata
        """
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/get_by_session_id",
                params={"session_id": session_id},
                headers={"X-API-Key": self.api_key},
            )
            response.raise_for_status()
            return response.json()

    def get_by_date(
        self,
        start_date_time: Optional[datetime.datetime] = None,
        end_date_time: Optional[datetime.datetime] = None,
    ):
        """Get documents filtered by date range.

        Args:
            start_date_time (datetime.datetime, optional): Only return documents with a date greater than or equal to this. Defaults to None.
            end_date_time (datetime.datetime, optional): Only return documents with a date less than or equal to this. Defaults to None.

        Returns:
            Tuple[List[str], List[str], List[Dict]]: (ids, documents, metadatas)
            metadata dict includes:
                - language: str (the chunk's language)
                - filename: str (the audio filename the chunk was extracted from)
                - chunk_index: int (the index of the chunk in the audio file)
                - session_id: int (the session ID)
                - date_time: str (ISO format date string, or None if no date is present)
        """
        with httpx.Client() as client:
            params = {}
            if start_date_time:
                params["start_date_time"] = start_date_time.isoformat()
            if end_date_time:
                params["end_date_time"] = end_date_time.isoformat()

            response = client.post(
                f"{self.base_url}/get_by_date",
                json=params,
                headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            results_response = response.json()

        if not results_response.get("status") == "success":
            logger.error(f"Database get_by_date failed: {results_response['error']}")

        results = results_response["results"]
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

    def delete_by_session_id(self, session_id: int):
        """Delete all documents with the specified session_id.

        Args:
            session_id (int): The session ID to delete documents for

        Returns:
            dict: Response containing the number of documents deleted
        """
        with httpx.Client() as client:
            response = client.delete(
                f"{self.base_url}/delete_by_session_id",
                params={"session_id": session_id},
                headers={"X-API-Key": self.api_key},
            )
            response.raise_for_status()
            return response.json()

    def delete_by_date(
        self,
        start_date_time: Optional[datetime.datetime] = None,
        end_date_time: Optional[datetime.datetime] = None,
    ):
        """Delete documents within a specified date range.

        Args:
            start_date_time (datetime.datetime, optional): Delete documents with a date greater than or equal to this. Defaults to None.
            end_date_time (datetime.datetime, optional): Delete documents with a date less than or equal to this. Defaults to None.

        Returns:
            dict: Response containing the number of documents deleted
        """
        with httpx.Client() as client:
            params = {}
            if start_date_time:
                params["start_date_time"] = start_date_time.isoformat()
            if end_date_time:
                params["end_date_time"] = end_date_time.isoformat()

            response = client.delete(
                f"{self.base_url}/delete_by_date",
                params=params,
                headers={"X-API-Key": self.api_key},
            )
            response.raise_for_status()
            return response.json()

    async def _store_multiple(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        language: str,
        filename: str,
        session_id: int,
        date_times: List[Optional[datetime.datetime]] = None,
        chunk_indices: List[int] = None,
    ) -> Tuple[List[int], List[int]]:
        documents = []

        # Use provided chunk indices or default to array indices
        if chunk_indices is None:
            chunk_indices = list(range(len(chunks)))

        for i, (chunk, embedding, chunk_index, doc_date_time) in enumerate(
            zip(chunks, embeddings, chunk_indices, date_times or [None] * len(chunks))
        ):
            documents.append(
                {
                    "text": chunk,
                    "embedding": embedding,
                    "metadata": {
                        "language": language,
                        "filename": filename,
                        "chunk_index": chunk_index,
                        "session_id": session_id,
                        "date_time": (
                            doc_date_time.isoformat() if doc_date_time else None
                        ),
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

    def store_multiple(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        language: str,
        filename: str,
        session_id: int,
        date_times: List[Optional[datetime.datetime]] = None,
        chunk_indices: List[int] = None,
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
            session_id (int): The session ID to associate with the chunks.
            date_times (List[Optional[datetime.datetime]], optional): The dates of the chunks. Defaults to None.
            chunk_indices (List[int], optional): The indices of the chunks. Defaults to None (will use array indices).
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to False.

        Returns:
            Tuple[int, int]: The number of documents added and skipped.
        """

        batched_store_multiple = batched_parallel(
            function=self._store_multiple,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Storing in database",
        )
        ns_added, ns_skipped = batched_store_multiple(
            chunks,
            embeddings,
            language,
            filename,
            session_id,
            date_times,
            chunk_indices,
        )
        return sum(ns_added), sum(ns_skipped)
