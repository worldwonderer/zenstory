import pytest
from httpx import AsyncClient

from tests.real_llm.sse_utils import collect_sse_events, event_names, iter_sse_events


@pytest.mark.integration
@pytest.mark.real_llm
async def test_stream_real_llm_event_lifecycle(
    client: AsyncClient,
    real_auth_context: dict,
    require_anthropic_key,
):
    context = real_auth_context
    project = context["project"]

    response = await client.post(
        "/api/v1/agent/stream",
        json={
            "project_id": str(project.id),
            "message": "请只回复一句中文短句：测试通过。",
            "metadata": {
                "current_file_type": "draft",
            },
        },
        headers=context["headers"],
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = await collect_sse_events(response, timeout_seconds=300.0)
    names = event_names(events)

    assert names, "SSE returned no events"
    assert "session_started" in names
    assert any(
        name in {"done", "error", "workflow_stopped", "workflow_complete"}
        for name in names
    ), f"No terminal event found in SSE stream: {names[-20:]}"
    if "content_start" in names:
        assert "content_end" in names


@pytest.mark.integration
@pytest.mark.real_llm
async def test_stream_real_llm_tool_roundtrip(
    client: AsyncClient,
    real_auth_context: dict,
    require_anthropic_key,
):
    context = real_auth_context
    project = context["project"]

    # Real LLM outputs are non-deterministic; verify tool event roundtrip contract only.
    prompts = [
        (
            "你必须调用 query_files 工具读取当前项目文件列表，"
            "然后再给一句简短总结。不要只做纯文字回答。"
        ),
        (
            "STRICT INSTRUCTION: You must call query_files tool first, "
            "then provide one-sentence summary."
        ),
    ]

    success = False
    last_names: list[str] = []

    for prompt in prompts:
        response = await client.post(
            "/api/v1/agent/stream",
            json={
                "project_id": str(project.id),
                "message": prompt,
            },
            headers=context["headers"],
        )
        assert response.status_code == 200

        events = []
        tool_result_seen = False

        async for evt in iter_sse_events(response, timeout_seconds=240.0):
            events.append(evt)
            if evt.event == "tool_result":
                tool_result_seen = True

            if tool_result_seen:
                break
            if evt.event in {"done", "error", "workflow_stopped", "workflow_complete"}:
                break

        names = event_names(events)
        last_names = names

        if tool_result_seen:
            success = True
            break

    assert success, (
        "Expected at least one tool_result event in real LLM stream. "
        f"Last event sequence: {last_names}"
    )
