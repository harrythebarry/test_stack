from abc import ABC, abstractmethod
from typing import Dict, Any, List, AsyncGenerator, Callable, Type
from pydantic import BaseModel
import json
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY
import base64
import httpx


class AgentTool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable

    def to_oai_tool(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_tool(self):
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters["properties"],
                "required": self.parameters.get("required", []),
            },
        }


class LLMProvider(ABC):
    @abstractmethod
    async def chat_complete(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float = 0.0
    ) -> str:
        pass

    @abstractmethod
    async def chat_complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[AgentTool],
        model: str,
        temperature: float = 0.0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        pass


class OpenAILLMProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    async def chat_complete(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float = 0.0
    ) -> str:
        resp = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content

    async def _handle_tool_call(self, tools: List[AgentTool], tool_call) -> str:
        # Default implementation for OpenAI format
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        tool = next((tool for tool in tools if tool.name == tool_name), None)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        return await tool.func(**arguments)

    async def chat_complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[AgentTool],
        model: str,
        temperature: float = 0.0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        running = True
        oai_messages = messages.copy()

        while running:
            # Only include tools parameter if tools are provided
            create_params = {
                "model": model,
                "messages": oai_messages,
                "temperature": temperature,
                "stream": True,
            }

            if tools:
                create_params["tools"] = [tool.to_oai_tool() for tool in tools]

            stream = await self.client.chat.completions.create(**create_params)

            tool_calls_buffer = []
            current_tool_call = None

            async for chunk in stream:
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        if tool_call_delta.index is not None:
                            if len(tool_calls_buffer) <= tool_call_delta.index:
                                tool_calls_buffer.append(tool_call_delta)
                                current_tool_call = tool_calls_buffer[
                                    tool_call_delta.index
                                ]
                            else:
                                current_tool_call = tool_calls_buffer[
                                    tool_call_delta.index
                                ]
                                if tool_call_delta.function.name:
                                    current_tool_call.function.name = (
                                        tool_call_delta.function.name
                                    )
                                if tool_call_delta.function.arguments:
                                    if not hasattr(
                                        current_tool_call.function, "arguments"
                                    ):
                                        current_tool_call.function.arguments = ""
                                    current_tool_call.function.arguments += (
                                        tool_call_delta.function.arguments
                                    )

                if finish_reason == "tool_calls":
                    oai_messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": tool_calls_buffer,
                        }
                    )
                    for tool_call in tool_calls_buffer:
                        tool_result = await self._handle_tool_call(tools, tool_call)
                        oai_messages.append(
                            {
                                "role": "tool",
                                "content": tool_result,
                                "name": tool_call.function.name,
                                "tool_call_id": tool_call.id,
                            }
                        )
                    yield {"type": "tool_calls", "tool_calls": tool_calls_buffer}
                elif finish_reason == "stop":
                    running = False
                    break

                if delta.content is not None:
                    yield {"type": "content", "content": delta.content}


class AnthropicLLMProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        # Create a shared httpx client for image fetching
        self.http_client = httpx.AsyncClient()

    async def _fetch_and_encode_image(self, url: str) -> tuple[str, str]:
        """Fetch image from URL and return (media_type, base64_data)"""
        resp = await self.http_client.get(url)
        resp.raise_for_status()
        media_type = resp.headers.get("content-type", "image/jpeg")
        b64_data = base64.b64encode(resp.content).decode("utf-8")
        return media_type, b64_data

    async def chat_complete(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float = 0.0
    ) -> str:
        response = await self.client.messages.create(
            model=model,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
            temperature=temperature,
            max_tokens=8192,
        )
        return response.content[0].text

    async def chat_complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[AgentTool],
        model: str,
        temperature: float = 0.0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # Convert tools to Anthropic format
        anthropic_tools = [tool.to_anthropic_tool() for tool in tools]

        # Extract system message and prepare current messages
        system_message = next(
            (msg["content"] for msg in messages if msg["role"] == "system"), None
        )

        # Convert messages to Anthropic format with image support
        current_messages = []
        for msg in messages:
            if msg["role"] == "system":
                continue

            content = []
            if isinstance(msg["content"], list):
                for content_block in msg["content"]:
                    if content_block["type"] == "text":
                        # Only add text block if it's not empty
                        if content_block["text"].strip():
                            content.append(
                                {"type": "text", "text": content_block["text"]}
                            )
                    elif content_block["type"] == "image_url":
                        # Fetch and encode the image
                        media_type, b64_data = await self._fetch_and_encode_image(
                            content_block["image_url"]["url"]
                        )
                        content.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64_data,
                                },
                            }
                        )
            else:
                # Only add text content if it's not empty
                if msg["content"] and msg["content"].strip():
                    content.append({"type": "text", "text": msg["content"]})

            # Only add message if it has content
            if content:
                current_messages.append({"role": msg["role"], "content": content})

        running = True
        while running:
            create_params = {
                "model": model,
                "messages": current_messages,
                "system": system_message,
                "temperature": temperature,
                "stream": True,
                "max_tokens": 8192,
            }

            if tools:
                create_params.update(
                    {"tools": anthropic_tools, "tool_choice": {"type": "auto"}}
                )

            stream = await self.client.messages.create(**create_params)

            tool_calls_buffer = []
            content_buffer = ""

            async for chunk in stream:
                if chunk.type == "message_start":
                    continue

                if chunk.type == "content_block_start":
                    if (
                        hasattr(chunk.content_block, "type")
                        and chunk.content_block.type == "tool_use"
                    ):
                        # Add new tool call to buffer
                        tool_calls_buffer.append(
                            {
                                "id": chunk.content_block.id,
                                "function": {
                                    "name": chunk.content_block.name,
                                    "arguments": "",
                                },
                            }
                        )

                elif chunk.type == "content_block_delta":
                    if hasattr(chunk.delta, "type"):
                        if chunk.delta.type == "text_delta":
                            content_buffer += chunk.delta.text
                            yield {"type": "content", "content": chunk.delta.text}
                        elif chunk.delta.type == "input_json_delta":
                            # Update arguments for the last tool call in buffer
                            if tool_calls_buffer:
                                tool_calls_buffer[-1]["function"][
                                    "arguments"
                                ] += chunk.delta.partial_json

                elif chunk.type == "content_block_stop":
                    if tool_calls_buffer:
                        # Process all tool calls in buffer
                        for tool_call in tool_calls_buffer:

                            arguments_dict = json.loads(
                                tool_call["function"]["arguments"]
                            )
                            tool_result = await self._handle_tool_call(tools, tool_call)

                            # Add tool use message
                            current_messages.append(
                                {
                                    "role": "assistant",
                                    "content": [
                                        {
                                            "type": "tool_use",
                                            "id": tool_call["id"],
                                            "name": tool_call["function"]["name"],
                                            "input": arguments_dict,
                                        }
                                    ],
                                }
                            )

                            # Add tool result message
                            current_messages.append(
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "tool_result",
                                            "tool_use_id": tool_call["id"],
                                            "content": tool_result,
                                        }
                                    ],
                                }
                            )

                        # Yield all tool calls at once
                        yield {
                            "type": "tool_calls",
                            "tool_calls": tool_calls_buffer,
                        }
                        tool_calls_buffer = []
                        content_buffer = ""
                elif (
                    chunk.type == "message_delta"
                    and chunk.delta.stop_reason == "end_turn"
                ):
                    running = False
                    break
                elif (
                    chunk.type == "message_delta"
                    and chunk.delta.stop_reason == "tool_use"
                ):
                    pass
                elif chunk.type == "message_stop":
                    pass
                else:
                    print(f"Unhandled anthropic chunk: {chunk}")

    async def _handle_tool_call(self, tools: List[AgentTool], tool_call) -> str:
        # Anthropic specific implementation
        tool_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])

        tool = next((tool for tool in tools if tool.name == tool_name), None)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        return await tool.func(**arguments)


LLM_PROVIDERS: Dict[str, Type[LLMProvider]] = {
    "openai": OpenAILLMProvider,
    "anthropic": AnthropicLLMProvider,
}
