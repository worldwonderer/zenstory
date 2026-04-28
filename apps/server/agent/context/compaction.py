"""
Context compaction for long sessions.

Pure functions for compaction logic. When context grows too large,
this module provides functionality to summarize older messages while
keeping recent context intact.

Based on the design pattern from pi-mono/packages/coding-agent/src/core/compaction/compaction.ts
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final, ParamSpec, TypeVar

from agent.utils.token_utils import estimate_message_tokens as estimate_tokens
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)

# Retry configuration
MAX_RETRIES: Final[int] = 3
BASE_DELAY: Final[float] = 1.0  # seconds
MAX_DELAY: Final[float] = 10.0  # seconds

T = TypeVar("T")
P = ParamSpec("P")

# Default context window for Claude models
CONTEXT_WINDOW = 200000


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class CompactionSettings:
    """Settings for context compaction behavior."""

    enabled: bool = True
    reserve_tokens: int = 16384  # Reserved for output
    keep_recent_tokens: int = 20000  # Keep recent messages within this token budget


@dataclass
class CompactionResult:
    """Result of a compaction operation."""

    summary: str
    first_kept_message_id: str
    tokens_before: int
    tokens_after: int
    messages_removed: int


@dataclass
class ContextUsageEstimate:
    """Estimate of context token usage."""

    total_tokens: int
    usage_tokens: int  # From actual LLM usage
    trailing_tokens: int  # Estimated tokens after last usage
    last_usage_index: int | None  # Index of last message with usage info


# ============================================================================
# Token Estimation (imported from agent.utils.token_utils)
# ============================================================================


def _get_assistant_usage(message: dict[str, Any]) -> dict[str, int] | None:
    """
    Get usage info from an assistant message if available.

    Skips aborted and error messages as they don't have valid usage data.

    Args:
        message: Message dict

    Returns:
        Usage dict with input_tokens, output_tokens, etc. or None
    """
    if message.get("role") != "assistant":
        return None

    stop_reason = message.get("stop_reason", "")
    if stop_reason in ("aborted", "error"):
        return None

    usage = message.get("usage")
    if usage and isinstance(usage, dict):
        return usage

    return None


def _calculate_context_tokens(usage: dict[str, int]) -> int:
    """
    Calculate total context tokens from usage.

    Uses the native totalTokens field when available, falls back to
    computing from components.

    Args:
        usage: Usage dict with token counts

    Returns:
        Total token count
    """
    if "total_tokens" in usage:
        return usage["total_tokens"]

    return (
        usage.get("input_tokens", 0)
        + usage.get("output_tokens", 0)
        + usage.get("cache_read_tokens", 0)
        + usage.get("cache_write_tokens", 0)
    )


def estimate_context_tokens(messages: list[dict[str, Any]]) -> ContextUsageEstimate:
    """
    Estimate context tokens from messages, using the last assistant usage when available.

    If there are messages after the last usage, estimate their tokens with estimateTokens.

    Args:
        messages: List of message dicts

    Returns:
        ContextUsageEstimate with token breakdown
    """
    # Find last assistant message with usage
    last_usage_info: tuple[dict[str, int], int] | None = None
    for i in range(len(messages) - 1, -1, -1):
        usage = _get_assistant_usage(messages[i])
        if usage:
            last_usage_info = (usage, i)
            break

    if not last_usage_info:
        # No usage info, estimate all messages
        estimated = 0
        for message in messages:
            estimated += estimate_tokens(message)
        return ContextUsageEstimate(
            total_tokens=estimated,
            usage_tokens=0,
            trailing_tokens=estimated,
            last_usage_index=None,
        )

    usage, last_usage_index = last_usage_info
    usage_tokens = _calculate_context_tokens(usage)

    # Estimate tokens for messages after the last usage
    trailing_tokens = 0
    for i in range(last_usage_index + 1, len(messages)):
        trailing_tokens += estimate_tokens(messages[i])

    return ContextUsageEstimate(
        total_tokens=usage_tokens + trailing_tokens,
        usage_tokens=usage_tokens,
        trailing_tokens=trailing_tokens,
        last_usage_index=last_usage_index,
    )


# ============================================================================
# Compaction Decision
# ============================================================================


def should_compact(
    context_tokens: int,
    context_window: int,
    settings: CompactionSettings,
) -> bool:
    """
    Check if compaction should trigger based on context usage.

    Args:
        context_tokens: Current context token count
        context_window: Maximum context window size
        settings: Compaction settings

    Returns:
        True if compaction should be performed
    """
    if not settings.enabled:
        return False

    return context_tokens > context_window - settings.reserve_tokens


# ============================================================================
# Cut Point Detection
# ============================================================================


def find_cut_point(
    messages: list[dict[str, Any]],
    keep_recent_tokens: int,
) -> tuple[int, bool]:
    """
    Find the cut point in messages that keeps approximately keep_recent_tokens.

    Algorithm: Walk backwards from newest, accumulating estimated message sizes.
    Stop when we've accumulated >= keepRecentTokens.

    Can cut at user OR assistant messages (never tool results).

    Args:
        messages: List of message dicts
        keep_recent_tokens: Token budget for recent messages to keep

    Returns:
        Tuple of (cut_index, is_split_turn):
        - cut_index: Index of first message to keep
        - is_split_turn: Whether this cut splits a turn (not cutting at user message)
    """
    if not messages:
        return 0, False

    # Find valid cut points (user or assistant messages, never tool results)
    valid_cut_indices: list[int] = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        if role in ("user", "assistant"):
            valid_cut_indices.append(i)

    if not valid_cut_indices:
        return 0, False

    # Walk backwards from newest, accumulating estimated message sizes
    accumulated_tokens = 0
    cut_index = valid_cut_indices[0]  # Default: keep from first valid message

    for i in range(len(messages) - 1, -1, -1):
        message_tokens = estimate_tokens(messages[i])
        accumulated_tokens += message_tokens

        # Check if we've exceeded the budget
        if accumulated_tokens >= keep_recent_tokens:
            # Find the closest valid cut point at or after this index
            for cut_idx in valid_cut_indices:
                if cut_idx >= i:
                    cut_index = cut_idx
                    break
            break

    # Determine if this is a split turn (cut at non-user message)
    cut_message = messages[cut_index] if cut_index < len(messages) else None
    is_user_message = cut_message and cut_message.get("role") == "user"
    is_split_turn = not is_user_message

    log_with_context(
        logger,
        20,  # INFO
        "Cut point found",
        cut_index=cut_index,
        is_split_turn=is_split_turn,
        accumulated_tokens=accumulated_tokens,
        keep_recent_tokens=keep_recent_tokens,
    )

    return cut_index, is_split_turn


# ============================================================================
# Summarization
# ============================================================================


SUMMARIZATION_SYSTEM_PROMPT = """You are a context summarization assistant. Your role is to create structured, concise summaries of conversation history that preserve all essential information for continuing work."""

SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages."""

