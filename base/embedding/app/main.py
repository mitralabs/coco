from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import os
import httpx
from typing import List, Optional, Dict, Any
import json


app = FastAPI()

# Configuration
API_KEY = os.getenv("API_KEY")
BASE_URL = "https://ollama.mitra-labs.ai/api"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nomic-embed-text")

if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")

api_key_header = APIKeyHeader(name="X-API-Key")

class ChunkMetadata(BaseModel):
    language: Optional[str]
    filename: Optional[str]
    chunk_index: int
    total_chunks: int

class Chunk(BaseModel):
    text: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None

class ChunksRequest(BaseModel):
    status: str
    chunks: List[Chunk]

class ChunksResponse(BaseModel):
    status: str
    chunks: List[Chunk]

def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key

@app.post("/embed", response_model=ChunksResponse)
async def embed_text(request: ChunksRequest, api_key: str = Depends(get_api_key)):
    """
    Get embeddings for chunks of text using the Ollama API
    """
    try:
        # Extract just the texts from the chunks
        texts = [chunk.text for chunk in request.chunks]
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": OLLAMA_MODEL,
            "input": texts
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/embed", json=payload, headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ollama API error: {response.status_code} - {response.text}"
            )
        
        response_json = response.json()
        
        if "embeddings" not in response_json:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid response from Ollama API"
            )
        
        # Add embeddings to chunks
        for chunk, embedding in zip(request.chunks, response_json["embeddings"]):
            chunk.embedding = embedding
        
        # Return the same structure with added embeddings
        return ChunksResponse(
            status="success",
            chunks=request.chunks
        )
        
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error connecting to Ollama API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# Health check endpoint
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {"status": "success", "message": "Embedding service: Test endpoint accessed successfully"}