from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import chromadb
from typing import List, Optional, Dict, Any

load_dotenv()  # Load environment variables from .env file

app = FastAPI()

# API Key Authentication
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
    language: Optional[str]
    filename: Optional[str]
    chunk_index: int
    total_chunks: int

class Document(BaseModel):
    text: str
    metadata: DocumentMetadata

class DocumentsRequest(BaseModel):
    status: str
    documents: List[Document]

class DocumentsResponse(BaseModel):
    status: str
    message: str

class QueryRequest(BaseModel):
    query_text: str
    n_results: int = 5

class QueryResponse(BaseModel):
    status: str
    results: List[Dict[str, Any]]

@app.post("/add", response_model=DocumentsResponse)
async def add_documents(request: DocumentsRequest, api_key: str = Depends(get_api_key)):
    """
    Add documents to Chroma collection.
    """
    try:
        documents = [doc.text for doc in request.documents]
        metadatas = [
            {
                "language": doc.metadata.language,
                "filename": doc.metadata.filename,
                "chunk_index": doc.metadata.chunk_index,
                "total_chunks": doc.metadata.total_chunks
            }
            for doc in request.documents
        ]
        ids = [f"doc_{i}" for i in range(len(documents))]

        collection.add(documents=documents, metadatas=metadatas, ids=ids)

        return DocumentsResponse(status="success", message="Documents added successfully")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add documents: {str(e)}"
        )

@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest, api_key: str = Depends(get_api_key)):
    """
    Query similar documents from Chroma collection.
    """
    try:
        results = collection.query(
            query_texts=[request.query_text],
            n_results=request.n_results,
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

        return QueryResponse(
            status="success",
            results=results
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query documents: {str(e)}"
        )

# Super basic test endpoint
@app.get("/test")
async def test_endpoint(api_key: str = Depends(get_api_key)):
    return {"status": "success", "message": "Test endpoint accessed successfully"}
