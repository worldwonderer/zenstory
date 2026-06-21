"""
Context assembly module.

Provides:
- Context assembler for gathering project data
- Priority-based context management
- Token budget allocation
- Retriever for snippets
"""

from .assembler import ContextAssembler, get_context_assembler
from .budget import TokenBudget
from .prioritizer import ContextPrioritizer

__all__ = [
    "ContextAssembler",
    "get_context_assembler",
    "ContextPrioritizer",
    "TokenBudget",
]
