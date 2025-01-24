import os
from pathlib import Path
import logging
import sys
from coco import CocoClient, rag_query

cc = CocoClient(
    chunking_base="http://127.0.0.1:8001",
    embedding_base="http://127.0.0.1:8002",
    db_api_base="http://127.0.0.1:8003",
    transcription_base="http://127.0.0.1:8000",
    api_key="test",
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],  # Output to console
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "test")


def main():
    """Main orchestration logic."""
    if len(sys.argv) != 2:
        logger.error("Usage: python orchestrator/orchestrator.py <audio_file_path>")
        sys.exit(1)

    audio_file_path = sys.argv[1]

    if not Path(audio_file_path).exists():
        logger.error(f"Error: Audio file not found at '{audio_file_path}'")
        sys.exit(1)

    logger.info("Starting health check...")
    cc.health_check()
    logger.info("Health check completed successfully.")

    logger.info(f"Starting orchestration for {audio_file_path}")
    text, language, filename = cc.transcription.transcribe_audio(audio_file_path)
    chunks = cc.chunking.chunk_text(text=text, chunk_size=1000, chunk_overlap=200)
    chunk_embeddings = cc.embedding.create_embeddings(chunks)
    cc.db_api.store_in_database(
        chunks=chunks,
        embeddings=chunk_embeddings,
        language=language,
        filename=filename,
    )

    logger.info("Orchestration completed successfully.")


if __name__ == "__main__":
    main()
    print(rag_query("What is rice usually served in?"))
