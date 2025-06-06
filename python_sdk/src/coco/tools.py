import inspect
from typing import (
    Dict,
    List,
    Any,
    Optional,
    get_type_hints,
    Literal,
    Union,
)
import logging
import functools
import datetime
import json

from .db_api import DbApiClient
from .lm import LanguageModelClient
from .structs import ToolCall, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


def tool(name: str = None, description: str = None):
    """
    Decorator to mark a method as a tool and provide metadata for tool description generation

    Args:
        name: Optional custom name for the tool (defaults to method name)
        description: Description of what the tool does
    """

    def decorator(func):
        sig = inspect.signature(func)
        func_name = name or func.__name__
        func_doc = description or inspect.getdoc(func) or ""

        # Extract parameter information
        parameters = []
        type_hints = get_type_hints(func)

        for param_name, param in sig.parameters.items():
            # Skip self parameter
            if param_name == "self":
                continue

            param_type = type_hints.get(param_name, Any)
            param_type_str = "string"  # Default

            # Convert Python types to JSON schema types
            if param_type in (str, Optional[str]):
                param_type_str = "string"
            elif param_type in (int, Optional[int]):
                param_type_str = "integer"
            elif param_type in (float, Optional[float]):
                param_type_str = "number"
            elif param_type in (bool, Optional[bool]):
                param_type_str = "boolean"
            elif param_type in (list, List, Optional[list], Optional[List]):
                param_type_str = "array"
            elif param_type in (dict, Dict, Optional[dict], Optional[Dict]):
                param_type_str = "object"

            # Check if it's an enum (Literal)
            enum_values = None
            origin = getattr(param_type, "__origin__", None)
            if origin is Literal:
                enum_values = list(param_type.__args__)
                param_type_str = "string"

            # Get parameter description from docstring if available
            param_desc = ""
            if func.__doc__:
                for line in func.__doc__.split("\n"):
                    if line.strip().startswith(f"{param_name}"):
                        param_desc = line.split(":", 1)[1].strip()
                        break

            # Determine if parameter is required
            required = param.default is inspect.Parameter.empty
            default = (
                None if param.default is inspect.Parameter.empty else param.default
            )

            parameters.append(
                ToolParameter(
                    name=param_name,
                    type=param_type_str,
                    description=param_desc,
                    required=required,
                    default=default,
                    enum=enum_values,
                )
            )

        # Create tool definition
        tool_def = ToolDefinition(
            name=func_name, description=func_doc, parameters=parameters, method=func
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Mark the function as a tool and attach the tool definition
        wrapper._is_tool = True
        wrapper._tool_definition = tool_def

        return wrapper

    return decorator


class ToolsClient:
    """
    Client for agentic workflows in coco.
    This client provides tools that can be used by language models to interact with coco.
    Methods of this client can be automatically converted to tool descriptions for Ollama and OpenAI.
    """

    def __init__(self, lm: LanguageModelClient, db_api: DbApiClient):
        """
        Initialize the ToolsClient.

        Args:
            lm: An initialized LanguageModelClient instance
            db_api: An initialized DbApiClient instance
        """
        self.lm = lm
        self.db_api = db_api
        self.tools: Dict[str, ToolDefinition] = {}

        # Automatically register methods marked with @tool decorator
        self._register_tools()

    def _register_tools(self):
        """Register all methods decorated with @tool as tools"""
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, "_is_tool") and method._is_tool:
                self.tools[name] = method._tool_definition
                # Update the method reference
                self.tools[name].method = method

    def get_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self.tools.values()]

    def execute_tool(self, tool_call: ToolCall) -> Any:
        """
        Execute a tool by name with provided arguments

        Args:
            tool_call: The tool call to execute

        Returns:
            The result of the tool execution
        """
        if tool_call.name not in self.tools:
            raise ValueError(f"Tool '{tool_call.name}' not found")

        logger.info(f"Executing tool: {tool_call}")

        tool = self.tools[tool_call.name]

        # Get type hints for the tool method
        type_hints = get_type_hints(tool.method)
        converted_kwargs = {}

        # Convert arguments to their expected types based on type annotations
        for param_name, param_value in tool_call.arguments.items():
            # Skip 'self' parameter
            if param_name == "self":
                continue

            # Get the expected type for this parameter
            expected_type = type_hints.get(param_name, Any)

            # Skip conversion for Any type
            if expected_type is Any:
                converted_kwargs[param_name] = param_value
                continue

            # Handle Optional types
            origin = getattr(expected_type, "__origin__", None)
            args = getattr(expected_type, "__args__", [])
            if origin is Union and type(None) in args:
                # It's an Optional type, get the actual type
                for arg in args:
                    if arg is not type(None):
                        expected_type = arg
                        break

            # Convert value to expected type
            try:
                # Handle basic types
                if expected_type is int:
                    converted_kwargs[param_name] = int(param_value)
                elif expected_type is float:
                    converted_kwargs[param_name] = float(param_value)
                elif expected_type is bool and isinstance(param_value, str):
                    # Convert string representations of booleans
                    if param_value.lower() in ("true", "yes", "1", "y"):
                        converted_kwargs[param_name] = True
                    elif param_value.lower() in ("false", "no", "0", "n"):
                        converted_kwargs[param_name] = False
                    else:
                        converted_kwargs[param_name] = bool(param_value)
                elif expected_type is str:
                    converted_kwargs[param_name] = str(param_value)
                elif expected_type in (list, List) and isinstance(param_value, str):
                    # Try to parse string as JSON list
                    try:
                        converted_kwargs[param_name] = json.loads(param_value)
                    except json.JSONDecodeError:
                        # Fall back to treating it as a comma-separated list
                        converted_kwargs[param_name] = [
                            item.strip() for item in param_value.split(",")
                        ]
                elif expected_type in (dict, Dict) and isinstance(param_value, str):
                    # Try to parse string as JSON dict
                    try:
                        converted_kwargs[param_name] = json.loads(param_value)
                    except json.JSONDecodeError:
                        # Keep original if not valid JSON
                        converted_kwargs[param_name] = param_value
                else:
                    # For other types, just pass the original value
                    converted_kwargs[param_name] = param_value
            except (ValueError, TypeError):
                # If conversion fails, use the original value
                logger.warning(
                    f"Failed to convert parameter '{param_name}' to {expected_type.__name__}, using original value"
                )
                converted_kwargs[param_name] = param_value

        # Execute the tool with converted arguments
        return tool.method(**converted_kwargs)

    @tool(
        description="Search for relevant information in the knowledge database by embedding similarity to the query_text. Searched chunks can be filtered by a start and end date before the search."
    )
    def semantic_query(
        self,
        query_text: str,
        num_results: int = 25,
        start_date_time_iso: Optional[str] = None,
        end_date_time_iso: Optional[str] = None,
        contains_substring: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant information in the database based on a query.

        Args:
            query_text (str): The query text to search for. This will be compared to the database chunks by embedding similarity.
            num_results (int, optional): The number of chunks to return for the query. If not set, defaults to 25.
            start_date_time_iso (Optional[str], optional): The start date in ISO format. If provided, only chunks dated after this date will be considered. If not set, all knowledge chunks will be considered.
            end_date_time_iso (Optional[str], optional): The end date in ISO format. If provided, only chunks dated before this date will be considered. If not set, all knowledge chunks will be considered.
            contains_substring (Optional[str], optional): Only consider chunks that contain this substring (case insensitive). If not set, all knowledge chunks will be considered.
        Returns:
            List[Dict[str, Any]]: The search results.
        """
        start, end = None, None
        if start_date_time_iso is not None:
            try:
                start = datetime.datetime.fromisoformat(start_date_time_iso)
            except ValueError:
                return {
                    "message": f"Invalid start date time: {start_date_time_iso}. Please provide a valid ISO 8601 formatted date time or don't set the parameter. Call the tool again without asking the user for confirmation.",
                }
        if end_date_time_iso is not None:
            try:
                end = datetime.datetime.fromisoformat(end_date_time_iso)
            except ValueError:
                return {
                    "message": f"Invalid end date time: {end_date_time_iso}. Please provide a valid ISO 8601 formatted date time or don't set the parameter. Call the tool again without asking the user for confirmation.",
                }
        embedding = self.lm.embed(query_text)
        ids, documents, metadatas, distances = self.db_api.get_closest(
            embedding=embedding,
            n_results=num_results,
            start_date_time=start,
            end_date_time=end,
            contains_substring=contains_substring,
        )
        knowledge = [
            {
                "content": document,
                "metadata": metadata,
            }
            for document, metadata in zip(documents, metadatas)
        ]
        return {
            "message": f"Here are your knowledge chunks and their metadata for the query '{query_text}'.",
            "knowledge": knowledge,
            "tool_timestamp": datetime.datetime.now().isoformat(),
        }

    @tool(description="Get the current date and time")
    def get_current_date_time(self) -> str:
        """Get the current date and time"""
        return {
            "date_time": datetime.datetime.now().isoformat(),
            "message": f"Das ist die aktuelle Uhrzeit und der aktuelle Tag.",
        }

    # @tool(
    #     description="Retrieve all chunks that belong to the same session as the first result from a semantic search."
    # )
    # def get_session_chunks(
    #     self,
    #     query_text: str,
    #     sort_by_date: bool = True,
    # ) -> Dict[str, Any]:
    #     """
    #     Find the first relevant chunk using semantic search and then retrieve all chunks
    #     that share the same session_id.

    #     Args:
    #         query_text: The natural language query to find the initial chunk
    #         sort_by_date: Whether to sort the results by date (default: True)

    #     Returns:
    #         A dictionary containing the session chunks and metadata
    #     """
    #     # First get the most relevant chunk to find the session_id
    #     embedding = self.lm.embed(query_text)
    #     ids, documents, metadatas, distances = self.db_api.get_closest(
    #         embedding=embedding,
    #         n_results=1,
    #     )

    #     if not metadatas or "session_id" not in metadatas[0]:
    #         return {
    #             "knowledge": [],
    #             "tool_timestamp": datetime.datetime.now().isoformat(),
    #             "message": "No matching session found.",
    #         }

    #     # Get all chunks with the same session_id
    #     session_id = str(metadatas[0]["session_id"])  # Convert to string for API call
    #     response = self.db_api.get_by_session_id(session_id)

    #     if not response or not response.get("results"):
    #         return {
    #             "knowledge": [],
    #             "tool_timestamp": datetime.datetime.now().isoformat(),
    #             "message": "No chunks found for the session.",
    #         }

    #     results = response["results"]
    #     if sort_by_date:
    #         results.sort(key=lambda x: x["metadata"]["date"] if x["metadata"]["date"] else "")

    #     knowledge = [
    #         {
    #             "content": result["document"],
    #             "metadata": result["metadata"],
    #         }
    #         for result in results
    #     ]

    #     return {
    #         "knowledge": knowledge,
    #         "tool_timestamp": datetime.datetime.now().isoformat(),
    #         "message": f"Found {len(knowledge)} chunks from the requested session.",
    #     }
