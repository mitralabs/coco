from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import os
from typing import List
import httpx
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from db import get_db
from db import Document as DbDocument


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

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


def nearest_neighbor_query(db: Session, query_embedding: List[float], n_results: int):
    query = (
        select(
            DbDocument,
            DbDocument.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .order_by(DbDocument.embedding.cosine_distance(query_embedding))
        .limit(n_results)
    )
    results = db.execute(query)
    return results


@app.post("/add")
async def add(
    data: AddRequest, db: Session = Depends(get_db), api_key: str = Depends(get_api_key)
):
    """
    Add documents to postgres database. Skip if document text already exists.
    """
    added_count = 0
    skipped_count = 0

    for doc in data.documents:
        # todo - this is inefficient as hell
        # todo - so do this properly some time
        existing_doc = db.query(DbDocument).filter(DbDocument.text == doc.text).first()
        if existing_doc:
            skipped_count += 1
            continue
        db_doc = DbDocument(
            text=doc.text,
            embedding=doc.embedding,
            language=doc.metadata.language,
            filename=doc.metadata.filename,
            chunk_index=doc.metadata.chunk_index,
            total_chunks=doc.metadata.total_chunks,
        )
        db.add(db_doc)
        added_count += 1

    db.commit()
    return {"status": "success", "added": added_count, "skipped": skipped_count}


@app.post("/query")
async def query(
    request: QueryRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
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

    results = nearest_neighbor_query(db, embedding, request.n_results)
    formatted_results = []
    for doc, distance in results:
        formatted_results.append(
            {
                "id": doc.id,
                "document": doc.text,
                "metadata": {
                    "language": doc.language,
                    "filename": doc.filename,
                    "chunk_index": doc.chunk_index,
                    "total_chunks": doc.total_chunks,
                },
                "distance": distance,
            }
        )

    return {
        "status": "success",
        "count": len(formatted_results),
        "results": formatted_results,
    }


@app.get("/get_all")
async def get_all(db: Session = Depends(get_db), api_key: str = Depends(get_api_key)):
    results = db.execute(select(DbDocument)).scalars().all()
    formatted_results = []
    for result in results:
        formatted_results.append(
            {
                "id": result.id,
                "document": result.text,
                "metadata": {
                    "language": result.language,
                    "filename": result.filename,
                    "chunk_index": result.chunk_index,
                    "total_chunks": result.total_chunks,
                },
            }
        )

    return {
        "status": "success",
        "count": len(formatted_results),
        "results": formatted_results,
    }


@app.delete("/delete_all")
async def delete_all(
    db: Session = Depends(get_db), api_key: str = Depends(get_api_key)
):
    result = db.execute(delete(DbDocument))
    db.commit()
    return {
        "status": "success",
        "count": result.rowcount,
    }


# Super basic test endpoint
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Database service: Test endpoint accessed successfully",
    }
