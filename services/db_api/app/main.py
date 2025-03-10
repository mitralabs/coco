from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, field_validator
import os
from typing import List
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, or_
import datetime

from db import get_db, EMBEDDING_DIM
from models import Document as DbDocument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

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
    date: datetime.date = None


class Document(BaseModel):
    text: str
    embedding: List[float]
    metadata: DocumentMetadata

    @field_validator("embedding", mode="before")
    @classmethod
    def pad_embedding(cls, v: List[float]) -> List[float]:
        if len(v) > EMBEDDING_DIM:
            raise ValueError(
                f"Embedding dimension cannot be larger than {EMBEDDING_DIM}"
            )
        if len(v) < EMBEDDING_DIM:
            v += [0.0] * (EMBEDDING_DIM - len(v))
        return v


class AddRequest(BaseModel):
    documents: List[Document]


class GetClosestRequest(BaseModel):
    embedding: List[float]
    n_results: int = 5
    start_date: datetime.date = None
    end_date: datetime.date = None

    @field_validator("embedding", mode="before")
    @classmethod
    def pad_embedding(cls, v: List[float]) -> List[float]:
        if len(v) > EMBEDDING_DIM:
            raise ValueError(
                f"Embedding dimension cannot be larger than {EMBEDDING_DIM}"
            )
        if len(v) < EMBEDDING_DIM:
            v += [0.0] * (EMBEDDING_DIM - len(v))
        return v


class GetMultipleClosestRequest(BaseModel):
    embeddings: List[List[float]]
    n_results: int = 5
    start_date: datetime.date = None
    end_date: datetime.date = None

    @field_validator("embeddings", mode="before")
    @classmethod
    def pad_embeddings(cls, v: List[List[float]]) -> List[List[float]]:
        for i, embedding in enumerate(v):
            if len(embedding) > EMBEDDING_DIM:
                raise ValueError(
                    f"Embedding dimension cannot be larger than {EMBEDDING_DIM}"
                )
            if len(embedding) < EMBEDDING_DIM:
                v[i] += [0.0] * (EMBEDDING_DIM - len(embedding))
        return v


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


def get_closest_from_embeddings(
    db: Session,
    embeddings: List[List[float]],
    n_results: int,
    start_date: datetime.date = None,
    end_date: datetime.date = None,
):
    all_formatted_results = []
    for embedding in embeddings:
        formatted_results = []
        query = select(
            DbDocument,
            DbDocument.embedding.cosine_distance(embedding).label("distance"),
        )

        if start_date:
            query = query.where(
                or_(DbDocument.date >= start_date, DbDocument.date == None)
            )
        if end_date:
            query = query.where(
                or_(DbDocument.date <= end_date, DbDocument.date == None)
            )

        query = query.order_by(DbDocument.embedding.cosine_distance(embedding)).limit(
            n_results
        )

        results = db.execute(query)
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
                        "date": doc.date.isoformat() if doc.date else None,
                    },
                    "distance": distance,
                }
            )
        all_formatted_results.append(formatted_results)
    return all_formatted_results


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
            date=doc.metadata.date,
        )
        db.add(db_doc)
        added_count += 1

    db.commit()
    return {"status": "success", "added": added_count, "skipped": skipped_count}


@app.post("/get_closest")
async def get_closest(
    request: GetClosestRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    formatted_results = get_closest_from_embeddings(
        db=db,
        embeddings=[request.embedding],
        n_results=request.n_results,
        start_date=request.start_date,
        end_date=request.end_date,
    )[0]
    return {
        "status": "success",
        "count": len(formatted_results),
        "results": formatted_results,
    }


@app.post("/get_multiple_closest")
async def get_multiple_closest(
    request: GetMultipleClosestRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    all_formatted_results = get_closest_from_embeddings(
        db=db,
        embeddings=request.embeddings,
        n_results=request.n_results,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    assert len(all_formatted_results) > 0
    return {
        "status": "success",
        "embedding_count": len(all_formatted_results),
        "docs_per_embedding_count": len(all_formatted_results[0]),
        "results": all_formatted_results,
    }


@app.get("/get_all")
async def get_all(
    start_date: datetime.date = None,
    end_date: datetime.date = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    query = select(DbDocument)
    if start_date:
        query = query.where(or_(DbDocument.date >= start_date, DbDocument.date == None))
    if end_date:
        query = query.where(or_(DbDocument.date <= end_date, DbDocument.date == None))

    results = db.execute(query).scalars().all()
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
                    "date": result.date.isoformat() if result.date else None,
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


@app.get("/max_embedding_dim")
async def max_embedding_dim(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "max_embedding_dim": EMBEDDING_DIM,
    }


@app.delete("/delete_by_date")
async def delete_by_date(
    start_date: datetime.date = None,
    end_date: datetime.date = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Delete documents within a specified date range.
    If no dates are provided, no documents will be deleted.
    """
    query = delete(DbDocument)
    if start_date:
        query = query.where(DbDocument.date >= start_date)
    if end_date:
        query = query.where(DbDocument.date <= end_date)

    result = db.execute(query)
    db.commit()

    return {
        "status": "success",
        "count": result.rowcount,
    }


@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Database service: Test endpoint accessed successfully",
    }
