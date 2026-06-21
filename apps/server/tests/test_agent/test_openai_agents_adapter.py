"""Tests for the openai-agents-python writing-agent adapter."""

import asyncio
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_metrics_and_model_cache():
    from agent.core.metrics import reset_metrics_collector
    from agent.openai_agents.model import reset_deepseek_sdk_cache

    reset_metrics_collector()
    reset_deepseek_sdk_cache()
    yield
    reset_deepseek_sdk_cache()
    reset_metrics_collector()


@pytest.mark.unit
def test_deepseek_client_requires_deepseek_api_key(monkeypatch):
    from agent.openai_agents.model import get_deepseek_client

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        get_deepseek_client()


@pytest.mark.unit
def test_build_agent_function_tools_uses_registry_names():
    from agent.openai_agents.tools_adapter import build_agent_function_tools
    from agent.tools.registry import get_agent_tools

    tools = build_agent_function_tools("quality_reviewer")

    assert [tool.name for tool in tools] == [tool["name"] for tool in get_agent_tools("quality_reviewer")]
    assert all(tool.strict_json_schema is False for tool in tools)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_invoke_project_tool_returns_mcp_text_and_metrics():
    from agent.core.metrics import TOOL_CALLS_ERRORS, TOOL_CALLS_TOTAL, get_metrics_collector
    from agent.openai_agents.tools_adapter import invoke_project_tool

    async def fake_tool(args):
        return {"content": [{"type": "text", "text": json.dumps({"status": "success", "args": args})}]}

    with patch.dict("agent.openai_agents.tools_adapter.TOOL_FUNCTIONS", {"demo_tool": fake_tool}, clear=True):
        result_text = await invoke_project_tool("demo_tool", '{"x": 1}')

    assert json.loads(result_text) == {"status": "success", "args": {"x": 1}}
    metrics = get_metrics_collector().get_all_metrics()
    assert metrics["counters"][TOOL_CALLS_TOTAL]["value"] == 1
    assert TOOL_CALLS_ERRORS not in metrics["counters"]


@pytest.mark.unit
def test_normalize_messages_for_openai_agents_omits_thinking_blocks():
    from agent.openai_agents.runner import normalize_messages_for_openai_agents

    messages = normalize_messages_for_openai_agents(
        [
            {"role": "user", "content": "写一章"},
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "internal"},
                    {"type": "text", "text": "正文"},
                ],
                "usage": {"input_tokens": 1},
            },
            {"role": "tool", "content": "ignored"},
        ]
    )

    assert messages == [
        {"role": "user", "content": "写一章"},
        {"role": "assistant", "content": "正文"},
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_runner_maps_sdk_text_tool_handoff_and_message_end():
    from agent.core.workflow_events import StreamEventType
    from agent.openai_agents.runner import run_openai_agents_streaming_agent

    result_text = json.dumps(
        {
            "status": "handoff",
            "target_agent": "quality_reviewer",
            "reason": "请审查",
            "context": "已完成初稿",
            "completed": ["初稿"],
        },
        ensure_ascii=False,
    )

    class FakeResult:
        raw_responses = []

        def __init__(self):
            self.cancel_mode = None

        def cancel(self, mode="immediate"):
            self.cancel_mode = mode

        async def stream_events(self):
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="正文"),
            )
            yield SimpleNamespace(
                type="run_item_stream_event",
                name="tool_called",
                item=SimpleNamespace(
                    raw_item={
                        "name": "handoff_to_agent",
                        "call_id": "call-1",
                        "arguments": json.dumps({"target_agent": "quality_reviewer"}, ensure_ascii=False),
                    }
                ),
            )
            yield SimpleNamespace(
                type="run_item_stream_event",
                name="tool_output",
                item=SimpleNamespace(
                    raw_item={"call_id": "call-1"},
                    output=result_text,
                ),
            )

    fake_result = FakeResult()
    state = {"user_message": "写一章", "messages": [], "system_prompt": "base"}

    with (
        patch("agent.openai_agents.runner._build_agent", return_value=object()),
        patch("agents.Runner.run_streamed", return_value=fake_result) as mock_run,
    ):
        events = [
            event async for event in run_openai_agents_streaming_agent(
                state=state,
                agent_type="writer",
                system_prompt="system",
            )
        ]

    assert mock_run.call_args.kwargs["max_turns"] > 0
    assert fake_result.cancel_mode == "after_turn"
    assert [event.type for event in events] == [
        StreamEventType.MESSAGE_START,
        StreamEventType.TEXT,
        StreamEventType.TOOL_USE,
        StreamEventType.TOOL_RESULT,
        StreamEventType.HANDOFF,
        StreamEventType.MESSAGE_END,
    ]
    assert events[1].data["text"] == "正文"
    assert events[2].data["name"] == "handoff_to_agent"
    assert events[4].data["handoff_packet"]["completed"] == ["初稿"]
    assert state["messages"][-2]["role"] == "assistant"
    assert state["messages"][-2]["content"][0]["type"] == "text"
    assert state["messages"][-2]["content"][0]["text"] == "正文"


