from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Optional, Dict, Any


app = FastAPI(debug=os.getenv("DEBUG") == "True")

# API Key Authentication
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")
api_key_header = APIKeyHeader(name="X-API-Key")


class ChunkJsonRequest(BaseModel):
    text: str
    chunk_size: int = 1000
    chunk_overlap: int = 200


def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key


def chunk(text: str, chunk_size: int, chunk_overlap: int):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )
    chunks: List[str] = text_splitter.split_text(text)
    return chunks


@app.post("/chunk/json")
async def chunk_json(data: ChunkJsonRequest, api_key: str = Depends(get_api_key)):
    chunks = chunk(
        text=data.text, chunk_size=data.chunk_size, chunk_overlap=data.chunk_overlap
    )
    response = JSONResponse(
        {
            "status": "success",
            "num_chunks": len(chunks),
            "chunks": chunks,
        }
    )
    return response


# Keep the test endpoint for basic connectivity testing
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {
        "status": "success",
        "message": "Chunking service: Test endpoint accessed successfully",
    }
