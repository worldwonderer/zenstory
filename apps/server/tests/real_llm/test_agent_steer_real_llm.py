import uuid

import pytest
from httpx import AsyncClient

from tests.real_llm.sse_utils import collect_sse_events, event_names


@pytest.mark.integration
@pytest.mark.real_llm
async def test_steer_real_llm_injected_during_stream(
    client: AsyncClient,
    real_auth_context: dict,
    require_anthropic_key,
):
    context = real_auth_context
    project = context["project"]
    session_id = str(uuid.uuid4())

    steering_message = "请在后续回答中保持一句话总结。"
    steer_response = await client.post(
        "/api/v1/agent/steer",
        json={
            "session_id": session_id,
            "message": steering_message,
        },
        headers=context["headers"],
    )
    assert steer_response.status_code == 200
    steer_json = steer_response.json()
    assert steer_json.get("queued") is True
    assert steer_json.get("message_id")

    stream_response = await client.post(
        "/api/v1/agent/stream",
        json={
            "project_id": str(project.id),
            "session_id": session_id,
            "message": "请给我一句简短的写作建议。",
        },
        headers=context["headers"],
    )
    assert stream_response.status_code == 200
    assert "text/event-stream" in stream_response.headers["content-type"]

    events = await collect_sse_events(stream_response, timeout_seconds=300.0)
    names = event_names(events)
    assert names
    assert "session_started" in names
    assert "steering_received" in names, (
        f"Expected steering_received in events, got: {names[-20:]}"
    )
    assert any(
        name in {"done", "error", "workflow_stopped", "workflow_complete"}
        for name in names
    ), f"No terminal event found in SSE stream: {names[-20:]}"
