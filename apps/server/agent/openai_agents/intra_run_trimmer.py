"""Intra-run tool-output trimmer (a RunConfig.call_model_input_filter).

Why a custom filter instead of agents.extensions.ToolOutputTrimmer:

The stock SDK trimmer only trims tool outputs that appear *before* the
Nth-from-last ``user`` message. In this project that is a guaranteed no-op:
``normalize_messages_for_openai_agents`` (runner.py) strips all tool blocks from
persisted history to plain text, so cross-request tool outputs are never
``function_call_output`` items; and intra-run tool outputs always appear *after*
the current turn's user message, so they are always in the stock trimmer's
"recent" (never-trimmed) zone. Verified empirically: the stock trimmer reclaims
0 chars for every ``recent_turns`` value here.

This filter instead trims by *intra-run recency*: within the input list for a
single model call it keeps the most recent ``keep_recent`` trimmable tool
outputs at full fidelity and replaces earlier oversized ones (from the same run)
with a compact preview. Bulky read-only retrieval outputs (``query_files`` /
``hybrid_search``) accumulate across a multi-tool run and dominate later model
calls; previewing the stale ones reclaims that budget while keeping the freshest
results intact.

Control-flow tool outputs (``handoff_to_agent`` / ``request_clarification``) are
never trimmed: they are outside the allowlist, AND the runner reads their
payload from the live SDK run-item, not from this filtered model input — so the
filter cannot affect control flow even in principle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from utils.logger import get_logger

if TYPE_CHECKING:
    from agents.run_config import CallModelData, ModelInputData

logger = get_logger(__name__)

# Read-only retrieval tools whose outputs are bulky and safe to preview once stale.
DEFAULT_TRIMMABLE_TOOLS: frozenset[str] = frozenset({"query_files", "hybrid_search"})


class IntraRunToolOutputTrimmer:
    """Preview stale intra-run tool outputs before each model call.

    Args:
        keep_recent: Number of most-recent trimmable tool outputs kept at full
            fidelity. Older trimmable outputs in the same run become candidates
            for previewing. Defaults to 2.
        max_output_chars: Only outputs longer than this are previewed. Defaults
            to 2000 (well above a one-line result, below a typical search dump).
        preview_chars: How many leading characters of the original output to keep
            in the preview. Defaults to 400.
        trimmable_tools: Tool names whose outputs may be previewed. Defaults to
            ``{"query_files", "hybrid_search"}``. Control-flow tools are never
            included.
    """

    def __init__(
        self,
        *,
        keep_recent: int = 2,
        max_output_chars: int = 2000,
        preview_chars: int = 400,
        trimmable_tools: frozenset[str] | None = None,
    ) -> None:
        if keep_recent < 0:
            raise ValueError(f"keep_recent must be >= 0, got {keep_recent}")
        if max_output_chars < 1:
            raise ValueError(f"max_output_chars must be >= 1, got {max_output_chars}")
        if preview_chars < 0:
            raise ValueError(f"preview_chars must be >= 0, got {preview_chars}")
        self.keep_recent = keep_recent
        self.max_output_chars = max_output_chars
        self.preview_chars = preview_chars
        self.trimmable_tools = (
            DEFAULT_TRIMMABLE_TOOLS if trimmable_tools is None else frozenset(trimmable_tools)
        )

    def __call__(self, data: CallModelData[Any]) -> ModelInputData:
        from agents.run_config import ModelInputData

        model_data = data.model_data
        items = model_data.input
        if not items:
            return model_data

        call_id_to_name = self._build_call_id_to_name(items)

        # Indices of trimmable function_call_output items, in input order.
        trimmable_indices = [
            i
            for i, it in enumerate(items)
            if self._is_trimmable_output(it, call_id_to_name)
        ]

        # Keep the most recent `keep_recent` trimmable outputs untouched.
        if len(trimmable_indices) <= self.keep_recent:
            return model_data
        stale_cutoff = len(trimmable_indices) - self.keep_recent if self.keep_recent else len(trimmable_indices)
        stale_indices = set(trimmable_indices[:stale_cutoff])

        new_items: list[Any] = []
        trimmed_count = 0
        chars_saved = 0
        for i, it in enumerate(items):
            if i in stale_indices:
                previewed, saved = self._preview_output(it)
                if previewed is not None:
                    new_items.append(previewed)
                    trimmed_count += 1
                    chars_saved += saved
                    continue
            new_items.append(it)

        if trimmed_count:
            self._record_metrics(trimmed_count, chars_saved)
            logger.debug(
                "IntraRunToolOutputTrimmer previewed %d stale tool output(s), saved ~%d chars",
                trimmed_count,
                chars_saved,
            )

        return ModelInputData(input=new_items, instructions=model_data.instructions)

    def _build_call_id_to_name(self, items: list[Any]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for it in items:
            if isinstance(it, dict) and it.get("type") == "function_call":
                call_id = it.get("call_id") or it.get("id")
                name = it.get("name")
                if call_id and name:
                    mapping[str(call_id)] = str(name)
        return mapping

    def _is_trimmable_output(self, item: Any, call_id_to_name: dict[str, str]) -> bool:
        if not isinstance(item, dict) or item.get("type") != "function_call_output":
            return False
        call_id = str(item.get("call_id") or item.get("id") or "")
        return call_id_to_name.get(call_id, "") in self.trimmable_tools

    def _preview_output(self, item: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
        output = item.get("output", "")
        output_str = output if isinstance(output, str) else str(output)
        original_len = len(output_str)
        if original_len <= self.max_output_chars:
            return None, 0

        preview = output_str[: self.preview_chars]
        summary = (
            f"[Trimmed stale tool output — {original_len} chars → "
            f"{self.preview_chars} char preview]\n{preview}..."
        )
        if len(summary) >= original_len:
            return None, 0

        previewed = dict(item)
        previewed["output"] = summary
        return previewed, original_len - len(summary)

    def _record_metrics(self, trimmed_count: int, chars_saved: int) -> None:
        try:
            from agent.core.metrics import (
                TOOL_OUTPUT_TRIMMED_CHARS,
                TOOL_OUTPUT_TRIMMED_TOTAL,
                get_metrics_collector,
            )

            mc = get_metrics_collector()
            mc.increment_counter(TOOL_OUTPUT_TRIMMED_TOTAL, trimmed_count)
            mc.increment_counter(TOOL_OUTPUT_TRIMMED_CHARS, chars_saved)
        except Exception:  # metrics are best-effort; never break a model call
            logger.debug("Failed to record tool-output-trim metrics", exc_info=True)
