from typing import List
import json
import httpx

from .async_utils import batched_parallel


class EmbeddingClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def _create_embeddings(self, chunks: List[str]) -> List[List[float]]:
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                url=f"{self.base_url}/embed_chunks",
                headers=headers,
                data=json.dumps({"chunks": chunks}),
            )
            response.raise_for_status()
            embedding_response = response.json()
        if not embedding_response["status"] == "success":
            raise Exception(f"Embedding failed: {embedding_response}")
        return embedding_response["embeddings"]

    def create_embeddings(
        self,
        chunks: List[str],
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """Create embeddings for a list of chunks.

        Args:
            chunks (List[str]): The chunks to embed.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to False.

        Returns:
            List[List[float]]: The embeddings of the chunks.
        """
        batched_create_embeddings = batched_parallel(
            function=self._create_embeddings,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Creating embeddings",
        )
        return batched_create_embeddings(chunks)
