import asyncio
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedSSEEvent:
    event: str
    data: dict[str, Any]
    raw_data: str


async def iter_sse_events(response, timeout_seconds: float = 300.0):
    current_event = ""
    try:
        async with asyncio.timeout(timeout_seconds):
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    continue
                if not line.startswith("data:"):
                    continue

                raw_data = line.split(":", 1)[1].strip()
                payload: dict[str, Any]
                try:
                    decoded = json.loads(raw_data) if raw_data else {}
                    payload = decoded if isinstance(decoded, dict) else {"value": decoded}
                except json.JSONDecodeError:
                    payload = {"_raw": raw_data}

                yield ParsedSSEEvent(
                    event=current_event,
                    data=payload,
                    raw_data=raw_data,
                )
    except TimeoutError as exc:
        raise AssertionError(f"SSE stream timed out after {timeout_seconds}s") from exc


async def collect_sse_events(
    response,
    *,
    stop_events: set[str] | None = None,
    max_events: int = 5000,
    timeout_seconds: float = 300.0,
) -> list[ParsedSSEEvent]:
    terminal = stop_events or {"done", "error", "workflow_stopped", "workflow_complete"}
    events: list[ParsedSSEEvent] = []
    async for event in iter_sse_events(response, timeout_seconds=timeout_seconds):
        events.append(event)
        if event.event in terminal or len(events) >= max_events:
            break
    return events


def event_names(events: list[ParsedSSEEvent]) -> list[str]:
    return [event.event for event in events]