def _free_local_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_runner_streams_through_openai_compatible_http_endpoint(monkeypatch):
    """Exercise SDK + AsyncOpenAI + SSE wiring without calling an external LLM."""
    from agent.core.workflow_events import StreamEventType
    from agent.openai_agents.model import reset_deepseek_sdk_cache
    from agent.openai_agents.runner import run_openai_agents_streaming_agent

    requests: list[dict] = []
    server_errors: list[str] = []

    class LocalChatCompletionsHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):  # noqa: A002
            return

        def do_POST(self):
            try:
                request_length = int(self.headers.get("content-length") or "0")
                body = json.loads(self.rfile.read(request_length) or b"{}")
                requests.append(body)

                if self.path != "/chat/completions":
                    raise AssertionError(f"unexpected path: {self.path}")
                if body.get("model") != "deepseek-v4-flash":
                    raise AssertionError(f"unexpected model: {body.get('model')}")
                if body.get("stream") is not True:
                    raise AssertionError("expected streaming request")

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

                chunks = [
                    {
                        "id": "chatcmpl-local",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": "deepseek-v4-flash",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": ""},
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-local",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": "deepseek-v4-flash",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": "本地"},
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-local",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": "deepseek-v4-flash",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": "smoke"},
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-local",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": "deepseek-v4-flash",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 3,
                            "completion_tokens": 2,
                            "total_tokens": 5,
                        },
                    },
                ]
                for chunk in chunks:
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception as exc:  # pragma: no cover - surfaced via assertion below
                server_errors.append(f"{type(exc).__name__}: {exc}")
                self.send_response(500)
                self.end_headers()

    port = _free_local_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), LocalChatCompletionsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-local-test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", f"http://127.0.0.1:{port}")
    reset_deepseek_sdk_cache()

    state = {"user_message": "请输出 smoke", "messages": [], "system_prompt": "base"}
    try:
        events = [
            event async for event in run_openai_agents_streaming_agent(
                state=state,
                agent_type="writer",
                system_prompt="你是测试助手",
            )
        ]
    finally:
        server.shutdown()
        server.server_close()
        await asyncio.to_thread(thread.join, 1)
        reset_deepseek_sdk_cache()

    assert server_errors == []
    assert requests, "local OpenAI-compatible endpoint was not called"
    assert requests[0]["model"] == "deepseek-v4-flash"
    assert [event.type for event in events] == [
        StreamEventType.MESSAGE_START,
        StreamEventType.TEXT,
        StreamEventType.TEXT,
        StreamEventType.MESSAGE_END,
    ]
    assert events[0].data == {"model": "deepseek-v4-flash", "agent_type": "writer"}
    assert "".join(event.data.get("text", "") for event in events) == "本地smoke"
    assert state["messages"][-1]["content"][0]["text"] == "本地smoke"


