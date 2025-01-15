from dotenv import load_dotenv
load_dotenv() # call before imports because sdk package needs API KEY set
import os
import logging
import sys
from cocosdk import (
    call_api,
    transcribe_audio,
    chunk_text,
    create_embeddings,
    store_in_database,
    TRANSCRIPTION_URL,
    CHUNK_URL,
    EMBEDDING_URL,
    DATABASE_URL,
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],  # Output to console
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.error("API_KEY environment variable must be set")
    sys.exit(1)  # Exit if API key is missing

def test_services():
    logger.info("Starting service tests...")
    headers = {"X-API-Key": API_KEY}

    # Test all services
    services = {
        "transcription": TRANSCRIPTION_URL,
        "chunking": CHUNK_URL,
        "embedding": EMBEDDING_URL,
        "database": DATABASE_URL,
    }

    for service_name, url in services.items():
        test_response = call_api(url, "/test", headers=headers, timeout=10)
        if test_response and test_response.get("status") == "success":
            logger.info(f"{service_name.capitalize()} service test successful.")
        else:
            logger.error(
                f"{service_name.capitalize()} service test failed. Response: {test_response}"
            )
            return False

    logger.info("All services tested successfully.")
    return True


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
