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
        temperature: float = 0.7,
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
            Dict[str, Any]: Final assistant response with tool calls, results, and conversation history
        """
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        tools = self.tools_client.get_tools(self.llm_api)

        conversation_history = messages.copy()

        response = {
            "content": "",
            "tool_calls": [],
            "tool_results": [],
            "conversation_history": conversation_history,
        }

        for iteration in range(max_iterations):
            logger.info(f"Agent iteration {iteration + 1}/{max_iterations}")

            if self.llm_api == "openai":
                result = self._handle_openai_chat(
                    conversation_history, model, tools, temperature, stream
                )
            else:
                result = self._handle_ollama_chat(
                    conversation_history, model, tools, temperature, stream
                )

            tool_calls = result.get("tool_calls", [])

            if not tool_calls or len(response["tool_calls"]) >= max_tool_calls:
                response["content"] = result.get("content", "")
                conversation_history.append(
                    {"role": "assistant", "content": result.get("content", "")}
                )
                response["conversation_history"] = conversation_history
                return response

            for tool_call in tool_calls:
                response["tool_calls"].append(tool_call)

                tool_result = self._execute_tool(tool_call)

                response["tool_results"].append(tool_result)

                tool_call_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call],
                }
                conversation_history.append(tool_call_msg)

                tool_result_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "name": tool_call.get("function", {}).get("name"),
                    "content": json.dumps(tool_result),
                }
                conversation_history.append(tool_result_msg)

        response["content"] = result.get("content", "")
        conversation_history.append(
            {"role": "assistant", "content": result.get("content", "")}
        )
        response["conversation_history"] = conversation_history

        return response

    def _execute_tool(self, tool_call: Dict[str, Any]) -> Any:
        """Execute a tool call and return the result.

        Args:
            tool_call (Dict[str, Any]): Tool call information

        Returns:
            Any: Result of the tool execution
        """
        try:
            function_name = tool_call.get("function", {}).get("name")
            function_args = tool_call.get("function", {}).get("arguments", "{}")

            if isinstance(function_args, str):
                try:
                    args_dict = json.loads(function_args)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse tool arguments: {function_args}")
                    return {"error": "Failed to parse tool arguments"}
            else:
                args_dict = function_args

            logger.info(f"Executing tool: {function_name} with args: {args_dict}")
            result = self.tools_client.execute_tool(function_name, **args_dict)
            return result
        except Exception as e:
            logger.error(f"Error executing tool: {str(e)}")
            return {"error": str(e)}

    def _handle_openai_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Handle OpenAI chat completion with tool calling.

        Args:
            messages (List[Dict[str, str]]): List of messages in the conversation
            model (str): Model to use for chat completion
            tools (List[Dict[str, Any]]): List of available tools
            temperature (float, optional): Temperature for chat completion. Defaults to 0.7.
            stream (bool, optional): Whether to stream the response. Defaults to False.

        Returns:
            Dict[str, Any]: Chat completion result
        """
        try:
            if not hasattr(self.lm, "openai"):
                raise ValueError("OpenAI client not initialized")

            response = self.lm.openai.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                stream=stream,
            )

            if stream:
                raise NotImplementedError("Streaming not yet implemented for OpenAI")
            else:
                result = response.choices[0].message
                content = result.content or ""

                tool_calls = []
                if hasattr(result, "tool_calls") and result.tool_calls:
                    for tool_call in result.tool_calls:
                        tool_calls.append(
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                        )

                return {"content": content, "tool_calls": tool_calls}

        except Exception as e:
            logger.error(f"Error in OpenAI chat completion: {str(e)}")
            return {"content": f"Error: {str(e)}", "tool_calls": []}

    def _handle_ollama_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Handle Ollama chat completion with tool calling.

        Args:
            messages (List[Dict[str, str]]): List of messages in the conversation
            model (str): Model to use for chat completion
            tools (List[Dict[str, Any]]): List of available tools
            temperature (float, optional): Temperature for chat completion. Defaults to 0.7.
            stream (bool, optional): Whether to stream the response. Defaults to False.

        Returns:
            Dict[str, Any]: Chat completion result
        """
        try:
            if not hasattr(self.lm, "ollama"):
                raise ValueError("Ollama client not initialized")

            options = {"temperature": temperature}

            if stream:
                raise NotImplementedError("Streaming not yet implemented for Ollama")
            else:
                response = self.lm.ollama.chat(
                    model=model, messages=messages, options=options, tools=tools
                )

                content = response["message"]["content"] or ""

                tool_calls = []
                if "tool_calls" in response["message"]:
                    logger.info(response["message"]["tool_calls"])
                    for idx, tool_call in enumerate(response["message"]["tool_calls"]):
                        tool_calls.append(
                            {
                                "id": f"call_{idx}",
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                        )

                return {"content": content, "tool_calls": tool_calls}

        except Exception as e:
            logger.error(f"Error in Ollama chat completion: {str(e)}")
            return {"content": f"Error: {str(e)}", "tool_calls": []}
