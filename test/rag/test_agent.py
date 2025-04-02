import logging
import json

from coco.client import CocoClient
from coco.structs import ToolCall

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("absl").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    """
    Test script for the secret word tool.
    This script demonstrates how to use the agent functionality to call the secret word tool.
    """
    # Initialize the CocoClient directly with hardcoded values
    cc = CocoClient(
        chunking_base="http://127.0.0.1:8001",
        db_api_base="http://127.0.0.1:8003",
        transcription_base="http://127.0.0.1:8000",
        ollama_base="http://127.0.0.1:11434",
        openai_base="https://openai.inference.de-txl.ionos.com/v1",
        api_key="test",
        embedding_api="openai",
        llm_api="openai",
    )
    cc_oai = CocoClient(
        chunking_base="http://127.0.0.1:8001",
        db_api_base="http://127.0.0.1:8003",
        transcription_base="http://127.0.0.1:8000",
        ollama_base="http://127.0.0.1:11434",
        openai_base="https://api.openai.com/v1",
        api_key="test",
        embedding_api="openai",
        llm_api="openai",
        tools_coco_client=cc,
    )
    # model = "meta-llama/Llama-3.3-70B-Instruct"
    # model = "mistral-nemo"
    model = "gpt-4o-2024-11-20"

    # Perform a health check to ensure all services are running
    logger.info("Performing health check...")
    try:
        cc.health_check()
    except Exception as e:
        logger.warning(f"Health check encountered issues: {e}")
        logger.warning("Continuing with the test despite health check issues...")

    logger.info("Available tools:")
    tools = cc.agent.tools_client.get_tools()
    logger.info(f"{json.dumps(tools, indent=2)}")

    logger.info("Testing tool through agent...")
    messages = [
        {
            "role": "user",
            "content": "call the semantic_query tool with the query 'What is the capital of France?'",
        }
    ]

    agent_result = cc_oai.agent.chat(
        messages=messages,
        model=model,
        max_iterations=3,
    )
    logger.info(
        f"Messages History: {json.dumps(agent_result['conversation_history'], indent=2)}"
    )
    logger.info(f"Agent result: {agent_result['content']}")


if __name__ == "__main__":
    main()
