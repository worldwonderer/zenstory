"""
Centralized runtime configuration for agent orchestration.

Keeps key workflow limits in one place so prompts, graph logic, and service
entrypoints use the same thresholds and iteration budgets.
"""

import os


def _get_int_env(name: str, default: int, minimum: int = 1) -> int:
    """Read an integer environment variable with safe fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _get_bool_env(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable with safe fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_str_env(
    name: str,
    default: str,
    *,
    allowed: set[str] | None = None,
) -> str:
    """Read a string environment variable with normalization + allowlist."""
    raw = os.getenv(name)
    value = default if raw is None else raw.strip()

    normalized = value.lower()
    if allowed is not None and normalized not in allowed:
        return default
    return normalized


# Iteration budgets. These caps are NOT for cost control (DeepSeek is cheap) — they only
# exist as a runaway-loop safety net so a stuck tool-loop or handoff ping-pong can't hang a
# request forever. They are therefore set generously so they never constrain a real task,
# while still bounding pathological loops. All remain env-overridable.

# Total request-level iteration budget (legacy compatibility constant)
AGENT_MAX_ITERATIONS = _get_int_env("AGENT_MAX_ITERATIONS", 100)

# Multi-agent collaboration loop budget (writer/planner/reviewer handoffs)
AGENT_COLLABORATION_MAX_ITERATIONS = _get_int_env(
    "AGENT_COLLABORATION_MAX_ITERATIONS",
    30,
)

# Single-agent tool-calling loop budget (SDK max_turns per agent run)
AGENT_TOOL_CALL_MAX_ITERATIONS = _get_int_env(
    "AGENT_TOOL_CALL_MAX_ITERATIONS",
    100,
)

# Max output tokens for the OpenAI Agents SDK Chat Completions calls.
# This is intentionally independent from the tool-turn budget above.
AGENT_OPENAI_AGENTS_MAX_OUTPUT_TOKENS = _get_int_env(
    "AGENT_OPENAI_AGENTS_MAX_OUTPUT_TOKENS",
    64000,
)

# Chat history loading budget (sliding window, newest-first)
AGENT_CHAT_HISTORY_TOKEN_BUDGET = _get_int_env(
    "AGENT_CHAT_HISTORY_TOKEN_BUDGET",
    6000,
)

# Compaction checkpoint retention per chat session.
# Keeps only the latest N checkpoints in agent_artifact_ledger.
AGENT_COMPACTION_CHECKPOINT_RETENTION = _get_int_env(
    "AGENT_COMPACTION_CHECKPOINT_RETENTION",
    20,
)

# Content length threshold for auto-handoff to quality reviewer
AGENT_AUTO_REVIEW_THRESHOLD_CHARS = _get_int_env(
    "AGENT_AUTO_REVIEW_THRESHOLD_CHARS",
    500,
)

# Router strategy used by writing graph:
# - llm: call router_node (extra LLM round-trip)
# - off: always start from writer (no routing)
AGENT_ROUTER_STRATEGY = _get_str_env(
    "AGENT_ROUTER_STRATEGY",
    "llm",
    allowed={"llm", "off"},
)

# Whether writing_graph.py should auto-trigger quality reviewer purely based on
# writer output length. Default is **True** for backward compatibility (the
# previous graph behavior always auto-triggered), but can be disabled to reduce
# extra agent round-trips when the prompts already handle explicit handoffs.
AGENT_ENABLE_GRAPH_AUTO_REVIEW = _get_bool_env(
    "AGENT_ENABLE_GRAPH_AUTO_REVIEW",
    True,
)
