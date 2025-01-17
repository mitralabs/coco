from dotenv import load_dotenv
load_dotenv() # call before imports because sdk package needs API KEY set
import os
import json
import logging
import sys
from cocosdk import (
    call_api,
    transcribe_audio,
    chunk_text,
    create_embeddings,
    store_in_database,
    query_database,
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
    
def ragquery(query):   
    
    PROMPT = """
        Du bist ein zweites Gehirn für mich, ein Erinnerungsexperte, und deine Aufgabe ist es, basierend auf dem gegebenen Kontext den du aus meinen Erinnerungen in Form von Textausschnitten innerhalb der XML tags die dann folgende Frage so akkurat wie möglich beantwortest. Achte dabei darauf das deine Knowledge Base nur auf dem gegebenen Kontext basiert und du dich streng an das gegebene Format hälst:

        <Kontext> 
        {Kontext}
        </Kontext>
    
        <Format>
        Ein Satz mit maximal 50 Tokens. Deine Antwort ist klar und beantwortet die Frage indem es sich direkt auf den Kontext stützt. Gebe bei der Antwort KEINE XML tags oder sonstigen Werte an. Beantworte die Frage ausschließlich auf Deutsch.
        </Format>

        Du hast jetzt den Kontext in den <Kontext> XML Tags verstanden hast und das Format übernommen. Beantworte nun die nachfolgende Frage innerhalb der <Frage> XML Tags basierend auf dem gegebenen Kontext in den XML tags. Achte dabei darauf die streng an das Format aus den XML Tags zu halten.

        <Frage>
        {Frage}
        </Frage>
    """
    # use the query_database endpoint to retrieve 5 chunks
    chunks = query_database(query)  # Retrieve 5 chunks based on the query
    if not chunks:
        logger.error("No chunks found for the given query.")
        return

    # combine the 5 chunks with the question in the given prompt
    context = "------/n".join(str(chunk['document']) for chunk in chunks)
    prompt = PROMPT.format(Kontext=context, Frage=query)
    print(prompt)
    
    response = call_api(
    "https://ollama.mitra-labs.ai", "/api/generate", 
    method="POST", 
    data=json.dumps({
        "model": "llama3.2",
        "prompt": prompt,
        "stream": False
    }),
    headers={"Content-Type": "application/json"}
)

    if response and response.get("status") == "success":
        print(response.get("answer"))  # Print the answer from the LLM
    else:
        logger.error(f"LLM request failed. Response: {response}")


if __name__ == "__main__":
    ragquery("Was weißt du?")
    #main()
