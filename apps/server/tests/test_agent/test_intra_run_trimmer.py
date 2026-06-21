"""Tests for the intra-run tool-output trimmer (call_model_input_filter)."""

from __future__ import annotations

from typing import Any

import pytest
from agents.run_config import CallModelData, ModelInputData

from agent.core.metrics import (
    TOOL_OUTPUT_TRIMMED_CHARS,
    TOOL_OUTPUT_TRIMMED_TOTAL,
    get_metrics_collector,
    reset_metrics_collector,
)
from agent.openai_agents.intra_run_trimmer import IntraRunToolOutputTrimmer

BIG = "X" * 5000  # well above the default 2000-char trim threshold
SMALL = "ok"


def _fc(call_id: str, name: str) -> dict[str, Any]:
    return {"type": "function_call", "call_id": call_id, "name": name, "arguments": "{}"}


def _fco(call_id: str, output: str) -> dict[str, Any]:
    return {"type": "function_call_output", "call_id": call_id, "output": output}


def _run(trimmer: IntraRunToolOutputTrimmer, items: list[dict[str, Any]]) -> list[Any]:
    md = ModelInputData(input=[dict(it) for it in items], instructions=None)
    data = CallModelData(model_data=md, agent=None, context=None)
    return trimmer(data).input


def _outputs(items: list[Any]) -> list[str]:
    return [it["output"] for it in items if it.get("type") == "function_call_output"]


def test_keeps_recent_trims_stale():
    """With 3 big retrieval outputs and keep_recent=2, only the oldest is previewed."""
    items = [
        {"role": "user", "content": "do it"},
        _fc("c1", "hybrid_search"), _fco("c1", BIG),
        _fc("c2", "hybrid_search"), _fco("c2", BIG),
        _fc("c3", "query_files"), _fco("c3", BIG),
    ]
    out = _run(IntraRunToolOutputTrimmer(keep_recent=2), items)
    outs = _outputs(out)
    assert outs[0].startswith("[Trimmed stale tool output")  # c1 previewed
    assert outs[1] == BIG  # c2 kept full
    assert outs[2] == BIG  # c3 kept full


def test_conservative_below_keep_recent():
    """With <= keep_recent trimmable outputs, nothing is trimmed."""
    items = [
        {"role": "user", "content": "do it"},
        _fc("c1", "hybrid_search"), _fco("c1", BIG),
        _fc("c2", "query_files"), _fco("c2", BIG),
    ]
    out = _run(IntraRunToolOutputTrimmer(keep_recent=2), items)
    assert _outputs(out) == [BIG, BIG]


def test_small_outputs_untouched():
    """Outputs below max_output_chars are never previewed, even if stale."""
    items = [
        _fc("c1", "hybrid_search"), _fco("c1", SMALL),
        _fc("c2", "hybrid_search"), _fco("c2", SMALL),
        _fc("c3", "hybrid_search"), _fco("c3", SMALL),
    ]
    out = _run(IntraRunToolOutputTrimmer(keep_recent=1), items)
    assert _outputs(out) == [SMALL, SMALL, SMALL]


def test_excludes_non_allowlisted_tools():
    """Control-flow / non-retrieval tool outputs are never trimmed."""
    items = [
        _fc("c1", "handoff_to_agent"), _fco("c1", BIG),
        _fc("c2", "request_clarification"), _fco("c2", BIG),
        _fc("c3", "create_file"), _fco("c3", BIG),
    ]
    out = _run(IntraRunToolOutputTrimmer(keep_recent=1), items)
    assert _outputs(out) == [BIG, BIG, BIG]


def test_only_stale_allowlisted_trimmed_mixed():
    """A mix: only the stale allowlisted output is previewed; others untouched."""
    items = [
        _fc("c1", "hybrid_search"), _fco("c1", BIG),   # stale allowlisted -> trimmed
        _fc("c2", "handoff_to_agent"), _fco("c2", BIG),  # excluded -> full
        _fc("c3", "query_files"), _fco("c3", BIG),     # recent allowlisted -> full
    ]
    out = _run(IntraRunToolOutputTrimmer(keep_recent=1), items)
    outs = _outputs(out)
    assert outs[0].startswith("[Trimmed stale tool output")
    assert outs[1] == BIG
    assert outs[2] == BIG


def test_empty_input_returns_unchanged():
    md = ModelInputData(input=[], instructions=None)
    data = CallModelData(model_data=md, agent=None, context=None)
    assert IntraRunToolOutputTrimmer()(data).input == []


def test_does_not_mutate_original_items():
    original = [
        _fc("c1", "hybrid_search"), _fco("c1", BIG),
        _fc("c2", "hybrid_search"), _fco("c2", BIG),
        _fc("c3", "hybrid_search"), _fco("c3", BIG),
    ]
    snapshot = [dict(it) for it in original]
    md = ModelInputData(input=original, instructions=None)
    IntraRunToolOutputTrimmer(keep_recent=2)(CallModelData(model_data=md, agent=None, context=None))
    assert original == snapshot  # filter must not mutate the caller's items


def test_metrics_recorded_on_trim():
    reset_metrics_collector()
    items = [
        _fc("c1", "hybrid_search"), _fco("c1", BIG),
        _fc("c2", "hybrid_search"), _fco("c2", BIG),
        _fc("c3", "hybrid_search"), _fco("c3", BIG),
    ]
    _run(IntraRunToolOutputTrimmer(keep_recent=2), items)
    counters = get_metrics_collector().get_all_metrics()["counters"]
    assert counters[TOOL_OUTPUT_TRIMMED_TOTAL]["value"] == 1
    assert counters[TOOL_OUTPUT_TRIMMED_CHARS]["value"] > 0


def test_no_metrics_when_nothing_trimmed():
    reset_metrics_collector()
    items = [_fc("c1", "hybrid_search"), _fco("c1", BIG)]
    _run(IntraRunToolOutputTrimmer(keep_recent=2), items)
    counters = get_metrics_collector().get_all_metrics()["counters"]
    assert TOOL_OUTPUT_TRIMMED_TOTAL not in counters


@pytest.mark.parametrize(
    "kwargs",
    [
        {"keep_recent": -1},
        {"max_output_chars": 0},
        {"preview_chars": -1},
    ],
)
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        IntraRunToolOutputTrimmer(**kwargs)
