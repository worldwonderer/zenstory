"""
Unified LLM client with sync/async/streaming support.

Features:
- Standard completion (sync and async)
- Streaming completion for SSE
- Structured output with JSON Schema
- Error handling and retry logic
"""

import json
import os
from collections.abc import AsyncGenerator, Callable, Generator
from typing import (
    Any,
    TypeVar,
)

import httpx
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from config.datetime_utils import utcnow
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def _get_positive_float_env(name: str, default: float) -> float:
    """Read a positive float env var with safe fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _get_non_negative_int_env(name: str, default: int) -> int:
    """Read a non-negative integer env var with safe fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


OPENAI_CLIENT_TIMEOUT_S = _get_positive_float_env("OPENAI_CLIENT_TIMEOUT_S", 45.0)
OPENAI_CLIENT_CONNECT_TIMEOUT_S = _get_positive_float_env(
    "OPENAI_CLIENT_CONNECT_TIMEOUT_S",
    5.0,
)
OPENAI_CLIENT_MAX_RETRIES = _get_non_negative_int_env(
    "OPENAI_CLIENT_MAX_RETRIES",
    2,
)


class LLMClient:
    """
    Unified LLM client for all agent operations.

    Supports:
    - Sync/async completion
    - Streaming output
    - Structured output with Pydantic models
    """

    # Model aliases — configurable via env vars
    MODEL_FAST = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    MODEL_QUALITY = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    # Default inference parameters
    DEFAULT_TEMPERATURE = 1.0
    DEFAULT_TOP_P = 0.95

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        """Initialize with OpenAI API key and optional base URL."""
        self.api_key = (
            api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        # Base URL resolution:
        # - If using DEEPSEEK_API_KEY, prefer DeepSeek endpoints over legacy OPENAI_API_BASE
        if base_url:
            self.base_url = base_url
        elif os.getenv("DEEPSEEK_BASE_URL"):
            self.base_url = os.getenv("DEEPSEEK_BASE_URL")
        elif os.getenv("DEEPSEEK_API_KEY"):
            self.base_url = "https://api.deepseek.com"
        else:
            self.base_url = os.getenv("OPENAI_API_BASE")
        if not self.api_key:
            raise ValueError("OpenAI API key not found")

        self._sync_client: OpenAI | None = None
        self._async_client: AsyncOpenAI | None = None

        log_with_context(
            logger,
            20,  # INFO
            "LLMClient initialized",
            base_url=self.base_url,
            model_fast=self.MODEL_FAST,
            model_quality=self.MODEL_QUALITY,
        )

    @property
    def sync_client(self) -> OpenAI:
        """Lazy-load sync client."""
        if self._sync_client is None:
            self._sync_client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    OPENAI_CLIENT_TIMEOUT_S,
                    connect=OPENAI_CLIENT_CONNECT_TIMEOUT_S,
                ),
                max_retries=OPENAI_CLIENT_MAX_RETRIES,
            )
        return self._sync_client

    @property
    def async_client(self) -> AsyncOpenAI:
        """Lazy-load async client."""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    OPENAI_CLIENT_TIMEOUT_S,
                    connect=OPENAI_CLIENT_CONNECT_TIMEOUT_S,
                ),
                max_retries=OPENAI_CLIENT_MAX_RETRIES,
            )
        return self._async_client

    # ========== Sync Methods ==========

    def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """
        Standard synchronous completion.

        Args:
            messages: Chat messages
            model: Model to use (default: MODEL_QUALITY)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        start_time = utcnow()
        model_name = model or self.MODEL_QUALITY

        log_with_context(
            logger,
            20,  # INFO
            "LLM sync completion started",
            model=model_name,
            message_count=len(messages),
            max_tokens=max_tokens,
        )

        try:
            response = self.sync_client.chat.completions.create(
                model=model_name,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature if temperature is not None else self.DEFAULT_TEMPERATURE,
                top_p=top_p if top_p is not None else self.DEFAULT_TOP_P,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content or ""
            duration_ms = int((utcnow() - start_time).total_seconds() * 1000)

            # Extract token usage if available
            usage = response.usage
            if usage:
                log_with_context(
                    logger,
                    20,  # INFO
                    "LLM sync completion completed",
                    model=model_name,
                    duration_ms=duration_ms,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    response_length=len(content),
                )
            else:
                log_with_context(
                    logger,
                    20,  # INFO
                    "LLM sync completion completed",
                    model=model_name,
                    duration_ms=duration_ms,
                    response_length=len(content),
                )

            return content
        except Exception as e:
            log_with_context(
                logger,
                40,  # ERROR
                "LLM sync completion failed",
                model=model_name,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=int((utcnow() - start_time).total_seconds() * 1000),
            )
            raise

    def complete_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> Generator[str, None, None]:
        """
        Streaming synchronous completion.

        Args:
            messages: Chat messages
            model: Model to use
            temperature: Sampling temperature

        Yields:
            Text chunks as they are generated
        """
        stream = self.sync_client.chat.completions.create(
            model=model or self.MODEL_QUALITY,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else self.DEFAULT_TEMPERATURE,
            top_p=top_p if top_p is not None else self.DEFAULT_TOP_P,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:  # type: ignore[union-attr]
                yield chunk.choices[0].delta.content  # type: ignore[union-attr]

    def complete_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
    ) -> T:
        """
        Structured output using JSON Schema.

        Args:
            messages: Chat messages
            response_model: Pydantic model for response
            model: Model to use

        Returns:
            Validated Pydantic model instance
        """
        response = self.sync_client.chat.completions.create(
            model=model or self.MODEL_QUALITY,
            messages=messages,  # type: ignore[arg-type]
            response_format=self._build_json_schema(response_model),
            temperature=0.0,
        )  # type: ignore[call-overload]
        data = json.loads(response.choices[0].message.content or "{}")
        return response_model.model_validate(data)

    # ========== Async Methods ==========

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int = 2000,
        thinking_enabled: bool = True,
    ) -> str:
        """
        Async completion.

        Args:
            messages: Chat messages
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            thinking_enabled: Whether to enable reasoning/thinking mode (default True).
                             Set to False for simple tasks that don't need reasoning.

        Returns:
            Generated text
        """
        start_time = utcnow()
        model_name = model or self.MODEL_QUALITY

        log_with_context(
            logger,
            20,  # INFO
            "LLM async completion started",
            model=model_name,
            message_count=len(messages),
            max_tokens=max_tokens,
            thinking_enabled=thinking_enabled,
        )

        extra_body = {}

        try:
            response = await self.async_client.chat.completions.create(
                model=model_name,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature if temperature is not None else self.DEFAULT_TEMPERATURE,
                top_p=top_p if top_p is not None else self.DEFAULT_TOP_P,
                max_tokens=max_tokens,
                extra_body=extra_body if extra_body else None,
            )

            content = response.choices[0].message.content or ""
            duration_ms = int((utcnow() - start_time).total_seconds() * 1000)

            # Extract token usage if available
            usage = response.usage
            if usage:
                log_with_context(
                    logger,
                    20,  # INFO
                    "LLM async completion completed",
                    model=model_name,
                    duration_ms=duration_ms,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    response_length=len(content),
                )
            else:
                log_with_context(
                    logger,
                    20,  # INFO
                    "LLM async completion completed",
                    model=model_name,
                    duration_ms=duration_ms,
                    response_length=len(content),
                )

            return content
        except Exception as e:
            log_with_context(
                logger,
                40,  # ERROR
                "LLM async completion failed",
                model=model_name,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=int((utcnow() - start_time).total_seconds() * 1000),
            )
            raise

    async def acomplete_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async streaming completion for SSE.

        Args:
            messages: Chat messages
            model: Model to use
            temperature: Sampling temperature

        Yields:
            Text chunks as they are generated
        """
        stream = await self.async_client.chat.completions.create(
            model=model or self.MODEL_QUALITY,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else self.DEFAULT_TEMPERATURE,
            top_p=top_p if top_p is not None else self.DEFAULT_TOP_P,
            stream=True,
        )
        async for chunk in stream:  # type: ignore[union-attr]
            if chunk.choices[0].delta.content:  # type: ignore[union-attr]
                yield chunk.choices[0].delta.content  # type: ignore[union-attr]

    async def acomplete_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
    ) -> T:
        """
        Async structured output.

        Args:
            messages: Chat messages
            response_model: Pydantic model for response
            model: Model to use

        Returns:
            Validated Pydantic model instance
        """
        response = await self.async_client.chat.completions.create(
            model=model or self.MODEL_QUALITY,
            messages=messages,  # type: ignore[arg-type]
            response_format=self._build_json_schema(response_model),
            temperature=0.0,
        )  # type: ignore[call-overload]
        data = json.loads(response.choices[0].message.content or "{}")
        return response_model.model_validate(data)

    async def acomplete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_handler: Callable,
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_iterations: int = 5,
    ) -> dict[str, Any]:
        """
        Async completion with Function Calling support.

        This method handles the full tool calling loop:
        1. Call LLM with tools
        2. If tool_calls present, execute tools via tool_handler
        3. Feed tool results back to LLM
        4. Repeat until LLM generates final response

        Args:
            messages: Chat messages
            tools: List of tool definitions (OpenAI format)
            tool_handler: Callable to execute tools, signature:
                         tool_handler(tool_name: str, tool_args: dict) -> dict
            model: Model to use
            temperature: Sampling temperature
            max_iterations: Maximum tool calling iterations

        Returns:
            Dict with:
            - type: "text" | "tool_calls"
            - content: Final text response
            - tool_calls: List of tool calls made
            - tool_results: List of tool execution results

        Example:
            >>> def my_tool_handler(name, args):
            ...     if name == "create_entity":
            ...         return {"status": "success", "data": {"id": 123}}
            >>> result = await llm.acomplete_with_tools(
            ...     messages=[{"role": "user", "content": "Create outline"}],
            ...     tools=tool_definitions,
            ...     tool_handler=my_tool_handler
            ... )
        """
        start_time = utcnow()
        model_name = model or self.MODEL_QUALITY

        log_with_context(
            logger,
            20,  # INFO
            "LLM async completion with tools started",
            model=model_name,
            message_count=len(messages),
            tool_count=len(tools),
            max_iterations=max_iterations,
        )

        current_messages = messages.copy()
        all_tool_calls: list[dict[str, Any]] = []
        all_tool_results: list[dict[str, Any]] = []

        for iteration in range(max_iterations):
            # Call LLM with tools
            response = await self.async_client.chat.completions.create(
                model=model_name,
                messages=current_messages,  # type: ignore[arg-type]
                tools=tools,
                tool_choice="auto",
                temperature=temperature if temperature is not None else self.DEFAULT_TEMPERATURE,
                top_p=top_p if top_p is not None else self.DEFAULT_TOP_P,
            )  # type: ignore[call-overload]

            message = response.choices[0].message

            # Check if LLM wants to call tools
            if not message.tool_calls:
                # No more tool calls, return final response
                duration_ms = int((utcnow() - start_time).total_seconds() * 1000)
                log_with_context(
                    logger,
                    20,  # INFO
                    "LLM async completion with tools completed (text response)",
                    model=model_name,
                    duration_ms=duration_ms,
                    iterations=iteration + 1,
                    total_tool_calls=len(all_tool_calls),
                )
                return {
                    "type": "text",
                    "content": message.content or "",
                    "tool_calls": all_tool_calls,
                    "tool_results": all_tool_results,
                    "iterations": iteration + 1,
                }

            # Execute tool calls
            tool_calls = message.tool_calls
            all_tool_calls.extend(tool_calls)

            log_with_context(
                logger,
                20,  # INFO
                "LLM tool calling iteration",
                model=model_name,
                iteration=iteration + 1,
                tool_count=len(tool_calls),
            )

            # Add assistant message with tool calls to history
            current_messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [  # type: ignore[dict-item]
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            # Execute each tool and collect results
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # Execute tool via handler
                try:
                    tool_result = tool_handler(tool_name, tool_args)
                    log_with_context(
                        logger,
                        20,  # INFO
                        "Tool executed successfully",
                        model=model_name,
                        iteration=iteration + 1,
                        tool_name=tool_name,
                    )
                except Exception as e:
                    tool_result = {
                        "status": "error",
                        "error": str(e),
                    }
                    log_with_context(
                        logger,
                        40,  # ERROR
                        "Tool execution failed",
                        model=model_name,
                        iteration=iteration + 1,
                        tool_name=tool_name,
                        error=str(e),
                    )

                # Add tool result message to history
                current_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result),
                    }
                )

                all_tool_results.append(
                    {
                        "id": tool_call.id,
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result,
                    }
                )

        # Max iterations reached without final response
        duration_ms = int((utcnow() - start_time).total_seconds() * 1000)
        log_with_context(
            logger,
            30,  # WARNING
            "LLM async completion with tools reached max iterations",
            model=model_name,
            duration_ms=duration_ms,
            max_iterations=max_iterations,
            total_tool_calls=len(all_tool_calls),
        )
        return {
            "type": "tool_calls",
            "content": "",
            "tool_calls": all_tool_calls,
            "tool_results": all_tool_results,
            "error": f"Max iterations ({max_iterations}) reached",
        }

    # ========== Helpers ==========

    def _build_json_schema(self, model: type[BaseModel]) -> dict[str, Any]:
        """Build JSON schema for structured output."""
        schema = model.model_json_schema()

        # Clean up schema for OpenAI compatibility
        def clean_schema(s: dict) -> dict[str, Any]:
            """Remove unsupported fields and ensure strict mode compatibility."""
            cleaned: dict[str, Any] = {}
            for key, value in s.items():
                if key in ("title", "description", "examples", "default"):
                    continue
                if isinstance(value, dict):
                    cleaned[key] = clean_schema(value)
                elif isinstance(value, list):
                    cleaned[key] = [  # type: ignore[assignment]
                        clean_schema(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    cleaned[key] = value

            # Ensure additionalProperties is set for objects
            if (
                cleaned.get("type") == "object"
                and "additionalProperties" not in cleaned
            ):
                cleaned["additionalProperties"] = False  # type: ignore[assignment]

            return cleaned

        cleaned_schema = clean_schema(schema)

        # Handle $defs (definitions) if present
        if "$defs" in cleaned_schema:
            cleaned_schema["$defs"] = {
                k: clean_schema(v) for k, v in cleaned_schema["$defs"].items()
            }

        return {
            "type": "json_schema",
            "json_schema": {
                "name": model.__name__,
                "strict": True,
                "schema": cleaned_schema,
            },
        }


# Singleton instance
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
