"""
Anthropic SDK client wrapper for zenstory Agent.

Provides streaming message creation with tool calling support.
"""

import ast
import asyncio
import os
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

import httpx
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    RateLimitError,
)

from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


class _StripAuthHeaderClient(httpx.AsyncClient):
    """httpx client that strips the Authorization header injected by anthropic SDK.

    The anthropic SDK (>=0.40) sends ``Authorization: Bearer PROXY_MANAGED`` alongside
    ``x-api-key``.  Some providers (e.g. DeepSeek) check the Authorization header first
    and reject the request.  Stripping is safe for all current providers because the
    native Anthropic API authenticates via ``x-api-key``, not ``Authorization: Bearer``.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("timeout", httpx.Timeout(600.0, connect=10.0))
        kwargs.setdefault("limits", httpx.Limits(max_connections=100, max_keepalive_connections=20))
        super().__init__(**kwargs)

    async def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        if "authorization" in request.headers:
            del request.headers["authorization"]
        return await super().send(request, **kwargs)


# Default configuration — env vars allow instant provider switching
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEFAULT_MAX_TOKENS = 64000  # Increased to accommodate thinking budget
DEFAULT_AGENT_PRIMARY_BASE_URL = os.getenv(
    "DEEPSEEK_ANTHROPIC_BASE_URL",
    "https://api.deepseek.com/anthropic",
)
TRANSIENT_PROVIDER_ERROR_CODES = {"1234", "1302", "1305", "429", "503"}


class StreamEventType(Enum):
    """Types of streaming events."""

    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    MESSAGE_START = "message_start"
    MESSAGE_END = "message_end"
    ERROR = "error"
    AGENT_SELECTED = "agent_selected"
    HANDOFF = "handoff"  # Agent requests handoff to another agent
    ITERATION_EXHAUSTED = "iteration_exhausted"  # Iteration limit reached
    ROUTER_THINKING = "router_thinking"  # Router 正在分析请求
    ROUTER_DECIDED = "router_decided"  # Router 决策完成
    WORKFLOW_STOPPED = "workflow_stopped"  # 工作流因需要澄清而停止
    WORKFLOW_COMPLETE = "workflow_complete"  # 任务完成，工作流正常结束
    STEERING_RECEIVED = "steering_received"  # Steering message received from user


@dataclass
class StreamEvent:
    """Represents a streaming event from Anthropic API."""

    type: StreamEventType
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnthropicConfig:
    """Configuration for AnthropicClient."""

    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = 1.0
    api_key: str | None = None
    base_url: str | None = None
    fallback_base_url: str | None = None
    # Extended thinking configuration
    thinking_enabled: bool = True
    thinking_budget_tokens: int = 10000


class AnthropicClient:
    """
    Anthropic SDK client wrapper with streaming and tool calling support.

    Features:
    - Async streaming message creation
    - Tool calling with automatic result handling
    - Configurable model and parameters
    """

    def __init__(self, config: AnthropicConfig | None = None) -> None:
        """Initialize the Anthropic client."""
        self.config = config or AnthropicConfig()

        # Get API key from config or environment
        api_key = self.config.api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "LLM API key not found. "
                "Set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY environment variable."
            )

        # Resolve base URL: explicit config > DEEPSEEK env > ANTHROPIC env > module default
        if not self.config.base_url:
            self.config = replace(
                self.config,
                base_url=os.getenv("DEEPSEEK_ANTHROPIC_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL"),
            )

        # Allow base URL override from environment for compatible Anthropic gateways.
        primary_base_url = _normalize_base_url(
            self.config.base_url if self.config.base_url is not None else os.getenv("ANTHROPIC_BASE_URL")
        )
        fallback_base_url = _normalize_base_url(self.config.fallback_base_url)
        self._api_key = api_key
        self._base_url_candidates = _build_base_url_candidates(primary_base_url, fallback_base_url)
        self._clients: dict[str | None, AsyncAnthropic] = {}

        # Initialize the primary async client eagerly so initialization errors surface early.
        self._client = self._get_client_for_base_url(self._base_url_candidates[0])

        log_with_context(
            logger,
            20,  # INFO
            "AnthropicClient initialized",
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            thinking_enabled=self.config.thinking_enabled,
            thinking_budget_tokens=self.config.thinking_budget_tokens,
            base_url=self._base_url_candidates[0],
            fallback_base_url=self._base_url_candidates[1] if len(self._base_url_candidates) > 1 else None,
        )

    def _get_client_for_base_url(self, base_url: str | None) -> AsyncAnthropic:
        """Get or create an AsyncAnthropic client for a specific base URL."""
        if base_url not in self._clients:
            self._clients[base_url] = AsyncAnthropic(
                api_key=self._api_key,
                base_url=base_url,
                http_client=_StripAuthHeaderClient(),
            )
        return self._clients[base_url]

    async def stream_message(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream a message response from Anthropic API.

        Args:
            messages: List of message dicts with role and content
            system_prompt: Optional system prompt
            tools: Optional list of tool definitions in Anthropic format

        Yields:
            StreamEvent objects for text, thinking, tool_use, etc.
        """
        log_with_context(
            logger,
            20,  # INFO
            "Starting stream_message",
            message_count=len(messages),
            has_system=system_prompt is not None,
            tool_count=len(tools) if tools else 0,
        )

        # Build request parameters
        params: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
        }

        if system_prompt:
            params["system"] = system_prompt

        if tools:
            params["tools"] = tools

        # Apply base temperature when extended thinking is disabled.
        # (When thinking is enabled, providers typically require temperature=1.)
        params["temperature"] = float(self.config.temperature)

        # Include metadata.user_id so the gateway identifies this as a
        # Claude Code client request and applies priority routing.
        try:
            from agent.tools.mcp_tools import ToolContext
            ctx = ToolContext._get_context()
            uid = ctx.get("user_id") if isinstance(ctx, dict) else None
            if uid:
                params["metadata"] = {"user_id": uid}
        except Exception:
            pass

        # Thinking mode control — DeepSeek defaults to enabled; must explicitly disable.
        if self.config.thinking_enabled:
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget_tokens,
            }
            # Extended thinking requires temperature = 1
            params["temperature"] = 1.0
            # Ensure max_tokens > budget_tokens
            min_tokens = self.config.thinking_budget_tokens + 4096
            params["max_tokens"] = max(self.config.max_tokens, min_tokens)
        else:
            params["thinking"] = {"type": "disabled"}

        max_retries = _parse_int_env("AGENT_LLM_STREAM_MAX_RETRIES", 3, min_value=0)
        base_delay_s = _parse_float_env("AGENT_LLM_STREAM_RETRY_BASE_DELAY_S", 1.0, min_value=0.0)
        max_delay_s = _parse_float_env("AGENT_LLM_STREAM_RETRY_MAX_DELAY_S", 4.0, min_value=0.0)
        jitter_s = _parse_float_env("AGENT_LLM_STREAM_RETRY_JITTER_S", 0.25, min_value=0.0)
        # 0 disables the per-attempt elapsed-time budget check. We still only retry when
        # nothing has been streamed yet to avoid duplicating partial outputs.
        max_attempt_elapsed_s = _parse_float_env("AGENT_LLM_STREAM_RETRY_MAX_ATTEMPT_ELAPSED_S", 0.0, min_value=0.0)

        # Only retry failures that happen before we have streamed any meaningful content.
        # (Once tokens / tool calls have started, an automatic retry may cause duplicated output.)
        message_start_emitted = False
        attempt = 0
        base_url_index = 0
        while True:
            streamed_anything = False
            attempt_started_at = asyncio.get_running_loop().time()
            active_base_url = self._base_url_candidates[base_url_index]
            active_client = self._get_client_for_base_url(active_base_url)
            try:
                async with active_client.messages.stream(**params) as stream:
                    # Yield message start event (only once across retries)
                    if not message_start_emitted:
                        yield StreamEvent(
                            type=StreamEventType.MESSAGE_START,
                            data={"model": self.config.model},
                        )
                        message_start_emitted = True

                    current_tool_use: dict[str, Any] | None = None

                    async for event in stream:
                        async for stream_event in self._process_stream_event(
                            event, current_tool_use
                        ):
                            if stream_event.type in {
                                StreamEventType.TEXT,
                                StreamEventType.THINKING,
                                StreamEventType.TOOL_USE,
                            }:
                                streamed_anything = True
                            if stream_event.type == StreamEventType.TOOL_USE:
                                status = stream_event.data.get("status")
                                if status == "start" and "id" in stream_event.data:
                                    # Track current tool use for input accumulation
                                    current_tool_use = stream_event.data.copy()
                                elif status == "stop":
                                    # Avoid emitting duplicate stop events on subsequent content_block_stop events.
                                    current_tool_use = None
                            yield stream_event

                    # Get final message for stop reason
                    final_message = await stream.get_final_message()
                    usage_data = {
                        "input_tokens": final_message.usage.input_tokens,
                        "output_tokens": final_message.usage.output_tokens,
                    }
                    # DeepSeek cache metrics (Anthropic protocol)
                    for attr in ("cache_creation_input_tokens", "cache_read_input_tokens"):
                        val = getattr(final_message.usage, attr, None)
                        if val:
                            usage_data[attr] = val
                    logger.info(
                        "LLM stream usage: %s (model=%s, base=%s)",
                        usage_data, self.config.model, active_base_url,
                    )
                    yield StreamEvent(
                        type=StreamEventType.MESSAGE_END,
                        data={
                            "stop_reason": final_message.stop_reason,
                            "usage": usage_data,
                        },
                    )
                    return

            except Exception as e:
                error_type = type(e).__name__
                error_text = str(e) or repr(e)
                attempt_elapsed_s = asyncio.get_running_loop().time() - attempt_started_at

                status_code = _extract_status_code(e)
                provider_code, provider_message = _extract_provider_error_details(e, error_text)
                is_retryable_error, should_failover_base_url = _classify_retryable_error(
                    e,
                    error_text,
                    status_code=status_code,
                    provider_code=provider_code,
                    provider_message=provider_message,
                )

                within_attempt_budget = max_attempt_elapsed_s <= 0 or attempt_elapsed_s <= max_attempt_elapsed_s

                # Allow mid-stream retries for transient provider errors
                # (e.g. z.ai 1234 network blips) — the AI regenerates a fresh
                # response and the frontend seamlessly picks up the new stream.
                is_transient = provider_code in TRANSIENT_PROVIDER_ERROR_CODES or _is_transient_provider_error(provider_code, provider_message, error_text)
                should_retry = (
                    attempt < max_retries
                    and is_retryable_error
                    and within_attempt_budget
                    and (not streamed_anything or is_transient)
                )
                retry_delay_s: float | None = None
                next_base_url: str | None = active_base_url
                if should_retry:
                    retry_delay_s = base_delay_s * (2**attempt)
                    if max_delay_s > 0:
                        retry_delay_s = min(retry_delay_s, max_delay_s)
                    if jitter_s > 0:
                        retry_delay_s += random.uniform(0, jitter_s)
                    if should_failover_base_url and base_url_index + 1 < len(self._base_url_candidates):
                        base_url_index += 1
                        next_base_url = self._base_url_candidates[base_url_index]

                log_with_context(
                    logger,
                    40,  # ERROR
                    "Error in stream_message",
                    error=error_text,
                    error_type=error_type,
                    error_repr=repr(e),
                    status_code=status_code,
                    provider_code=provider_code,
                    provider_message=provider_message,
                    attempt_elapsed_s=attempt_elapsed_s,
                    streamed_anything=streamed_anything,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    within_attempt_budget=within_attempt_budget,
                    will_retry=should_retry,
                    retry_delay_s=retry_delay_s,
                    active_base_url=active_base_url,
                    next_base_url=next_base_url if should_retry else None,
                )

                if should_retry:
                    await asyncio.sleep(retry_delay_s or 0)
                    attempt += 1
                    continue

                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    data={"error": error_text, "error_type": error_type},
                )
                return

    async def _process_stream_event(
        self,
        event: Any,
        current_tool_use: dict[str, Any] | None,
    ) -> AsyncIterator[StreamEvent]:
        """Process a single stream event from Anthropic API."""
        event_type = getattr(event, "type", None)

        if event_type == "content_block_start":
            content_block = event.content_block
            block_type = getattr(content_block, "type", None)

            if block_type == "text":
                pass  # Text will come in delta events
            elif block_type == "thinking":
                pass  # Thinking will come in delta events
            elif block_type == "tool_use":
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "id": content_block.id,
                        "name": content_block.name,
                        "input": {},
                        "status": "start",
                    },
                )

        elif event_type == "content_block_delta":
            delta = event.delta
            delta_type = getattr(delta, "type", None)

            if delta_type == "text_delta":
                yield StreamEvent(
                    type=StreamEventType.TEXT,
                    data={"text": delta.text},
                )
            elif delta_type == "thinking_delta":
                yield StreamEvent(
                    type=StreamEventType.THINKING,
                    data={"thinking": delta.thinking},
                )
            elif delta_type == "input_json_delta":
                # Tool input is streamed as JSON delta
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "partial_json": delta.partial_json,
                        "status": "delta",
                    },
                )

        elif event_type == "content_block_stop":
            # Content block finished
            if current_tool_use:
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "id": current_tool_use.get("id"),
                        "name": current_tool_use.get("name"),
                        "status": "stop",
                    },
                )

    async def create_message(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Create a non-streaming message response.

        Args:
            messages: List of message dicts with role and content
            system_prompt: Optional system prompt
            tools: Optional list of tool definitions

        Returns:
            Dict with response content and metadata
        """
        params: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
        }

        if system_prompt:
            params["system"] = system_prompt

        if tools:
            params["tools"] = tools

        params["temperature"] = float(self.config.temperature)

        # Thinking mode control — DeepSeek defaults to enabled; must explicitly disable.
        if self.config.thinking_enabled:
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget_tokens,
            }
            # Extended thinking requires temperature = 1
            params["temperature"] = 1.0
            # Ensure max_tokens > budget_tokens
            min_tokens = self.config.thinking_budget_tokens + 4096
            params["max_tokens"] = max(self.config.max_tokens, min_tokens)
        else:
            params["thinking"] = {"type": "disabled"}

        response = await self._client.messages.create(**params)

        usage_data = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        for attr in ("cache_creation_input_tokens", "cache_read_input_tokens"):
            val = getattr(response.usage, attr, None)
            if val:
                usage_data[attr] = val
        logger.info(
            "LLM non-stream usage: %s (model=%s)",
            usage_data, self.config.model,
        )
        return {
            "id": response.id,
            "content": [
                self._serialize_content_block(block) for block in response.content
            ],
            "stop_reason": response.stop_reason,
            "usage": usage_data,
        }

    def _serialize_content_block(self, block: Any) -> dict[str, Any]:
        """Serialize a content block to dict."""
        block_type = getattr(block, "type", "unknown")

        serializers = {
            "text": lambda: {"type": "text", "text": block.text},
            "tool_use": lambda: {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            },
            "thinking": lambda: {
                "type": "thinking",
                "thinking": block.thinking,
            },
        }

        return serializers.get(block_type, lambda: {"type": block_type})()


# Singleton instance
_anthropic_client: AnthropicClient | None = None
_router_client: AnthropicClient | None = None


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_str_env(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _parse_int_env(
    name: str,
    default: int,
    *,
    min_value: int | None = None,
    on_underflow: str = "clamp",
) -> int:
    raw = os.getenv(name)
    if raw is None:
        value = default
    else:
        raw = raw.strip()
        if not raw:
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                log_with_context(
                    logger,
                    30,  # WARNING
                    "Invalid integer env value; falling back to default",
                    env=name,
                    raw=raw,
                    default=default,
                )
                value = default

    if min_value is not None and value < min_value:
        if on_underflow not in {"clamp", "default"}:
            on_underflow = "clamp"

        log_with_context(
            logger,
            30,  # WARNING
            "Integer env below minimum; applying fallback",
            env=name,
            value=value,
            min_value=min_value,
            default=default,
            action=on_underflow,
        )

        if on_underflow == "default":
            return default if default >= min_value else min_value
        return min_value
    return value


def _parse_float_env(
    name: str,
    default: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    raw = os.getenv(name)
    if raw is None:
        value = default
    else:
        raw = raw.strip()
        if not raw:
            value = default
        else:
            try:
                value = float(raw)
            except ValueError:
                log_with_context(
                    logger,
                    30,  # WARNING
                    "Invalid float env value; falling back to default",
                    env=name,
                    raw=raw,
                    default=default,
                )
                value = default

    if min_value is not None and value < min_value:
        value = min_value
    if max_value is not None and value > max_value:
        value = max_value
    return value


def _normalize_base_url(value: str | None) -> str | None:
    """Normalize base URL env/config values."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_base_url_candidates(*base_urls: str | None) -> list[str | None]:
    """Deduplicate base URL candidates while preserving order."""
    candidates: list[str | None] = []
    seen: set[str | None] = set()

    for base_url in base_urls:
        normalized = _normalize_base_url(base_url)
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(normalized)

    return candidates or [None]


def _read_optional_base_url_override(name: str) -> tuple[bool, str | None]:
    """Read a base URL override env var, preserving whether it was explicitly set."""
    raw = os.getenv(name)
    if raw is None:
        return False, None
    return True, _normalize_base_url(raw)


def _resolve_agent_base_url_pair() -> tuple[str | None, str | None]:
    """
    Resolve primary/fallback base URLs for agent Anthropic traffic.

    Default behavior:
    - Primary: Z.ai Anthropic-compatible gateway
    - Fallback: existing ANTHROPIC_BASE_URL (or provider default when unset)

    Operators can override either side via AGENT_ANTHROPIC_PRIMARY_BASE_URL /
    AGENT_ANTHROPIC_FALLBACK_BASE_URL. Setting AGENT_ANTHROPIC_PRIMARY_BASE_URL
    to an empty string disables the Z.ai-first default.
    """
    primary_set, primary_override = _read_optional_base_url_override("AGENT_ANTHROPIC_PRIMARY_BASE_URL")
    fallback_set, fallback_override = _read_optional_base_url_override("AGENT_ANTHROPIC_FALLBACK_BASE_URL")
    original_base_url = _normalize_base_url(os.getenv("ANTHROPIC_BASE_URL"))

    if primary_set:
        primary_base_url = primary_override if primary_override is not None else original_base_url
    else:
        primary_base_url = DEFAULT_AGENT_PRIMARY_BASE_URL

    fallback_base_url = fallback_override if fallback_set else original_base_url
    if primary_base_url == fallback_base_url:
        fallback_base_url = None

    return primary_base_url, fallback_base_url


def _extract_status_code(error: Exception) -> int | None:
    """Extract HTTP status code from SDK/network exceptions when available."""
    status_code = getattr(error, "status_code", None)
    if status_code is not None:
        return status_code
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)


