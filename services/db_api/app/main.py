from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, field_validator
import os
from typing import List, Optional
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
    session_id: int
    date_time: Optional[datetime.datetime] = None


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
    start_date_time: datetime.datetime = None
    end_date_time: datetime.datetime = None
    session_id: Optional[int] = None

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
    start_date_time: datetime.datetime = None
    end_date_time: datetime.datetime = None
    session_id: Optional[int] = None

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
    start_date_time: Optional[datetime.datetime] = None,
    end_date_time: Optional[datetime.datetime] = None,
    session_id: Optional[int] = None,
):
    all_formatted_results = []
    for embedding in embeddings:
        formatted_results = []
        query = select(
            DbDocument,
            DbDocument.embedding.cosine_distance(embedding).label("distance"),
        )

        if start_date_time:
            query = query.where(
                or_(
                    DbDocument.date_time >= start_date_time,
                    DbDocument.date_time == None,
                )
            )
        if end_date_time:
            query = query.where(
                or_(
                    DbDocument.date_time <= end_date_time,
                    DbDocument.date_time == None,
                )
            )
        if session_id is not None:
            query = query.where(DbDocument.session_id == session_id)

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
                        "session_id": doc.session_id,
                        "date_time": (
                            doc.date_time.isoformat() if doc.date_time else None
                        ),
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
            session_id=doc.metadata.session_id,
            date_time=doc.metadata.date_time,
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
        start_date_time=request.start_date_time,
        end_date_time=request.end_date_time,
        session_id=request.session_id,
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
        start_date_time=request.start_date_time,
        end_date_time=request.end_date_time,
        session_id=request.session_id,
    )
    assert len(all_formatted_results) > 0
    return {
        "status": "success",
        "embedding_count": len(all_formatted_results),
        "docs_per_embedding_count": len(all_formatted_results[0]),
        "results": all_formatted_results,
    }


@app.post("/get_by_session_id")
async def get_by_session_id(
    session_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Retrieve all documents that match the given session_id.
    """
    query = select(DbDocument).where(DbDocument.session_id == session_id)
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
                    "session_id": result.session_id,
                    "date_time": (
                        result.date_time.isoformat() if result.date_time else None
                    ),
                },
            }
        )

    return {
        "status": "success",
        "count": len(formatted_results),
        "results": formatted_results,
    }


@app.post("/get_by_date")
async def get_by_date(
    start_date_time: Optional[datetime.datetime] = None,
    end_date_time: Optional[datetime.datetime] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Retrieve all documents within the specified date range.
    If no dates are provided, all documents will be retrieved.
    """
    query = select(DbDocument)

    if start_date_time:
        query = query.where(DbDocument.date_time >= start_date_time)
    if end_date_time:
        query = query.where(DbDocument.date_time <= end_date_time)

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
                    "session_id": result.session_id,
                    "date_time": (
                        result.date_time.isoformat() if result.date_time else None
                    ),
                },
            }
        )

    return {
        "status": "success",
        "count": len(formatted_results),
        "results": formatted_results,
    }


@app.get("/get_all")
async def get_all(
    start_date_time: Optional[datetime.datetime] = None,
    end_date_time: Optional[datetime.datetime] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    query = select(DbDocument)
    if start_date_time:
        query = query.where(
            or_(DbDocument.date_time >= start_date_time, DbDocument.date_time == None)
        )
    if end_date_time:
        query = query.where(
            or_(DbDocument.date_time <= end_date_time, DbDocument.date_time == None)
        )

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
                    "session_id": result.session_id,
                    "date_time": (
                        result.date_time.isoformat() if result.date_time else None
                    ),
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


@app.delete("/delete_by_session_id")
async def delete_by_session_id(
    session_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Delete all documents with the specified session_id.
    """
    query = delete(DbDocument).where(DbDocument.session_id == session_id)

    result = db.execute(query)
    db.commit()

    return {
        "status": "success",
        "count": result.rowcount,
    }


@app.delete("/delete_by_date")
async def delete_by_date(
    start_date_time: datetime.datetime = None,
    end_date_time: datetime.datetime = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Delete documents within a specified date range.
    If no dates are provided, no documents will be deleted.
    """
    query = delete(DbDocument)
    if start_date_time:
        query = query.where(DbDocument.date_time >= start_date_time)
    if end_date_time:
        query = query.where(DbDocument.date_time <= end_date_time)

    result = db.execute(query)
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


@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Database service: Test endpoint accessed successfully",
    }
