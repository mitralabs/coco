import os
from pathlib import Path
import logging
import sys
from coco.chunking import chunk_text, CHUNK_URL
from coco.database import store_in_database, DATABASE_URL
from coco.embeddings import create_embeddings, EMBEDDING_URL
from coco.transcription import transcribe_audio, TRANSCRIPTION_URL
from coco.utils import call_api
from coco.rag import rag_query


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],  # Output to console
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "test")


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

    if not Path(audio_file_path).exists():
        logger.error(f"Error: Audio file not found at '{audio_file_path}'")
        sys.exit(1)

    logger.info(f"Starting orchestration for {audio_file_path}")

    if not test_services():
        logger.error("Service tests failed. Aborting orchestration.")
        sys.exit(1)

    text, language, filename = transcribe_audio(audio_file_path)
    chunks = chunk_text(text=text, chunk_size=1000, chunk_overlap=200)
    chunk_embeddings = create_embeddings(chunks)
    store_in_database(
        chunks=chunks,
        embeddings=chunk_embeddings,
        language=language,
        filename=filename,
    )

    logger.info("Orchestration completed successfully.")


if __name__ == "__main__":
    main()
    print(rag_query("What is rice usually served in?"))
