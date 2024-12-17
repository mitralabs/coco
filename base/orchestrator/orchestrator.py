import requests
import json
import os
import logging
import sys
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Output to console
    ],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.error("API_KEY environment variable must be set")
    sys.exit(1) # Exit if API key is missing

TRANSCRIPTION_URL_BASE = "http://127.0.0.1:8000"
CHUNK_URL_BASE = "http://127.0.0.1:8001"
EMBEDDING_URL_BASE = "http://127.0.0.1:8002"
DATABASE_URL_BASE = "http://127.0.0.1:8003"

TRANSCRIPTION_URL = TRANSCRIPTION_URL_BASE
CHUNK_URL = CHUNK_URL_BASE
EMBEDDING_URL = EMBEDDING_URL_BASE
DATABASE_URL = DATABASE_URL_BASE


def call_api(url, endpoint, method="GET", headers=None, data=None, files=None, timeout=100):
    #Modular function to call API endpoints with logging, error handling, and timeout
    full_url = f"{url}{endpoint}"
    
    try:
        logger.info(f"Calling {method} endpoint: {full_url}")
        response = requests.request(
            method, full_url, headers=headers, data=data, files=files, timeout=timeout
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        try:
            return response.json()
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response from {full_url}: Response Content: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling {full_url}: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                logger.error(f"Response: {e.response.text}")
            except Exception as e_in:
                logger.error(f"Could not print error message {e_in}")
        return None
    

def test_services():
    logger.info("Starting service tests...")
    headers = {"X-API-Key": API_KEY}
    
    # Test all services
    services = {
        "transcription": TRANSCRIPTION_URL,
        "chunking": CHUNK_URL,
        "embedding": EMBEDDING_URL,
        "database": DATABASE_URL
    }
    
    for service_name, url in services.items():
        test_response = call_api(url, "/test", headers=headers, timeout=10)
        if test_response and test_response.get("status") == "success":
            logger.info(f"{service_name.capitalize()} service test successful.")
        else:
            logger.error(f"{service_name.capitalize()} service test failed. Response: {test_response}")
            return False
    
    logger.info("All services tested successfully.")
    return True

def transcribe_audio(audio_file_path):
    """Transcribe an audio file using the transcription service with a timeout."""
    logger.info("Starting audio transcription...")
    
    headers = {"X-API-Key": API_KEY}
    
    try:
        with open(audio_file_path, "rb") as audio_file:
            files = {"audio_file": audio_file}
            transcription_response = call_api(
                TRANSCRIPTION_URL,
                "/transcribe/",
                method="POST",
                headers=headers,
                files=files,
            )
            
    except FileNotFoundError:
      logger.error(f"Error: Audio file not found at '{audio_file_path}'")
      return None
    
    if not transcription_response:
        logger.error("Transcription failed (check previous errors)")
        return None

    if transcription_response.get("status") == "success":
        logger.info("Transcription successful.")
        return transcription_response.get("document")
    else:
        logger.error(f"Transcription failed: {transcription_response.get('error')}")
        return None


def chunk_text(document):
    """Chunk the transcribed text using the chunking service with a timeout."""
    logger.info("Starting text chunking...")
    
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({"document": document})
    chunk_response = call_api(
        CHUNK_URL,
        "/chunk/json?chunk_size=1000&chunk_overlap=200", # These defaults can be parameterized
        method="POST",
        headers=headers,
        data=data
    )
    
    if not chunk_response:
        logger.error("Chunking failed (check previous errors)")
        return None
        
    if chunk_response.get("status") == "success":
        logger.info("Chunking successful.")
        return chunk_response
    else:
        logger.error(f"Chunking failed: {chunk_response.get('error')}")
        return None

def create_embeddings(chunks):
    """Create embeddings for the text chunks using the embedding service."""
    logger.info("Starting embedding creation...")
    
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({
        "status": "success",
        "chunks": chunks
    })
    
    embedding_response = call_api(
        EMBEDDING_URL,
        "/embed",
        method="POST",
        headers=headers,
        data=data
    )
    
    if not embedding_response:
        logger.error("Embedding creation failed (check previous errors)")
        return None
        
    if embedding_response.get("status") == "success":
        logger.info("Embedding creation successful.")
        return embedding_response.get("chunks")
    else:
        logger.error(f"Embedding creation failed: {embedding_response}")
        return None

def store_in_database(chunks):
    """Store the embedded chunks in the database."""
    logger.info("Storing documents in database...")
    
    # Convert chunks to documents format expected by database
    documents = []
    for chunk in chunks:
        documents.append({
            "text": chunk["text"],
            "metadata": chunk["metadata"]
        })
    
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    data = json.dumps({
        "status": "success",
        "documents": documents
    })
    
    database_response = call_api(
        DATABASE_URL,
        "/add",
        method="POST",
        headers=headers,
        data=data
    )
    
    if not database_response:
        logger.error("Database storage failed (check previous errors)")
        return None
        
    if database_response.get("status") == "success":
        logger.info("Database storage successful.")
        return database_response
    else:
        logger.error(f"Database storage failed: {database_response}")
        return None

def main():
    """Main orchestration logic."""
    if len(sys.argv) != 2:
        logger.error("Usage: python orchestrator/orchestrator.py <audio_file_path>")
        sys.exit(1)

    audio_file_path = sys.argv[1]

    if not os.path.exists(audio_file_path):
        logger.error(f"Error: Audio file not found at '{audio_file_path}'")
        sys.exit(1)
    
    logger.info(f"Starting orchestration for {audio_file_path}")

    if not test_services():
        logger.error("Service tests failed. Aborting orchestration.")
        sys.exit(1)

    transcription_doc = transcribe_audio(audio_file_path)
    if not transcription_doc:
         logger.error("Transcription failed. Aborting orchestration.")
         sys.exit(1)

    chunked_response = chunk_text(transcription_doc)
    if not chunked_response:
         logger.error("Chunking failed. Aborting orchestration.")
         sys.exit(1)
    
    embedded_chunks = create_embeddings(chunked_response.get("chunks", []))
    if not embedded_chunks:
         logger.error("Embedding failed. Aborting orchestration.")
         sys.exit(1)
    
    storage_response = store_in_database(embedded_chunks)
    if not storage_response:
         logger.error("Database storage failed. Aborting orchestration.")
         sys.exit(1)
         
    logger.info("Orchestration completed successfully.")


if __name__ == "__main__":
    main()