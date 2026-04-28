"""
Token budget management for context assembly.

Handles token estimation, budget allocation, and content truncation
to fit within prompt limits.
"""

from typing import Any

from agent.utils.token_utils import CHARS_PER_TOKEN, estimate_text_tokens

from ..schemas.context import ContextItem, ContextPriority


class TokenBudget:
    """
    Manages token budget for context assembly.

    Features:
    - Token estimation for text
    - Priority-based budget allocation
    - Smart truncation with preserved meaning
    """

    # Default budget allocation percentages
    DEFAULT_ALLOCATION = {
        ContextPriority.CRITICAL: 0.30,
        ContextPriority.CONSTRAINT: 0.35,
        ContextPriority.RELEVANT: 0.25,
        ContextPriority.INSPIRATION: 0.10,
    }

    def __init__(
        self,
        max_tokens: int = 4000,
        allocation: dict[ContextPriority, float] | None = None,
    ):
        """
        Initialize budget manager.

        Args:
            max_tokens: Maximum total tokens
            allocation: Custom priority allocation percentages
        """
        self.max_tokens = max_tokens
        self.allocation = allocation or self.DEFAULT_ALLOCATION
        self.used: dict[ContextPriority, int] = dict.fromkeys(ContextPriority, 0)

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses simple character-based estimation.
        For more accurate results, use tiktoken.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return estimate_text_tokens(text)

    def estimate_item_tokens(self, item: ContextItem) -> int:
        """
        Estimate tokens for a context item.

        Includes title and content.

        Args:
            item: Context item

        Returns:
            Estimated token count
        """
        return self.estimate_tokens(f"{item.title}\n{item.content}")

    def get_budget(self, priority: ContextPriority) -> int:
        """
        Get token budget for a priority level.

        Args:
            priority: Priority level

        Returns:
            Token budget
        """
        pct = self.allocation.get(priority, 0.1)
        return int(self.max_tokens * pct)

    def get_remaining(self, priority: ContextPriority) -> int:
        """
        Get remaining budget for a priority.

        Args:
            priority: Priority level

        Returns:
            Remaining tokens
        """
        return self.get_budget(priority) - self.used.get(priority, 0)

    def get_total_remaining(self) -> int:
        """Get total remaining budget across all priorities."""
        return self.max_tokens - sum(self.used.values())

    def allocate(
        self,
        priority: ContextPriority,
        tokens: int,
    ) -> bool:
        """
        Allocate tokens from a priority budget.

        Args:
            priority: Priority level
            tokens: Tokens to allocate

        Returns:
            True if allocation succeeded
        """
        remaining = self.get_remaining(priority)
        if tokens <= remaining:
            self.used[priority] = self.used.get(priority, 0) + tokens
            return True
        return False

    def can_fit(
        self,
        item: ContextItem,
        priority: ContextPriority | None = None,
    ) -> bool:
        """
        Check if an item can fit in the budget.

        Args:
            item: Context item
            priority: Priority level (uses item's priority if not specified)

        Returns:
            True if item fits
        """
        priority = priority or item.priority
        tokens = self.estimate_item_tokens(item)
        return tokens <= self.get_remaining(priority)

    def select_items(
        self,
        items: list[ContextItem],
        priority_groups: dict[ContextPriority, list[ContextItem]] | None = None,
    ) -> tuple[list[ContextItem], dict[ContextPriority, int]]:
        """
        Select items that fit within budget.

        Uses priority-based allocation to ensure important
        content is included first.

        Args:
            items: All context items (will be grouped by priority)
            priority_groups: Pre-grouped items (optional)

        Returns:
            Tuple of (selected items, budget usage)
        """
        selected: list[ContextItem] = []

        # Group items by priority if not provided
        if priority_groups is None:
            priority_groups = {}
            for item in items:
                p = item.priority
                if p not in priority_groups:
                    priority_groups[p] = []
                priority_groups[p].append(item)

        # Process each priority level in order
        for priority in ContextPriority.priority_order():
            group_items = priority_groups.get(priority, [])
            budget = self.get_budget(priority)
            used = 0

            for item in group_items:
                tokens = self.estimate_item_tokens(item)

                if used + tokens <= budget:
                    selected.append(item)
                    used += tokens
                else:
                    # Try to fit a truncated version
                    remaining = budget - used
                    if remaining > 50:  # Only if meaningful space
                        truncated = self.truncate_item(item, remaining)
                        if truncated:
                            selected.append(truncated)
                            used += self.estimate_item_tokens(truncated)
                    # Keep scanning remaining items in this priority group.
                    # A later item may still fit even if the current one doesn't.
                    continue

            self.used[priority] = used

        return selected, dict(self.used)

    def truncate_item(
        self,
        item: ContextItem,
        max_tokens: int,
    ) -> ContextItem | None:
        """
        Truncate an item to fit within token limit.

        Args:
            item: Item to truncate
            max_tokens: Maximum tokens

        Returns:
            Truncated item or None if too small
        """
        if max_tokens < 20:
            return None

        # Reserve tokens for title
        title_tokens = self.estimate_tokens(item.title) + 5  # +5 for formatting
        content_tokens = max_tokens - title_tokens

        if content_tokens < 20:
            return None

        # Truncate content
        max_chars = content_tokens * CHARS_PER_TOKEN
        content = item.content[:max_chars]

        # Try to cut at a sentence or word boundary
        for sep in ["。", ".", "！", "!", "？", "?", "\n", "，", ",", " "]:
            last_sep = content.rfind(sep)
            if last_sep > max_chars * 0.6:
                content = content[:last_sep + 1]
                break

        content = content.rstrip() + "..."

        return ContextItem(
            id=item.id,
            type=item.type,
            title=item.title,
            content=content,
            relevance_score=item.relevance_score,
            priority=item.priority,
            metadata={**item.metadata, "truncated": True},
        )

    def get_usage_report(self) -> dict[str, Any]:
        """
        Get a report of budget usage.

        Returns:
            Dict with usage statistics
        """
        return {
            "max_tokens": self.max_tokens,
            "used_tokens": sum(self.used.values()),
            "remaining_tokens": self.get_total_remaining(),
            "by_priority": {
                p.value: {
                    "budget": self.get_budget(p),
                    "used": self.used.get(p, 0),
                    "remaining": self.get_remaining(p),
                }
                for p in ContextPriority
            },
        }
