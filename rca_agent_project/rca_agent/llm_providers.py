"""
LLM Providers — Swappable Backends
====================================
Switch between Anthropic (Claude), OpenAI (GPT-4), or Google (Gemini)
by changing LLM_PROVIDER in config. All providers implement the same
interface: send messages + tool schemas, get back response + tool calls.

This is the key benefit of MCP architecture: tools are in the MCP server,
LLM reasoning is here, and they're completely decoupled.
"""

from __future__ import annotations
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Unified response format ──────────────────────────────────────────────────

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass 
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = None
    stop_reason: str = ""
    raw: Any = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


# ── Base class ───────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        """Format a tool result message for the provider's API format."""
        ...

    @abstractmethod
    def format_assistant_message(self, response: LLMResponse) -> dict:
        """Convert LLMResponse back into a message for conversation history."""
        ...


# ── Anthropic (Claude) ──────────────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    """Claude API via anthropic SDK."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = ""):
        self.model = model
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key or None)

    def chat(self, messages: list[dict], tools: list[dict] = None,
             temperature: float = 0.2, max_tokens: int = 4096) -> LLMResponse:
        # Separate system message from conversation
        system_msg = ""
        conv_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                conv_messages.append(m)

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": conv_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        response = self.client.messages.create(**kwargs)

        # Parse response
        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            raw=response,
        )

    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": result,
            }],
        }

    def format_assistant_message(self, response: LLMResponse) -> dict:
        content = []
        if response.content:
            content.append({"type": "text", "text": response.content})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": content}

    @staticmethod
    def _convert_tools(tools: list[dict]) -> list[dict]:
        """Convert unified tool schema to Anthropic format."""
        converted = []
        for t in tools:
            fn = t.get("function", t)
            converted.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {}),
            })
        return converted


# ── OpenAI (GPT-4) ──────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    """OpenAI API via openai SDK."""

    def __init__(self, model: str = "gpt-4o", api_key: str = ""):
        self.model = model
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key or None)

    def chat(self, messages: list[dict], tools: list[dict] = None,
             temperature: float = 0.2, max_tokens: int = 4096) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t.get("function", t)}
                               for t in tools]
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            stop_reason=response.choices[0].finish_reason,
            raw=response,
        )

    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        }

    def format_assistant_message(self, response: LLMResponse) -> dict:
        msg = {"role": "assistant", "content": response.content}
        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ]
        return msg

# ── Google (Gemini) ──────────────────────────────────────────────────────────

