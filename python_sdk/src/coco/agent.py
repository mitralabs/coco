import json
import logging
from typing import List, Dict, Any, Optional

from .tools import ToolsClient
from .lm import LanguageModelClient

logger = logging.getLogger(__name__)

# Default system prompt for the agent
DEFAULT_SYSTEM_PROMPT = """
Du bist Coco, ein hilfreicher Assistent mit Zugriff auf verschiedene Tools. 
Nutze diese Tools, um die Anfrage des Benutzers zu erfüllen. Antworte immer
präzise und nützlich. Wenn du mehr Informationen benötigst, verwende die
entsprechenden Tools, um sie zu erhalten. Wenn du mehrere Tools ausführen musst,
tue dies ohne nachfrage nacheinander und beziehe die Ergebnisse in deine
Überlegungen ein.
"""


class AgentClient:
    def __init__(
        self,
        lm: LanguageModelClient,
        tools_client: ToolsClient,
        llm_api: str,
        system_prompt: Optional[str] = None,
    ):
        """Initialize the AgentClient.

        Args:
            lm (LanguageModelClient): Language model client for chat completion
            tools_client (ToolsClient): Tools client for executing tools
            llm_api (str): Language model API to use ('ollama' or 'openai')
            system_prompt (Optional[str], optional): System prompt for the agent. Defaults to None.
        """
        self.lm = lm
        self.tools_client = tools_client
        self.llm_api = llm_api
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama3.2:1b",
        max_tool_calls: int = 10,
        max_iterations: int = 5,
        temperature: float = 0.0,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Handle a chat session with tool calling support.

        Args:
            messages (List[Dict[str, str]]): List of messages in the conversation
            model (str, optional): Model to use for chat completion. Defaults to "llama3.2:1b".
            max_tool_calls (int, optional): Maximum number of tool calls. Defaults to 10.
            max_iterations (int, optional): Maximum number of iterations for tool calling. Defaults to 5.
            temperature (float, optional): Temperature for chat completion. Defaults to 0.7.
            stream (bool, optional): Whether to stream the response. Defaults to False.

        Returns:
            {
                "content": str,
                "tool_calls": List[ToolCall],
                "tool_results": List[Any],
                "conversation_history": List[Dict[str, Any]],
            }
        """
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        tools = self.tools_client.get_tools()

        conversation_history = messages.copy()

        ans = {
            "content": "",
            "tool_calls": [],
            "tool_results": [],
            "conversation_history": conversation_history,
        }

        for iteration in range(max_iterations):
            result = self.lm.tool_chat(
                conversation_history, model, tools, temperature, stream
            )

            tool_calls = result.get("tool_calls", [])

            if not tool_calls or len(ans["tool_calls"]) >= max_tool_calls:
                ans["content"] = result.get("content", "")
                conversation_history.append(
                    {"role": "assistant", "content": result.get("content", "")}
                )
                ans["conversation_history"] = conversation_history
                return ans

            for tool_call in tool_calls:
                ans["tool_calls"].append(tool_call)
                tool_result = self.tools_client.execute_tool(tool_call)
                ans["tool_results"].append(tool_result)
                tool_call_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call.to_dict()],
                }
                conversation_history.append(tool_call_msg)
                tool_result_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": json.dumps(tool_result),
                }
                conversation_history.append(tool_result_msg)

        ans["content"] = result.get("content", "")
        conversation_history.append(
            {"role": "assistant", "content": result.get("content", "")}
        )
        ans["conversation_history"] = conversation_history

        return ans