UPDATE_SUMMARIZATION_PROMPT = """The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

Update the existing structured summary with new information. RULES:
- PRESERVE all existing information from the previous summary
- ADD new progress, decisions, and context from the new messages
- UPDATE the Progress section: move items from "In Progress" to "Done" when completed
- UPDATE "Next Steps" based on what was accomplished
- PRESERVE exact file paths, function names, and error messages
- If something is no longer relevant, you may remove it

Use this EXACT format:

## Goal
[Preserve existing goals, add new ones if the task expanded]

## Constraints & Preferences
- [Preserve existing, add new ones discovered]

## Progress
### Done
- [x] [Include previously done items AND newly completed items]

### In Progress
- [ ] [Current work - update based on progress]

### Blocked
- [Current blockers - remove if resolved]

## Key Decisions
- **[Decision]**: [Brief rationale] (preserve all previous, add new)

## Next Steps
1. [Update based on current state]

## Critical Context
- [Preserve important context, add new if needed]

Keep each section concise. Preserve exact file paths, function names, and error messages."""


def _simple_truncate_messages(
    messages: list[dict[str, Any]],
    keep_recent_count: int = 5,
) -> str:
    """
    Fallback strategy: simple truncation with basic summary.

    Used when LLM summarization fails after all retries.
    """
    if not messages:
        return "No prior history."

    # Keep brief description of recent messages
    recent = messages[-keep_recent_count:] if len(messages) > keep_recent_count else messages
    summary_parts = ["[Context truncated due to summarization failure]\n"]
    summary_parts.append("## Recent Activity\n")

    for msg in recent:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, str):
            preview = content[:200]
        elif isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", "")[:100])
            preview = " ".join(texts)[:200]
        else:
            preview = str(content)[:200]

        summary_parts.append(f"- [{role.upper()}]: {preview}...")

    return "\n".join(summary_parts)


