import pytest
from httpx import AsyncClient

from tests.real_llm.sse_utils import collect_sse_events, event_names


@pytest.mark.integration
@pytest.mark.real_llm
async def test_agent_api_chat_real_llm_stream(
    client: AsyncClient,
    real_agent_api_key: dict,
    require_anthropic_key,
):
    project = real_agent_api_key["project"]
    plain_key = real_agent_api_key["plain_key"]

    response = await client.post(
        "/api/v1/agent/chat",
        headers={"X-Agent-API-Key": plain_key},
        json={
            "project_id": str(project.id),
            "message": "Give me a concise writing suggestion.",
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = await collect_sse_events(response, timeout_seconds=300.0)
    names = event_names(events)

    assert names, "SSE returned no events for /api/v1/agent/chat"
    assert "session_started" in names
    assert any(
        name in {"done", "error", "workflow_stopped", "workflow_complete"}
        for name in names
    ), f"No terminal event found in SSE stream: {names[-20:]}"
