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
        llm_api="ollama",
    )
    # model = "meta-llama/Llama-3.3-70B-Instruct"
    model = "mistral-nemo"

    # Perform a health check to ensure all services are running
    logger.info("Performing health check...")
    try:
        cc.health_check()
    except Exception as e:
        logger.warning(f"Health check encountered issues: {e}")
        logger.warning("Continuing with the test despite health check issues...")

    logger.info("Testing direct tool execution...")
    result = cc._tools_client.execute_tool(
        ToolCall(
            id="tool_call_1",
            name="get_secret_word",
            arguments={},
        )
    )
    logger.info(f"Secret word result (direct):\n{json.dumps(result, indent=2)}")

    # Print available tools for debugging
    logger.info("Available tools:")
    tools = cc.agent.tools_client.get_tools()
    logger.info(f"{json.dumps(tools, indent=2)}")

    logger.info("Testing tool through agent...")
    messages = [
        {
            "role": "user",
            "content": "Finde das geheime Wort.",
        }
    ]

    agent_result = cc.agent.chat(
        messages=messages,
        model=model,
        max_iterations=3,
    )
    messages = agent_result["conversation_history"] + [
        {
            "role": "user",
            "content": "Kannst du es in den geheimen Satz einsetzen?",
        }
    ]
    agent_result = cc.agent.chat(
        messages=messages,
        model=model,
        max_iterations=3,
    )
    messages = agent_result["conversation_history"] + [
        {
            "role": "user",
            "content": "Ich weiß nicht, ob sich die Geheimnisse nicht ändern. Kannst du bitte nochmal nachschauen?",
        }
    ]
    agent_result = cc.agent.chat(
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
