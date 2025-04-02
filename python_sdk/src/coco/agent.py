import json
import logging
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from .tools import ToolsClient
from .lm import LanguageModelClient
from .async_utils import batched_parallel

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

    async def async_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama3.2:1b",
        max_tool_calls: int = 10,
        max_iterations: int = 5,
        temperature: float = 0.0,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Handle a chat session asynchronously with tool calling support.

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
            result = await self.lm.async_tool_chat(
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

    async def _chat_multiple(
        self,
        queries: List[str],
        system_prompt: str = None,
        model: str = "llama3.2:1b",
        max_tool_calls: int = 10,
        max_iterations: int = 5,
        temperature: float = 0.0,
        return_just_answers: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Internal async method to handle multiple chat sessions in parallel.

        Args:
            queries (List[str]): List of user queries
            system_prompt (str, optional): System prompt for the agent. Defaults to None.
            model (str, optional): Model to use for chat completion. Defaults to "llama3.2:1b".
            max_tool_calls (int, optional): Maximum number of tool calls. Defaults to 10.
            max_iterations (int, optional): Maximum number of iterations for tool calling. Defaults to 5.
            temperature (float, optional): Temperature for chat completion. Defaults to 0.0.

        Returns:
            (answers, n_toolcalls): Tuple[List[str], List[int]]: List of answers and list of number of tool calls
        """
        results = []
        for query in queries:
            messages = [
                {"role": "system", "content": system_prompt or self.system_prompt},
                {"role": "user", "content": query},
            ]

            result = await self.async_chat(
                messages=messages,
                model=model,
                max_tool_calls=max_tool_calls,
                max_iterations=max_iterations,
                temperature=temperature,
                stream=False,
            )
            results.append(result)

        if return_just_answers:
            results = [r["content"] for r in results]
        return results

    def chat_multiple(
        self,
        queries: List[str],
        system_prompt: str = None,
        model: str = "llama3.2:1b",
        max_tool_calls: int = 10,
        max_iterations: int = 5,
        temperature: float = 0.0,
        pull_model: bool = False,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
        return_just_answers: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Handle multiple chat sessions with tool calling support.

        Args:
            queries (List[str]): List of user queries
            model (str, optional): Model to use for chat completion. Defaults to "llama3.2:1b".
            max_tool_calls (int, optional): Maximum number of tool calls. Defaults to 10.
            max_iterations (int, optional): Maximum number of iterations for tool calling. Defaults to 5.
            temperature (float, optional): Temperature for chat completion. Defaults to 0.0.
            pull_model (bool, optional): Whether to pull the ollama model. Defaults to False.
            batch_size (int, optional): The batch size to use. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.

        Returns:
            if return_just_answers is True:
                List[str]: List of answers
            else:
                List[Dict[str, Any]]: List of chat results
                {
                    "content": str,
                    "tool_calls": List[coco.structs.ToolCall],
                    "tool_results": List[Any],
                    "conversation_history": List[Dict[str, Any]],
                }
        """
        if pull_model and self.llm_api == "ollama":
            models = self.lm.list_ollama_models()
            if model not in models:
                logger.info(f"Pulling model {model} because it is not available")
                self.lm.pull_ollama_model(model)
                logger.info(f"Pulled model {model}")

        batched_chat = batched_parallel(
            function=self._chat_multiple,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Generating answers with agent",
        )

        return batched_chat(
            queries=queries,
            system_prompt=system_prompt,
            model=model,
            max_tool_calls=max_tool_calls,
            max_iterations=max_iterations,
            temperature=temperature,
            return_just_answers=return_just_answers,
        )

    def chat_multiple_sequential(
        self,
        queries: List[str],
        system_prompt: str = None,
        model: str = "llama3.2:1b",
        max_tool_calls: int = 10,
        max_iterations: int = 5,
        temperature: float = 0.0,
        pull_model: bool = False,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
        return_just_answers: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Sequentially handle multiple chat sessions with tool calling support.

        Args:
            queries (List[str]): List of user queries
            model (str, optional): Model to use for chat completion. Defaults to "llama3.2:1b".
            max_tool_calls (int, optional): Maximum number of tool calls. Defaults to 10.
            max_iterations (int, optional): Maximum number of iterations for tool calling. Defaults to 5.
            temperature (float, optional): Temperature for chat completion. Defaults to 0.0.
            pull_model (bool, optional): Whether to pull the ollama model. Defaults to False.
            batch_size (int, optional): The batch size to use. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.

        Returns:
            if return_just_answers is True:
                List[str]: List of answers
            else:
                List[Dict[str, Any]]: List of chat results
                {
                    "content": str,
                    "tool_calls": List[coco.structs.ToolCall],
                    "tool_results": List[Any],
                    "conversation_history": List[Dict[str, Any]],
                }
        """
        if pull_model and self.llm_api == "ollama":
            models = self.lm.list_ollama_models()
            if model not in models:
                logger.info(f"Pulling model {model} because it is not available")
                self.lm.pull_ollama_model(model)
                logger.info(f"Pulled model {model}")

        results = []
        for query in tqdm(queries, desc="Generating answers with agent"):
            messages = [
                {"role": "system", "content": system_prompt or self.system_prompt},
                {"role": "user", "content": query},
            ]

            result = self.chat(
                messages=messages,
                model=model,
                max_tool_calls=max_tool_calls,
                max_iterations=max_iterations,
                temperature=temperature,
                stream=False,
            )
            results.append(result)

        if return_just_answers:
            results = [r["content"] for r in results]
        return results