@pytest.mark.unit
def test_normalize_omits_tool_use_and_tool_result_blocks():
    """Replayed history must not leak raw tool JSON as prose/user messages (review #1)."""
    from agent.openai_agents.runner import normalize_messages_for_openai_agents

    messages = normalize_messages_for_openai_agents(
        [
            {"role": "user", "content": "写第一章"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "我来创建章节文件。"},
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "create_file",
                        "input": {"title": "第一章", "content": "secret"},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_1", "content": '{"id":"f1"}'},
                ],
            },
        ]
    )

    # Only the user request and the assistant's prose survive; tool calls/results are dropped.
    assert messages == [
        {"role": "user", "content": "写第一章"},
        {"role": "assistant", "content": "我来创建章节文件。"},
    ]
    blob = str(messages)
    assert "create_file" not in blob and "secret" not in blob
    assert "工具调用" not in blob and "工具结果" not in blob


def _called(name, call_id):
    return SimpleNamespace(
        type="run_item_stream_event",
        name="tool_called",
        item=SimpleNamespace(
            raw_item={"name": name, "call_id": call_id, "arguments": "{}"}
        ),
    )


def _output(call_id, text="ok"):
    return SimpleNamespace(
        type="run_item_stream_event",
        name="tool_output",
        item=SimpleNamespace(raw_item={"call_id": call_id}, output=text),
    )


async def test_runner_wires_intra_run_trimmer_into_run_config():
    """The intra-run tool-output trimmer is attached as the model-input filter."""
    from agent.openai_agents.intra_run_trimmer import IntraRunToolOutputTrimmer
    from agent.openai_agents.runner import run_openai_agents_streaming_agent

    class FakeResult:
        raw_responses = []

        def cancel(self, mode="immediate"):
            pass

        async def stream_events(self):
            if False:  # empty stream
                yield

    state = {"user_message": "hi", "messages": [], "system_prompt": "base"}
    with (
        patch("agent.openai_agents.runner._build_agent", return_value=object()),
        patch("agents.Runner.run_streamed", return_value=FakeResult()) as mock_run,
    ):
        _ = [
            event
            async for event in run_openai_agents_streaming_agent(
                state=state, agent_type="writer", system_prompt="system"
            )
        ]

    run_config = mock_run.call_args.kwargs["run_config"]
    assert isinstance(run_config.call_model_input_filter, IntraRunToolOutputTrimmer)
    assert run_config.tool_execution.max_function_tool_concurrency == 1


async def test_readonly_cocall_metric_counts_each_turn_once():
    """Regression lock: the read-only co-call metric counts each turn once, not per output."""
    from agent.core.metrics import (
        TOOL_READONLY_COCALL_TOTAL,
        TOOL_READONLY_TURNS_TOTAL,
        get_metrics_collector,
    )
    from agent.openai_agents.runner import run_openai_agents_streaming_agent

    class FakeResult:
        raw_responses = []

        def cancel(self, mode="immediate"):
            pass

        async def stream_events(self):
            # Turn 1: two read-only calls then their two outputs -> ONE turn, ONE co-call.
            yield _called("hybrid_search", "c1")
            yield _called("query_files", "c2")
            yield _output("c1")
            yield _output("c2")
            # Turn 2: a single non-read-only call -> ONE turn, NO co-call.
            yield _called("create_file", "c3")
            yield _output("c3")

    state = {"user_message": "x", "messages": [], "system_prompt": "base"}
    with (
        patch("agent.openai_agents.runner._build_agent", return_value=object()),
        patch("agents.Runner.run_streamed", return_value=FakeResult()),
    ):
        _ = [
            event
            async for event in run_openai_agents_streaming_agent(
                state=state, agent_type="writer", system_prompt="system"
            )
        ]

    counters = get_metrics_collector().get_all_metrics()["counters"]
    # Pre-fix bug: TURNS counted every tool_output (would be 3). Correct is 2 turns.
    assert counters[TOOL_READONLY_TURNS_TOTAL]["value"] == 2
    assert counters[TOOL_READONLY_COCALL_TOTAL]["value"] == 1