async def _retry_with_backoff(  # noqa: UP047
    func: Callable[P, Awaitable[T]],
    *args: P.args,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    **kwargs: P.kwargs,
) -> T:
    """Retry wrapper with exponential backoff."""
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt), MAX_DELAY)
                log_with_context(
                    logger, 30,  # WARNING
                    "LLM call failed, retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)

    raise last_error


def _serialize_messages_to_text(messages: list[dict[str, Any]]) -> str:
    """
    Serialize messages to text format for summarization.

    Args:
        messages: List of message dicts

    Returns:
        Formatted text representation of messages
    """
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # Handle different content formats
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                    if block_type == "text":
                        text_parts.append(block.get("text", ""))
                    elif block_type == "thinking":
                        text_parts.append(f"[Thinking: {block.get('thinking', '')}]")
                    elif block_type == "tool_use":
                        text_parts.append(
                            f"[Tool: {block.get('name', '')}({block.get('input', {})})]"
                        )
                    elif block_type == "tool_result":
                        text_parts.append(f"[Result: {block.get('content', '')}]")
            text = "\n".join(text_parts)
        else:
            text = str(content)

        lines.append(f"[{role.upper()}]: {text}")
        lines.append("")

    return "\n".join(lines)


async def generate_compaction_summary(
    messages_to_summarize: list[dict[str, Any]],
    previous_summary: str | None = None,
    max_tokens: int = 8192,
) -> str:
    """Generate a structured summary of messages using LLM with retry and fallback."""
    from agent.llm.anthropic_client import get_anthropic_client

    # Reserved for future model-level output budgeting.
    _ = max_tokens

    if not messages_to_summarize:
        return "No prior history to summarize."

    conversation_text = _serialize_messages_to_text(messages_to_summarize)

    prompt_text = f"<conversation>\n{conversation_text}\n</conversation>\n\n"
    if previous_summary:
        prompt_text += f"<previous-summary>\n{previous_summary}\n</previous-summary>\n\n"
        prompt_text += UPDATE_SUMMARIZATION_PROMPT
    else:
        prompt_text += SUMMARIZATION_PROMPT

    summarization_messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt_text}],
        }
    ]

    log_with_context(
        logger, 20,
        "Generating compaction summary",
        message_count=len(messages_to_summarize),
        has_previous_summary=previous_summary is not None,
    )

    async def _call_llm() -> str:
        client = get_anthropic_client()
        response = await client.create_message(
            messages=summarization_messages,
            system_prompt=SUMMARIZATION_SYSTEM_PROMPT,
        )

        content = response.get("content", [])
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        return "\n".join(text_parts)

    try:
        summary = await _retry_with_backoff(_call_llm)
        log_with_context(
            logger, 20,
            "Compaction summary generated",
            summary_length=len(summary),
        )
        return summary

    except Exception as e:
        # Fallback: use simple truncation
        log_with_context(
            logger, 40,  # ERROR
            "All compaction retries failed, using fallback truncation",
            error=str(e),
            messages_count=len(messages_to_summarize),
        )
        return _simple_truncate_messages(messages_to_summarize)


