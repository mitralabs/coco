from typing import List
import json
import asyncio
from tqdm import tqdm
import httpx

from .constants import API_KEY


EMBEDDING_URL_BASE = "http://127.0.0.1:8002"
EMBEDDING_URL = EMBEDDING_URL_BASE


async def _create_embedding_batch(
    client: httpx.AsyncClient, batch: List[str], headers: dict
) -> List[List[float]]:
    """Create embeddings for a single batch of chunks."""
    data = json.dumps({"chunks": batch})
    response = await client.post(
        f"{EMBEDDING_URL}/embed_chunks",
        headers=headers,
        data=data,
    )
    response.raise_for_status()
    embedding_response = response.json()
    if not embedding_response["status"] == "success":
        raise Exception(f"Embedding failed: {embedding_response}")
    return embedding_response["embeddings"]


async def _create_embeddings_async(
    chunks: List[str],
    headers: dict,
    batch_size: int = 10,
    show_progress: bool = False,
) -> List[List[float]]:
    """Async implementation of create_embeddings."""
    batches = [chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)]

    async with httpx.AsyncClient(timeout=300.0) as client:
        tasks = [_create_embedding_batch(client, batch, headers) for batch in batches]

        if show_progress:
            embeddings = []
            for f in tqdm(
                asyncio.as_completed(tasks),
                total=len(tasks),
                desc="Creating embeddings",
                unit="batch",
            ):
                batch_embeddings = await f
                embeddings.extend(batch_embeddings)
        else:
            results = await asyncio.gather(*tasks)
            embeddings = [e for batch in results for e in batch]

    return embeddings


def create_embeddings(
    chunks: List[str],
    batch_size: int = 10,
    show_progress: bool = False,
) -> List[List[float]]:
    """Create embeddings for a list of chunks using the embedding service.

    Args:
        chunks (List[str]): The chunks to embed.
        batch_size (int, optional): Number of chunks to process in each batch. Defaults to 10.
        show_progress (bool, optional): Whether to show a progress bar. Defaults to False.

    Raises:
        Exception: If the embedding service returns an error.

    Returns:
        List[List[float]]: The embeddings of the chunks.
    """
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    if len(chunks) <= batch_size:
        with httpx.Client(timeout=300.0) as client:
            return _create_embedding_batch(client, chunks, headers)
    return asyncio.run(
        _create_embeddings_async(chunks, headers, batch_size, show_progress)
    )
