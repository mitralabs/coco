from dataclasses import dataclass, field
import json
from typing import Any, Callable, Dict, List, Optional, Union

import ollama
import openai


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

    @staticmethod
    def from_chat_response(
        tool_call_property: Union[
            ollama._types.Message.ToolCall,
            openai.types.chat.chat_completion_message_tool_call.ChatCompletionMessageToolCall,
        ],
        id: str = None,
    ):
        """Convert a tool call from a chat response to a ToolCall object

        Args:
            tool_call_property (Union[ ollama._types.Message.ToolCall, openai.types.chat.chat_completion_message_tool_call.ChatCompletionMessageToolCall, ]): The tool call property from the chat response
            id (str, optional): The id of the tool call. Defaults to None.

        Returns:
            ToolCall: The ToolCall object
        """
        if isinstance(tool_call_property, ollama._types.Message.ToolCall):
            assert (
                id is not None
            ), "id is required since ollama does not set one automatically"
            return ToolCall(
                id=id,
                name=tool_call_property.function.name,
                arguments=tool_call_property.function.arguments,
            )
        elif isinstance(
            tool_call_property,
            openai.types.chat.chat_completion_message_tool_call.ChatCompletionMessageToolCall,
        ):
            return ToolCall(
                id=tool_call_property.id,
                name=tool_call_property.function.name,
                arguments=json.loads(tool_call_property.function.arguments),
            )
        else:
            raise ValueError(
                f"Unsupported tool call property type: {type(tool_call_property)}"
            )

    def __str__(self):
        return f"""ToolCall(
            id={self.id},
            name={self.name},
            arguments={json.dumps(self.arguments, indent=2)}
        )"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for JSON serialization"""
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments},
        }


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: List[str] = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    method: Optional[Callable] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to OpenAI and Ollama function calling format"""
        properties = {}
        required = []

        for param in self.parameters:
            param_spec = {"type": param.type, "description": param.description}

            if param.enum:
                param_spec["enum"] = param.enum

            properties[param.name] = param_spec

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