class GoogleProvider(LLMProvider):
    """
    Google Gemini API via google-generativeai SDK with full function calling.

    Handles Gemini's strict alternating-turn requirement by batching all
    FunctionResponse parts from one agent step into a single user turn.
    """

    def __init__(self, model: str = "gemini-2.0-flash", api_key: str = ""):
        self.model_name = model
        import google.generativeai as genai
        if api_key:
            genai.configure(api_key=api_key)
        self.genai = genai

    # ── Schema conversion ────────────────────────────────────────────────────

    def _convert_tools(self, tools: list[dict]):
        """Convert unified tool schemas to Gemini FunctionDeclaration protos."""
        from google.generativeai import protos
        declarations = []
        for t in tools:
            fn = t.get("function", t)
            declarations.append(protos.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=self._json_schema_to_gemini(fn.get("parameters", {})),
            ))
        return [protos.Tool(function_declarations=declarations)]

    def _json_schema_to_gemini(self, schema: dict):
        """Recursively convert a JSON Schema dict to a Gemini Schema proto."""
        from google.generativeai import protos
        type_map = {
            "string": protos.Type.STRING,
            "number": protos.Type.NUMBER,
            "integer": protos.Type.INTEGER,
            "boolean": protos.Type.BOOLEAN,
            "array": protos.Type.ARRAY,
            "object": protos.Type.OBJECT,
        }
        schema_type = type_map.get((schema.get("type") or "string").lower(),
                                   protos.Type.STRING)
        properties = {
            name: self._json_schema_to_gemini(prop)
            for name, prop in schema.get("properties", {}).items()
        }
        return protos.Schema(
            type_=schema_type,
            description=schema.get("description", ""),
            properties=properties or None,
            required=schema.get("required", []),
            enum=schema.get("enum", []),
        )

    # ── Message format helpers ───────────────────────────────────────────────

    def _build_contents(self, messages: list[dict]) -> tuple[str, list]:
        """
        Convert unified messages to Gemini contents list.

        Gemini requires strict user/model alternation, so consecutive
        FunctionResponse parts (tool results) are merged into one user turn.
        """
        from google.generativeai import protos

        system_instruction = ""
        contents = []
        pending_fn_responses: list = []  # batch tool results into one user turn

        def flush_fn_responses():
            if pending_fn_responses:
                contents.append({"role": "user", "parts": list(pending_fn_responses)})
                pending_fn_responses.clear()

        for m in messages:
            role = m["role"]
            content = m.get("content", "")

            if role == "system":
                system_instruction = content

            elif role == "user":
                if isinstance(content, list):
                    # Tool results injected by format_tool_result
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "function_response":
                            pending_fn_responses.append(
                                protos.Part(function_response=protos.FunctionResponse(
                                    name=item["name"],
                                    response={"result": item["content"]},
                                ))
                            )
                else:
                    # Regular user text — flush any pending tool results first
                    flush_fn_responses()
                    if content:
                        contents.append({"role": "user", "parts": [content]})

            elif role in ("assistant", "model"):
                flush_fn_responses()
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") == "text" and item.get("text"):
                            parts.append(item["text"])
                        elif item.get("type") == "function_call":
                            parts.append(protos.Part(
                                function_call=protos.FunctionCall(
                                    name=item["name"],
                                    args=item.get("args", {}),
                                )
                            ))
                    if parts:
                        contents.append({"role": "model", "parts": parts})
                elif content:
                    contents.append({"role": "model", "parts": [content]})

        flush_fn_responses()
        return system_instruction, contents

    # ── Main chat method ─────────────────────────────────────────────────────

    def chat(self, messages: list[dict], tools: list[dict] = None,
             temperature: float = 0.2, max_tokens: int = 4096) -> LLMResponse:
        from google.generativeai import protos

        system_instruction, contents = self._build_contents(messages)

        model = self.genai.GenerativeModel(
            self.model_name,
            system_instruction=system_instruction or None,
            tools=self._convert_tools(tools) if tools else None,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        response = model.generate_content(contents)

        # Parse response parts into text + tool calls
        content_text = ""
        tool_calls = []
        try:
            for part in response.parts:
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", None):
                    tool_calls.append(ToolCall(
                        id=fc.name,          # Gemini has no call IDs; use name
                        name=fc.name,
                        arguments=dict(fc.args),
                    ))
                elif getattr(part, "text", None):
                    content_text += part.text
        except Exception:
            try:
                content_text = response.text
            except Exception:
                content_text = ""

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            stop_reason="stop",
            raw=response,
        )

    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        # Structured so _build_contents can convert it to FunctionResponse parts
        return {
            "role": "user",
            "content": [{
                "type": "function_response",
                "name": tool_call_id,   # tool_call_id == function name for Gemini
                "content": result,
            }],
        }

    def format_assistant_message(self, response: LLMResponse) -> dict:
        content = []
        if response.content:
            content.append({"type": "text", "text": response.content})
        for tc in response.tool_calls:
            content.append({
                "type": "function_call",
                "name": tc.name,
                "args": tc.arguments,
            })
        # Fall back to plain string if nothing structured
        return {"role": "assistant", "content": content if content else response.content}


# ── Factory ──────────────────────────────────────────────────────────────────

def create_provider(provider: str, model: str = "", api_key: str = "") -> LLMProvider:
    """
    Create an LLM provider by name.
    
    provider: "anthropic", "openai", or "google"
    """
    providers = {
        "anthropic": lambda: AnthropicProvider(
            model=model or "claude-sonnet-4-20250514", api_key=api_key),
        "openai": lambda: OpenAIProvider(
            model=model or "gpt-4o", api_key=api_key),
        "google": lambda: GoogleProvider(
            model=model or "gemini-2.0-flash", api_key=api_key),
    }

    factory = providers.get(provider.lower())
    if not factory:
        raise ValueError(f"Unknown LLM provider '{provider}'. Choose: {list(providers.keys())}")

    logger.info(f"[LLM] Using provider: {provider} / {model}")
    return factory()