def _extract_provider_error_details(error: Exception, error_text: str) -> tuple[str | None, str | None]:
    """Extract provider-specific error code/message from SDK body or serialized payload."""
    payload = getattr(error, "body", None)

    if not isinstance(payload, dict):
        try:
            parsed = ast.literal_eval(error_text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed

    if not isinstance(payload, dict):
        return None, None

    error_obj = payload.get("error")
    if not isinstance(error_obj, dict):
        return None, None

    code_raw = error_obj.get("code")
    message_raw = error_obj.get("message")
    provider_code = str(code_raw).strip() if code_raw is not None else None
    provider_message = str(message_raw).strip() if message_raw is not None else None
    return provider_code or None, provider_message or None


def _is_transient_provider_error(
    provider_code: str | None,
    provider_message: str | None,
    error_text: str,
) -> bool:
    """Detect provider-side transient throttling / overload responses."""
    if provider_code in TRANSIENT_PROVIDER_ERROR_CODES:
        return True

    combined_text = " ".join(
        part for part in (provider_message, error_text) if part
    ).lower()
    transient_fragments = (
        "network error",
        "rate limit",
        "overloaded",
        "capacity",
        "请求频率",
        "速率限制",
        "访问量过大",
        "稍后再试",
        "try again later",
        "too many requests",
        "server error",
    )
    return any(fragment in combined_text for fragment in transient_fragments)


def _classify_retryable_error(
    error: Exception,
    error_text: str,
    *,
    status_code: int | None,
    provider_code: str | None,
    provider_message: str | None,
) -> tuple[bool, bool]:
    """Return (is_retryable, should_failover_base_url)."""
    is_failover_worthy = bool(
        isinstance(
            error,
            (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
                APIConnectionError,
                APITimeoutError,
            ),
        )
        or status_code in {408}
        or (isinstance(status_code, int) and status_code >= 500)
        or ("Internal Network Failure" in error_text)
    )

    is_transient_provider = _is_transient_provider_error(provider_code, provider_message, error_text)

    # Transient provider errors (e.g. z.ai 1234 "Network error") indicate
    # the gateway itself is having trouble — failover to the alternate URL
    # so the retry has a better chance of success.
    is_transient_failover = bool(
        is_transient_provider
        and isinstance(error, (RateLimitError, APIStatusError))
    )

    is_retryable = bool(
        is_failover_worthy
        or is_transient_failover
        or (isinstance(error, RateLimitError) and is_transient_provider)
        or (isinstance(error, APIStatusError) and is_transient_provider)
    )
    return is_retryable, is_failover_worthy or is_transient_failover


def get_anthropic_client(config: AnthropicConfig | None = None) -> AnthropicClient:
    """Get or create the singleton Anthropic client instance."""
    global _anthropic_client
    if _anthropic_client is None:
        if config is None:
            thinking_budget = _parse_int_env(
                "AGENT_THINKING_BUDGET_TOKENS",
                int(getattr(AnthropicConfig, "thinking_budget_tokens", 10000)),
                min_value=0,
            )
            thinking_enabled = _parse_bool_env(
                "AGENT_THINKING_ENABLED",
                AnthropicConfig.thinking_enabled,  # type: ignore[attr-defined]
            )
            if thinking_budget <= 0:
                thinking_enabled = False
                thinking_budget = 0
            primary_base_url, fallback_base_url = _resolve_agent_base_url_pair()

            config = AnthropicConfig(
                model=_parse_str_env("AGENT_MODEL", DEFAULT_MODEL),
                max_tokens=_parse_int_env(
                    "AGENT_MAX_TOKENS",
                    DEFAULT_MAX_TOKENS,
                    min_value=1,
                    on_underflow="default",
                ),
                temperature=_parse_float_env("AGENT_TEMPERATURE", 1.0, min_value=0.0, max_value=2.0),
                base_url=primary_base_url,
                fallback_base_url=fallback_base_url,
                thinking_enabled=thinking_enabled,
                thinking_budget_tokens=thinking_budget,
            )
        _anthropic_client = AnthropicClient(config)
    return _anthropic_client


def get_router_client(config: AnthropicConfig | None = None) -> AnthropicClient:
    """
    Get or create a dedicated router client.

    Router calls are latency-sensitive and do not need extended thinking.
    We keep a separate singleton so disabling thinking / shrinking token budget
    does not affect the main writer/reviewer agents.
    """
    global _router_client
    if _router_client is None:
        if config is None:
            router_thinking_enabled = os.getenv("AGENT_ROUTER_THINKING_ENABLED", "false").strip().lower() in {
                "1",
                "true",
                "yes",
                "y",
                "on",
            }
            router_thinking_budget = _parse_int_env(
                "AGENT_ROUTER_THINKING_BUDGET_TOKENS",
                0,
                min_value=0,
            )
            if router_thinking_budget <= 0:
                router_thinking_enabled = False
                router_thinking_budget = 0
            primary_base_url, fallback_base_url = _resolve_agent_base_url_pair()

            config = AnthropicConfig(
                model=_parse_str_env("AGENT_ROUTER_MODEL", DEFAULT_MODEL),
                # NOTE:
                # - This is the completion/output token limit (provider-dependent).
                # - Keep it reasonably high to avoid truncation on gateways that
                #   interpret it as a total token budget.
                max_tokens=_parse_int_env(
                    "AGENT_ROUTER_MAX_TOKENS",
                    4096,
                    min_value=1,
                    on_underflow="default",
                ),
                # Router temperature should usually stay consistent with the
                # project's global defaults unless explicitly overridden.
                temperature=_parse_float_env("AGENT_ROUTER_TEMPERATURE", 1.0, min_value=0.0, max_value=2.0),
                base_url=primary_base_url,
                fallback_base_url=fallback_base_url,
                thinking_enabled=router_thinking_enabled,
                thinking_budget_tokens=router_thinking_budget,
            )
        _router_client = AnthropicClient(config)
    return _router_client


def reset_anthropic_client() -> None:
    """Reset the singleton client (for testing)."""
    global _anthropic_client
    _anthropic_client = None


def reset_router_client() -> None:
    """Reset the router singleton client (for testing)."""
    global _router_client
    _router_client = None