# ============================================================================
# Main Compaction Function
# ============================================================================


async def compact_context(
    messages: list[dict[str, Any]],
    settings: CompactionSettings,
    previous_summary: str | None = None,
    context_window: int = CONTEXT_WINDOW,
) -> CompactionResult | None:
    """
    Main compaction function.

    If context is too large, summarize older messages and keep recent ones.
    Returns CompactionResult with summary and metadata, or None if no compaction needed.

    Args:
        messages: List of message dicts
        settings: Compaction settings
        previous_summary: Optional previous summary to update
        context_window: Maximum context window size

    Returns:
        CompactionResult if compaction was performed, None otherwise
    """
    if not messages:
        return None

    # Estimate current context usage
    usage_estimate = estimate_context_tokens(messages)

    log_with_context(
        logger,
        20,  # INFO
        "Checking if compaction needed",
        total_tokens=usage_estimate.total_tokens,
        context_window=context_window,
        reserve_tokens=settings.reserve_tokens,
    )

    # Check if compaction is needed
    if not should_compact(usage_estimate.total_tokens, context_window, settings):
        log_with_context(
            logger,
            20,  # INFO
            "Compaction not needed",
            total_tokens=usage_estimate.total_tokens,
        )
        return None

    # Find cut point
    cut_index, is_split_turn = find_cut_point(
        messages,
        settings.keep_recent_tokens,
    )

    # Messages to summarize (will be discarded after summary)
    messages_to_summarize = messages[:cut_index]
    messages_to_keep = messages[cut_index:]

    if not messages_to_summarize:
        log_with_context(
            logger,
            20,  # INFO
            "No messages to summarize",
            cut_index=cut_index,
        )
        return None

    # Generate summary
    summary = await generate_compaction_summary(
        messages_to_summarize,
        previous_summary=previous_summary,
        max_tokens=int(0.8 * settings.reserve_tokens),
    )

    # Get ID of first kept message
    first_kept_message_id = messages_to_keep[0].get("id", "") if messages_to_keep else ""

    # Estimate tokens after compaction with the same system-memory wrapper
    # used in the final message history.
    summary_message = create_compaction_summary_message(
        summary,
        usage_estimate.total_tokens,
    )
    tokens_after = estimate_context_tokens([summary_message] + messages_to_keep).total_tokens

    result = CompactionResult(
        summary=summary,
        first_kept_message_id=first_kept_message_id,
        tokens_before=usage_estimate.total_tokens,
        tokens_after=tokens_after,
        messages_removed=len(messages_to_summarize),
    )

    log_with_context(
        logger,
        20,  # INFO
        "Compaction completed",
        tokens_before=result.tokens_before,
        tokens_after=result.tokens_after,
        messages_removed=result.messages_removed,
        cut_index=cut_index,
        is_split_turn=is_split_turn,
    )

    return result


# ============================================================================
# Utility Functions
# ============================================================================


def create_compaction_summary_message(summary: str, tokens_before: int) -> dict[str, Any]:
    """
    Create a compaction summary message as a system-memory block.

    This is intentionally not a normal user utterance. We keep it LLM-compatible
    by encoding the memory block as an assistant text message.

    Args:
        summary: The compaction summary text
        tokens_before: Token count before compaction

    Returns:
        LLM-compatible message dict
    """
    memory_text = (
        f"[System Memory Block: Context Compaction - {tokens_before} tokens compressed]\n"
        "Treat this as condensed session memory for continuity, not as a user instruction.\n\n"
        f"{summary}"
    )

    return {
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": memory_text,
            }
        ],
        "metadata": {
            "type": "compaction_summary",
            "semantic_role": "system_memory",
            "tokens_before": tokens_before,
        },
    }
