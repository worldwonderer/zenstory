from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

from agent.core.llm_client import LLMClient


class _NestedPayload(BaseModel):
    flag: bool = Field(default=True, description="nested flag")


class _StructuredPayload(BaseModel):
    name: str = Field(description="payload name")
    nested: _NestedPayload


class _DummyAsyncCompletions:
    def __init__(self, responses: list[object]):
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _DummyAsyncClient:
    def __init__(self, responses: list[object]):
        self.chat = SimpleNamespace(completions=_DummyAsyncCompletions(responses))


class _DummySyncCompletions:
    def __init__(self, response_or_stream):
        self.response_or_stream = response_or_stream
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response_or_stream


class _DummySyncClient:
    def __init__(self, response_or_stream):
        self.chat = SimpleNamespace(completions=_DummySyncCompletions(response_or_stream))


def _tool_call(tool_id: str, name: str, arguments: str):
    return SimpleNamespace(
        id=tool_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _response(*, content: str = "", tool_calls: list[object] | None = None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))],
        usage=None,
    )


@pytest.mark.unit
def test_build_json_schema_strips_titles_defaults_and_sets_additional_properties():
    client = LLMClient(api_key="test-key", base_url="https://example.invalid")

    schema = client._build_json_schema(_StructuredPayload)
    payload_schema = schema["json_schema"]["schema"]

    assert schema["json_schema"]["name"] == "_StructuredPayload"
    assert schema["json_schema"]["strict"] is True
    assert payload_schema["type"] == "object"
    assert payload_schema["additionalProperties"] is False
    assert "title" not in payload_schema
    assert "description" not in payload_schema["properties"]["name"]
    assert payload_schema["$defs"]["_NestedPayload"]["additionalProperties"] is False
    assert "default" not in payload_schema["$defs"]["_NestedPayload"]["properties"]["flag"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acomplete_disables_thinking_via_extra_body():
    client = LLMClient(api_key="test-key", base_url="https://example.invalid")
    dummy_client = _DummyAsyncClient([_response(content="done")])
    client._async_client = dummy_client

    result = await client.acomplete([{"role": "user", "content": "hi"}], thinking_enabled=False)

    assert result == "done"
    assert dummy_client.chat.completions.calls[0].get("extra_body") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acomplete_with_tools_records_tool_errors_and_stops_on_max_iterations():
    client = LLMClient(api_key="test-key", base_url="https://example.invalid")
    tool_call = _tool_call("call-1", "explode", '{"value": 1}')
    dummy_client = _DummyAsyncClient([
        _response(tool_calls=[tool_call]),
        _response(tool_calls=[tool_call]),
    ])
    client._async_client = dummy_client

    def tool_handler(name: str, args: dict[str, object]):
        raise RuntimeError(f"{name} failed with {args['value']}")

    result = await client.acomplete_with_tools(
        messages=[{"role": "user", "content": "run tool"}],
        tools=[{"type": "function", "function": {"name": "explode"}}],
        tool_handler=tool_handler,
        max_iterations=2,
    )

    assert result["type"] == "tool_calls"
    assert result["error"] == "Max iterations (2) reached"
    assert len(result["tool_calls"]) == 2
    assert len(result["tool_results"]) == 2
    assert result["tool_results"][0]["result"]["status"] == "error"
    assert "explode failed with 1" in result["tool_results"][0]["result"]["error"]


@pytest.mark.unit
def test_complete_uses_default_sampling_parameters_and_returns_content():
    client = LLMClient(api_key="test-key", base_url="https://example.invalid")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="sync-done"))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
    )
    dummy_client = _DummySyncClient(response)
    client._sync_client = dummy_client

    result = client.complete([{"role": "user", "content": "hi"}], max_tokens=123)

    assert result == "sync-done"
    call = dummy_client.chat.completions.calls[0]
    assert call["temperature"] == client.DEFAULT_TEMPERATURE
    assert call["top_p"] == client.DEFAULT_TOP_P
    assert call["max_tokens"] == 123


@pytest.mark.unit
def test_complete_stream_yields_only_non_empty_chunks():
    client = LLMClient(api_key="test-key", base_url="https://example.invalid")
    stream = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="he"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="llo"))]),
    ]
    dummy_client = _DummySyncClient(stream)
    client._sync_client = dummy_client

    chunks = list(client.complete_stream([{"role": "user", "content": "hi"}]))

    assert chunks == ["he", "llo"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acomplete_structured_validates_response_model():
    client = LLMClient(api_key="test-key", base_url="https://example.invalid")
    dummy_client = _DummyAsyncClient([
        _response(content=json.dumps({"name": "payload", "nested": {"flag": False}})),
    ])
    client._async_client = dummy_client

    result = await client.acomplete_structured(
        [{"role": "user", "content": "give structured"}],
        _StructuredPayload,
    )

    assert result.name == "payload"
    assert result.nested.flag is False
