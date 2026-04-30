"""
Tests for agent/llm/anthropic_client.py

Tests the Anthropic SDK client wrapper.
"""

import os
from unittest.mock import ANY, patch

import httpx
import pytest
from anthropic import APIStatusError, RateLimitError


class _FakeStream:
    def __init__(self, *, events: list[object] | None = None, raise_after: Exception | None = None, final_message: object | None = None):
        self._events = list(events or [])
        self._raise_after = raise_after
        self._final_message = final_message

    def __aiter__(self):
        async def _gen():
            for event in self._events:
                yield event
            if self._raise_after is not None:
                raise self._raise_after

        return _gen()

    async def get_final_message(self):
        return self._final_message


class _FakeStreamCM:
    def __init__(self, *, stream: _FakeStream | None = None, exc: Exception | None = None):
        self._stream = stream
        self._exc = exc

    async def __aenter__(self):
        if self._exc is not None:
            raise self._exc
        return self._stream

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeMessages:
    def __init__(self, cms: list[_FakeStreamCM]):
        self._cms = list(cms)
        self.calls = 0

    def stream(self, **kwargs):
        cm = self._cms[self.calls]
        self.calls += 1
        return cm


class _FakeAnthropic:
    def __init__(self, cms: list[_FakeStreamCM]):
        self.messages = _FakeMessages(cms)


