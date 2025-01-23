from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import os
import chromadb
from typing import List
import httpx
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# API Key Authentication
EMBEDDING_URL = os.getenv("EMBEDDING_URL")
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")
api_key_header = APIKeyHeader(name="X-API-Key")


def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key


# Initialize Chroma client
client = chromadb.Client()

# Create or get Chroma collection
collection = client.get_or_create_collection("my_documents")


class DocumentMetadata(BaseModel):
    language: str
    filename: str
    chunk_index: int
    total_chunks: int


class Document(BaseModel):
    text: str
    embedding: List[float]
    metadata: DocumentMetadata


class AddRequest(BaseModel):
    documents: List[Document]


class QueryRequest(BaseModel):
    text: str
    n_results: int = 5


@app.post("/add")
async def add(data: AddRequest, api_key: str = Depends(get_api_key)):
    """
    Add documents to Chroma collection.
    """
    documents = [d.text for d in data.documents]
    metadatas = [dict(d.metadata) for d in data.documents]
    embeddings = [d.embedding for d in data.documents]
    ids = [str(uuid.uuid4()) for _ in range(len(documents))]
    collection.add(
        documents=documents, metadatas=metadatas, embeddings=embeddings, ids=ids
    )
    return {"status": "success"}


@app.post("/query")
async def query(request: QueryRequest, api_key: str = Depends(get_api_key)):
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        embedding_url = f"{EMBEDDING_URL}/embed_text"
        embedding_response = await client.post(
            embedding_url,
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
            json={"text": request.text},
        )

    if not embedding_response.status_code == 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "Failed to get embedding for query text"},
        )

    embedding_response_json = embedding_response.json()
    embedding = embedding_response_json["embedding"]

    results = collection.query(
        query_embeddings=[embedding],
        n_results=request.n_results,
        include=["documents", "metadatas", "distances"],
    )
    formatted_results = []
    for i in range(len(results["documents"])):
        formatted_results.append(
            {
                "id": results["ids"][i][0],
                "document": results["documents"][i][0],
                "metadata": results["metadatas"][i][0],
                "distance": (
                    results["distances"][i][0] if "distances" in results else None
                ),
            }
        )

    return {
        "status": "success",
        "count": len(formatted_results),
        "results": formatted_results,
    }


@app.get("/get_all")
async def get_all(api_key: str = Depends(get_api_key)):
    results = collection.get(include=["documents", "metadatas"])
    formatted_documents = []
    for i in range(len(results["documents"])):
        formatted_documents.append(
            {
                "id": results["ids"][i],
                "document": results["documents"][i],
                "metadata": results["metadatas"][i],
            }
        )

    return {
        "status": "success",
        "count": len(formatted_documents),
        "documents": formatted_documents,
    }


@app.delete("/delete_all")
async def delete_all(api_key: str = Depends(get_api_key)):
    results = collection.get()
    count = len(results["ids"])
    if count > 0:
        collection.delete(ids=results["ids"])
        # Get all document IDs first
    return {
        "status": "success",
        "count": count,
    }


# Super basic test endpoint
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Database service: Test endpoint accessed successfully",
    }
