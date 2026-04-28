"""Tests for request-scoped logging context helpers."""

from __future__ import annotations

import contextvars

from utils.request_context import bind_request_context, get_log_context, reset_request_context


def test_bind_and_reset_request_context_restores_previous_values():
    """reset_request_context should clear values set by bind_request_context."""

    def _run():
        tokens = bind_request_context(request_id="req-1", trace_id="trace-1", agent_run_id="run-1")
        assert get_log_context() == {
            "request_id": "req-1",
            "trace_id": "trace-1",
            "agent_run_id": "run-1",
        }

        reset_request_context(tokens)
        assert get_log_context() == {}

    contextvars.Context().run(_run)


def test_reset_request_context_is_best_effort_across_contexts():
    """Tokens can be created in one Context and reset in another (e.g. streaming close).

    In that case ContextVar.reset raises ValueError. We should not surface that
    error; instead we clear the value in the current context and allow cleanup
    to happen later in the original context.
    """

    def _ctx_a():
        tokens = bind_request_context(request_id="req-2")
        assert get_log_context()["request_id"] == "req-2"

        def _ctx_b():
            # Should not raise ValueError: Token was created in a different Context
            reset_request_context(tokens)
            assert get_log_context() == {}

        contextvars.Context().run(_ctx_b)

        # Still bound in ctx_a since we didn't reset in the correct context.
        assert get_log_context()["request_id"] == "req-2"

        # Now reset in the correct context should work.
        reset_request_context(tokens)
        assert get_log_context() == {}

    contextvars.Context().run(_ctx_a)

