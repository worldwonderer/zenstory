"""
Context assembly module.

Provides:
- Context assembler for gathering project data
- Priority-based context management
- Token budget allocation
- Retriever for snippets
- Context compaction for long sessions
"""

from .assembler import ContextAssembler, get_context_assembler
from .budget import TokenBudget
from .compaction import (
    CONTEXT_WINDOW,
    CompactionResult,
    CompactionSettings,
    ContextUsageEstimate,
    compact_context,
    create_compaction_summary_message,
    estimate_context_tokens,
    estimate_tokens,
    find_cut_point,
    generate_compaction_summary,
    should_compact,
)
from .prioritizer import ContextPrioritizer

__all__ = [
    "ContextAssembler",
    "get_context_assembler",
    "ContextPrioritizer",
    "TokenBudget",
    # Compaction
    "CompactionSettings",
    "CompactionResult",
    "ContextUsageEstimate",
    "compact_context",
    "create_compaction_summary_message",
    "estimate_context_tokens",
    "estimate_tokens",
    "find_cut_point",
    "generate_compaction_summary",
    "should_compact",
    "CONTEXT_WINDOW",
]