@pytest.mark.unit
class TestAnthropicConfig:
    """Tests for AnthropicConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from agent.llm.anthropic_client import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, AnthropicConfig

        config = AnthropicConfig()

        assert config.model == DEFAULT_MODEL
        assert config.max_tokens == DEFAULT_MAX_TOKENS
        assert config.temperature == 1.0
        assert config.api_key is None
        assert config.base_url is None
        assert config.fallback_base_url is None

    def test_custom_config(self):
        """Test custom configuration values."""
        from agent.llm.anthropic_client import AnthropicConfig

        config = AnthropicConfig(
            model="claude-3-opus",
            max_tokens=4096,
            temperature=0.7,
            api_key="test-key",
            base_url="https://custom.api.com",
        )

        assert config.model == "claude-3-opus"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.api_key == "test-key"
        assert config.base_url == "https://custom.api.com"


@pytest.mark.unit
class TestStreamEvent:
    """Tests for StreamEvent dataclass."""

    def test_stream_event_creation(self):
        """Test creating a StreamEvent."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        event = StreamEvent(
            type=StreamEventType.TEXT,
            data={"text": "Hello"},
        )

        assert event.type == StreamEventType.TEXT
        assert event.data == {"text": "Hello"}

    def test_stream_event_default_data(self):
        """Test StreamEvent with default empty data."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        event = StreamEvent(type=StreamEventType.MESSAGE_START)

        assert event.type == StreamEventType.MESSAGE_START
        assert event.data == {}


@pytest.mark.unit
class TestStreamEventType:
    """Tests for StreamEventType enum."""

    def test_all_event_types(self):
        """Test all event types are defined."""
        from agent.llm.anthropic_client import StreamEventType

        assert StreamEventType.TEXT.value == "text"
        assert StreamEventType.THINKING.value == "thinking"
        assert StreamEventType.TOOL_USE.value == "tool_use"
        assert StreamEventType.TOOL_RESULT.value == "tool_result"
        assert StreamEventType.MESSAGE_START.value == "message_start"
        assert StreamEventType.MESSAGE_END.value == "message_end"
        assert StreamEventType.ERROR.value == "error"


@pytest.mark.unit
class TestAnthropicClientInit:
    """Tests for AnthropicClient initialization."""

    def test_init_with_api_key_in_config(self):
        """Test initialization with API key in config."""
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        with patch.dict(os.environ, {}, clear=True):
            with patch("agent.llm.anthropic_client.AsyncAnthropic") as mock_anthropic:
                config = AnthropicConfig(api_key="test-api-key")
                AnthropicClient(config)

                mock_anthropic.assert_called_once_with(
                    api_key="test-api-key",
                    base_url=None,
                    http_client=ANY,
                )

    def test_init_with_env_api_key(self):
        """Test initialization with API key from environment."""
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-api-key"}, clear=True):
            with patch("agent.llm.anthropic_client.AsyncAnthropic") as mock_anthropic:
                config = AnthropicConfig()
                AnthropicClient(config)

                mock_anthropic.assert_called_once_with(
                    api_key="env-api-key",
                    base_url=None,
                    http_client=ANY,
                )

    def test_init_without_api_key_raises(self):
        """Test initialization without API key raises error."""
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        with patch.dict(os.environ, {}, clear=True):
            # Remove ANTHROPIC_API_KEY if it exists
            os.environ.pop("ANTHROPIC_API_KEY", None)

            with pytest.raises(ValueError, match="API key not found"):
                AnthropicClient(AnthropicConfig())

    def test_init_with_env_base_url(self):
        """Test initialization with base URL from environment."""
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        with patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "env-api-key", "ANTHROPIC_BASE_URL": "https://anthropic-proxy.example.com"},
            clear=True,
        ):
            with patch("agent.llm.anthropic_client.AsyncAnthropic") as mock_anthropic:
                AnthropicClient(AnthropicConfig())

                mock_anthropic.assert_called_once_with(
                    api_key="env-api-key",
                    base_url="https://anthropic-proxy.example.com",
                    http_client=ANY,
                )


@pytest.mark.unit
class TestAnthropicClientSingleton:
    """Tests for singleton pattern."""

    def test_get_anthropic_client_singleton(self):
        """Test get_anthropic_client returns singleton."""
        from agent.llm.anthropic_client import (
            get_anthropic_client,
            reset_anthropic_client,
        )

        with patch("agent.llm.anthropic_client.AsyncAnthropic"):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                reset_anthropic_client()

                client1 = get_anthropic_client()
                client2 = get_anthropic_client()

                assert client1 is client2

                reset_anthropic_client()

    def test_reset_anthropic_client(self):
        """Test reset_anthropic_client clears singleton."""
        from agent.llm.anthropic_client import (
            get_anthropic_client,
            reset_anthropic_client,
        )

        with patch("agent.llm.anthropic_client.AsyncAnthropic"):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                reset_anthropic_client()

                client1 = get_anthropic_client()
                reset_anthropic_client()
                client2 = get_anthropic_client()

                assert client1 is not client2

                reset_anthropic_client()

    def test_get_anthropic_client_defaults_to_zai_primary_with_env_fallback(self):
        """Agent singleton should prefer Z.ai and keep the original base URL as fallback."""
        from agent.llm.anthropic_client import (
            DEFAULT_AGENT_PRIMARY_BASE_URL,
            get_anthropic_client,
            reset_anthropic_client,
        )

        seen_calls: list[tuple[str | None, str | None]] = []

        def _fake_async_anthropic(*, api_key=None, base_url=None, **kwargs):
            seen_calls.append((api_key, base_url))
            return _FakeAnthropic([_FakeStreamCM(stream=_FakeStream(events=[], final_message=None))])

        with patch("agent.llm.anthropic_client.AsyncAnthropic", _fake_async_anthropic):
            with patch.dict(
                os.environ,
                {
                    "ANTHROPIC_API_KEY": "test-key",
                    "ANTHROPIC_BASE_URL": "https://original-gateway.example.com/anthropic",
                },
                clear=True,
            ):
                reset_anthropic_client()
                client = get_anthropic_client()

        assert seen_calls == [("test-key", DEFAULT_AGENT_PRIMARY_BASE_URL)]
        assert client.config.base_url == DEFAULT_AGENT_PRIMARY_BASE_URL
        assert client.config.fallback_base_url == "https://original-gateway.example.com/anthropic"
        reset_anthropic_client()


@pytest.mark.unit
class TestAnthropicClientStreamMessageRetry:
    @pytest.mark.asyncio
    async def test_stream_message_retries_on_early_readtimeout(self, monkeypatch: pytest.MonkeyPatch):
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        monkeypatch.setenv("AGENT_LLM_STREAM_MAX_RETRIES", "1")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_BASE_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_JITTER_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_ATTEMPT_ELAPSED_S", "0")

        final_message = type(
            "_Final",
            (),
            {
                "stop_reason": "end_turn",
                "usage": type("_Usage", (), {"input_tokens": 1, "output_tokens": 2})(),
            },
        )()

        cms = [
            _FakeStreamCM(exc=httpx.ReadTimeout("", request=httpx.Request("POST", "https://example.com"))),
            _FakeStreamCM(stream=_FakeStream(events=[], final_message=final_message)),
        ]
        fake_client = _FakeAnthropic(cms)

        def _fake_async_anthropic(*, api_key=None, base_url=None, **kwargs):
            return fake_client

        with patch("agent.llm.anthropic_client.AsyncAnthropic", _fake_async_anthropic):
            client = AnthropicClient(AnthropicConfig(api_key="test-key"))
            seen = [event.type.value async for event in client.stream_message(messages=[{"role": "user", "content": "hi"}])]

        assert fake_client.messages.calls == 2
        assert seen == ["message_start", "message_end"]

    @pytest.mark.asyncio
    async def test_stream_message_does_not_retry_after_any_streamed_content(self, monkeypatch: pytest.MonkeyPatch):
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig, StreamEvent, StreamEventType

        monkeypatch.setenv("AGENT_LLM_STREAM_MAX_RETRIES", "3")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_BASE_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_JITTER_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_ATTEMPT_ELAPSED_S", "0")

        cms = [
            _FakeStreamCM(
                stream=_FakeStream(
                    events=[object()],
                    raise_after=httpx.ReadTimeout("", request=httpx.Request("POST", "https://example.com")),
                    final_message=None,
                )
            ),
            _FakeStreamCM(stream=_FakeStream(events=[], final_message=None)),
        ]
        fake_client = _FakeAnthropic(cms)

        def _fake_async_anthropic(*, api_key=None, base_url=None, **kwargs):
            return fake_client

        async def _fake_process_stream_event(self, raw_event, current_tool_use):
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "hi"})

        with patch("agent.llm.anthropic_client.AsyncAnthropic", _fake_async_anthropic):
            client = AnthropicClient(AnthropicConfig(api_key="test-key"))
            with patch.object(AnthropicClient, "_process_stream_event", _fake_process_stream_event):
                seen = [event.type.value async for event in client.stream_message(messages=[{"role": "user", "content": "hi"}])]

        assert fake_client.messages.calls == 1
        assert seen == ["message_start", "text", "error"]

    @pytest.mark.asyncio
    async def test_stream_message_retries_on_transient_429_provider_code(self, monkeypatch: pytest.MonkeyPatch):
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        monkeypatch.setenv("AGENT_LLM_STREAM_MAX_RETRIES", "2")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_BASE_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_JITTER_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_ATTEMPT_ELAPSED_S", "0")

        final_message = type(
            "_Final",
            (),
            {
                "stop_reason": "end_turn",
                "usage": type("_Usage", (), {"input_tokens": 1, "output_tokens": 2})(),
            },
        )()

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(429, request=request)
        exc = RateLimitError(
            "rate limited",
            response=response,
            body={"error": {"code": "1302", "message": "您的账户已达到速率限制，请您控制请求频率"}},
        )

        cms = [
            _FakeStreamCM(exc=exc),
            _FakeStreamCM(stream=_FakeStream(events=[], final_message=final_message)),
        ]
        fake_client = _FakeAnthropic(cms)

        def _fake_async_anthropic(*, api_key=None, base_url=None, **kwargs):
            return fake_client

        with patch("agent.llm.anthropic_client.AsyncAnthropic", _fake_async_anthropic):
            client = AnthropicClient(AnthropicConfig(api_key="test-key"))
            seen = [event.type.value async for event in client.stream_message(messages=[{"role": "user", "content": "hi"}])]

        assert fake_client.messages.calls == 2
        assert seen == ["message_start", "message_end"]

    @pytest.mark.asyncio
    async def test_stream_message_retries_on_transient_provider_code_with_http_200(self, monkeypatch: pytest.MonkeyPatch):
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        monkeypatch.setenv("AGENT_LLM_STREAM_MAX_RETRIES", "2")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_BASE_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_JITTER_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_ATTEMPT_ELAPSED_S", "0")

        final_message = type(
            "_Final",
            (),
            {
                "stop_reason": "end_turn",
                "usage": type("_Usage", (), {"input_tokens": 1, "output_tokens": 2})(),
            },
        )()

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(200, request=request)
        exc = APIStatusError(
            "{'error': {'code': '1305', 'message': '该模型当前访问量过大，请您稍后再试'}}",
            response=response,
            body={"error": {"code": "1305", "message": "该模型当前访问量过大，请您稍后再试"}},
        )

        cms = [
            _FakeStreamCM(exc=exc),
            _FakeStreamCM(stream=_FakeStream(events=[], final_message=final_message)),
        ]
        fake_client = _FakeAnthropic(cms)

        def _fake_async_anthropic(*, api_key=None, base_url=None, **kwargs):
            return fake_client

        with patch("agent.llm.anthropic_client.AsyncAnthropic", _fake_async_anthropic):
            client = AnthropicClient(AnthropicConfig(api_key="test-key"))
            seen = [event.type.value async for event in client.stream_message(messages=[{"role": "user", "content": "hi"}])]

        assert fake_client.messages.calls == 2
        assert seen == ["message_start", "message_end"]

    @pytest.mark.asyncio
    async def test_stream_message_retries_on_provider_network_error_code_1234(self, monkeypatch: pytest.MonkeyPatch):
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        monkeypatch.setenv("AGENT_LLM_STREAM_MAX_RETRIES", "2")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_BASE_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_JITTER_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_ATTEMPT_ELAPSED_S", "0")

        final_message = type(
            "_Final",
            (),
            {
                "stop_reason": "end_turn",
                "usage": type("_Usage", (), {"input_tokens": 1, "output_tokens": 2})(),
            },
        )()

        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(200, request=request)
        exc = APIStatusError(
            "{'error': {'code': '1234', 'message': 'Network error, error id: abc, please contact customer service'}}",
            response=response,
            body={"error": {"code": "1234", "message": "Network error, error id: abc, please contact customer service"}},
        )

        cms = [
            _FakeStreamCM(exc=exc),
            _FakeStreamCM(stream=_FakeStream(events=[], final_message=final_message)),
        ]
        fake_client = _FakeAnthropic(cms)

        def _fake_async_anthropic(*, api_key=None, base_url=None, **kwargs):
            return fake_client

        with patch("agent.llm.anthropic_client.AsyncAnthropic", _fake_async_anthropic):
            client = AnthropicClient(AnthropicConfig(api_key="test-key"))
            seen = [event.type.value async for event in client.stream_message(messages=[{"role": "user", "content": "hi"}])]

        assert fake_client.messages.calls == 2
        assert seen == ["message_start", "message_end"]

    @pytest.mark.asyncio
    async def test_stream_message_fails_over_to_fallback_base_url_on_connection_error(self, monkeypatch: pytest.MonkeyPatch):
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig

        monkeypatch.setenv("AGENT_LLM_STREAM_MAX_RETRIES", "2")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_BASE_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_JITTER_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_DELAY_S", "0")
        monkeypatch.setenv("AGENT_LLM_STREAM_RETRY_MAX_ATTEMPT_ELAPSED_S", "0")

        final_message = type(
            "_Final",
            (),
            {
                "stop_reason": "end_turn",
                "usage": type("_Usage", (), {"input_tokens": 1, "output_tokens": 2})(),
            },
        )()

        primary_client = _FakeAnthropic([
            _FakeStreamCM(exc=httpx.ConnectError("boom", request=httpx.Request("POST", "https://api.z.ai/api/anthropic"))),
        ])
        fallback_client = _FakeAnthropic([
            _FakeStreamCM(stream=_FakeStream(events=[], final_message=final_message)),
        ])
        seen_base_urls: list[str | None] = []

        def _fake_async_anthropic(*, api_key=None, base_url=None, **kwargs):
            seen_base_urls.append(base_url)
            if base_url == "https://api.z.ai/api/anthropic":
                return primary_client
            if base_url == "https://original-gateway.example.com/anthropic":
                return fallback_client
            raise AssertionError(f"Unexpected base_url {base_url}")

        with patch("agent.llm.anthropic_client.AsyncAnthropic", _fake_async_anthropic):
            client = AnthropicClient(
                AnthropicConfig(
                    api_key="test-key",
                    base_url="https://api.z.ai/api/anthropic",
                    fallback_base_url="https://original-gateway.example.com/anthropic",
                )
            )
            seen = [event.type.value async for event in client.stream_message(messages=[{"role": "user", "content": "hi"}])]

        assert seen_base_urls == [
            "https://api.z.ai/api/anthropic",
            "https://original-gateway.example.com/anthropic",
        ]
        assert primary_client.messages.calls == 1
        assert fallback_client.messages.calls == 1
        assert seen == ["message_start", "message_end"]

    @pytest.mark.asyncio
    async def test_stream_message_emits_tool_stop_only_once(self, monkeypatch: pytest.MonkeyPatch):
        from agent.llm.anthropic_client import AnthropicClient, AnthropicConfig, StreamEvent, StreamEventType

        monkeypatch.setenv("AGENT_LLM_STREAM_MAX_RETRIES", "0")

        final_message = type(
            "_Final",
            (),
            {
                "stop_reason": "end_turn",
                "usage": type("_Usage", (), {"input_tokens": 1, "output_tokens": 2})(),
            },
        )()

        cms = [
            _FakeStreamCM(stream=_FakeStream(events=[object(), object()], final_message=final_message)),
        ]
        fake_client = _FakeAnthropic(cms)

        def _fake_async_anthropic(*, api_key=None, base_url=None, **kwargs):
            return fake_client

        async def _fake_process_stream_event(self, raw_event, current_tool_use):
            # First raw event: start + stop.
            if raw_event is self._raw_events[0]:  # type: ignore[attr-defined]
                yield StreamEvent(type=StreamEventType.TOOL_USE, data={"id": "t1", "name": "tool", "status": "start"})
                yield StreamEvent(type=StreamEventType.TOOL_USE, data={"id": "t1", "name": "tool", "status": "stop"})
                return

            # Second raw event: would incorrectly emit stop again if current_tool_use wasn't cleared.
            if current_tool_use is not None:
                yield StreamEvent(type=StreamEventType.TOOL_USE, data={"id": "t1", "name": "tool", "status": "stop"})

        with patch("agent.llm.anthropic_client.AsyncAnthropic", _fake_async_anthropic):
            client = AnthropicClient(AnthropicConfig(api_key="test-key"))
            # Inject stable identity for the two raw events so our patched processor can branch.
            client._raw_events = cms[0]._stream._events  # type: ignore[attr-defined]
            with patch.object(AnthropicClient, "_process_stream_event", _fake_process_stream_event):
                seen = [event.type.value async for event in client.stream_message(messages=[{"role": "user", "content": "hi"}])]

        assert seen.count("tool_use") == 2  # start + stop only
