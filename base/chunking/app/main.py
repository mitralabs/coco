from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Optional, Dict, Any


app = FastAPI()

# API Key Authentication
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable must be set")
api_key_header = APIKeyHeader(name="X-API-Key")

class DocumentInput(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None

class DocumentRequest(BaseModel):
    document: DocumentInput

def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key

def process_text(text: str, chunk_size: int, chunk_overlap: int, metadata: Optional[Dict[str, Any]] = None):
    # Initialize the text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )
    
    # Split the text into chunks
    chunks: List[str] = text_splitter.split_text(text)
    
    # Prepare the response
    return {
        "status": "success",
        "chunks": [
            {
                "text": chunk,
                "metadata": {
                    **(metadata or {}),
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
            }
            for i, chunk in enumerate(chunks)
        ],
        "num_chunks": len(chunks)
    }

@app.post("/chunk/file")
async def chunk_file(
    file: UploadFile = File(...),
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    api_key: str = Depends(get_api_key)
):
    """Endpoint to chunk text from file upload"""
    try:
        content = await file.read()
        text = content.decode('utf-8')
        
        return JSONResponse(content=process_text(
            text,
            chunk_size,
            chunk_overlap,
            metadata={"source_type": "file", "filename": file.filename}
        ))
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )

@app.post("/chunk/json")
async def chunk_json(
    document: DocumentRequest,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    api_key: str = Depends(get_api_key)
):
    """Endpoint to chunk text from JSON input"""
    try:
        return JSONResponse(content=process_text(
            document.document.text,
            chunk_size,
            chunk_overlap,
            metadata=document.document.metadata
        ))
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing JSON: {str(e)}"
        )

# Keep the test endpoint for basic connectivity testing
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {"status": "success", "message": "Chunking service: Test endpoint accessed successfully"}