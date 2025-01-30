from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import os
import httpx
from typing import List, Optional, Dict, Any
import logging
import ollama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

ollama_client = ollama.Client(host="http://jetson-ollama.mitra-labs.ai")

# Configuration
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")

api_key_header = APIKeyHeader(name="X-API-Key")


class EmbedChunksRequest(BaseModel):
    chunks: List[str]


class EmbedTextRequest(BaseModel):
    text: str


def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key


async def embed(chunks: List[str]) -> List[List[float]]:
    """Embed a list of chunks using the Ollama API.

    Args:
        chunks (List[str]): The chunks to embed.

    Raises:
        HTTPException: If the Ollama API returns an error.

    Returns:
        List[List[float]]: The embeddings of the chunks.
    """
    headers = {"Content-Type": "application/json"}
    embedding_api_data = {"model": OLLAMA_MODEL, "input": chunks}
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{BASE_URL}/embed", json=embedding_api_data, headers=headers
        )
    if not response.status_code == 200:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ollama API not 200.",
        )
    response_json = response.json()
    if "embeddings" not in response_json:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ollama did not return embeddings.",
        )
    embeddings = response_json["embeddings"]
    # embeddings = ollama_client.embed(model=OLLAMA_MODEL, input=chunks).embeddings
    return embeddings


@app.post("/embed_chunks")
async def embed_chunks(data: EmbedChunksRequest, api_key: str = Depends(get_api_key)):
    embeddings = await embed(data.chunks)
    return {
        "status": "success",
        "embeddings": embeddings,
    }


@app.post("/embed_text")
async def embed_text(request: EmbedTextRequest, api_key: str = Depends(get_api_key)):
    embeddings = await embed([request.text])
    return {
        "status": "success",
        "embedding": embeddings[0],
    }


# Health check endpoint
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Embedding service: Test endpoint accessed successfully",
    }
