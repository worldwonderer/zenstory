"""
Context prioritization based on content type and relevance.

Implements the priority system:
- CRITICAL: Focus content, must include
- CONSTRAINT: Character settings, high-importance lore, style rules
- RELEVANT: Retrieved snippets, related outlines
- INSPIRATION: Low-importance lore, general references
"""


from ..schemas.context import ContextItem, ContextPriority


class ContextPrioritizer:
    """
    Prioritizes context items based on type and relevance.

    Uses the priority system to ensure important context
    is included within token budget.
    """

    def __init__(self):
        """Initialize prioritizer with default rules."""
        pass

    def classify_priority(self, item: ContextItem) -> ContextPriority:
        """
        Classify the priority of a context item.

        Args:
            item: Context item to classify

        Returns:
            ContextPriority level
        """
        # Focus content is always critical
        if item.is_focus:
            return ContextPriority.CRITICAL

        # Priority already set
        if item.priority != ContextPriority.INSPIRATION:
            return item.priority

        # Classify based on type and metadata
        return self._classify_by_type(item)

    def _classify_by_type(self, item: ContextItem) -> ContextPriority:
        """Classify based on item type and metadata."""
        item_type = item.type

        # Outlines
        if item_type == "outline":
            relation = item.metadata.get("relation", "")
            if relation == "parent":
                return ContextPriority.CRITICAL
            elif relation in ("sibling", "child", "previous"):
                return ContextPriority.CONSTRAINT
            return ContextPriority.RELEVANT

        # Characters are always constraints
        if item_type == "character":
            return ContextPriority.CONSTRAINT

        # Lore depends on importance
        if item_type == "lore":
            importance = item.metadata.get("importance", "low")
            if importance == "high":
                return ContextPriority.CONSTRAINT
            elif importance == "medium":
                return ContextPriority.RELEVANT
            return ContextPriority.INSPIRATION

        # Snippets depend on relevance score
        if item_type == "snippet":
            if item.relevance_score and item.relevance_score > 0.7:
                return ContextPriority.RELEVANT
            elif item.relevance_score and item.relevance_score > 0.4:
                return ContextPriority.INSPIRATION
            return ContextPriority.INSPIRATION

        # Default
        return ContextPriority.INSPIRATION

    def prioritize(
        self,
        items: list[ContextItem],
    ) -> list[ContextItem]:
        """
        Sort items by priority and relevance.

        Args:
            items: List of context items

        Returns:
            Sorted list (highest priority first)
        """
        # Assign priorities
        for item in items:
            item.priority = self.classify_priority(item)

        # Priority order
        priority_order = {
            ContextPriority.CRITICAL: 0,
            ContextPriority.CONSTRAINT: 1,
            ContextPriority.RELEVANT: 2,
            ContextPriority.INSPIRATION: 3,
        }

        # Sort by:
        # 1. Priority (CRITICAL first)
        # 2. Relevance score (higher first)
        # 3. Type (outline > snippet > character > lore)
        type_order = {
            "outline": 0,
            "snippet": 1,
            "character": 2,
            "lore": 3,
        }

        return sorted(
            items,
            key=lambda x: (
                priority_order.get(x.priority, 4),
                -(x.relevance_score or 0),
                type_order.get(x.type, 4),
            )
        )

    def group_by_priority(
        self,
        items: list[ContextItem],
    ) -> dict[ContextPriority, list[ContextItem]]:
        """
        Group items by priority level.

        Args:
            items: List of context items

        Returns:
            Dict mapping priority to items
        """
        groups: dict[ContextPriority, list[ContextItem]] = {
            p: [] for p in ContextPriority
        }

        for item in items:
            priority = self.classify_priority(item)
            groups[priority].append(item)

        # Sort within each group by relevance
        for priority in groups:
            groups[priority].sort(
                key=lambda x: -(x.relevance_score or 0)
            )

        return groups

    def get_budget_allocation(
        self,
        max_tokens: int,
        custom_allocation: dict[ContextPriority, float] | None = None,
    ) -> dict[ContextPriority, int]:
        """
        Get token budget allocation per priority.

        Args:
            max_tokens: Total token budget
            custom_allocation: Optional custom percentages

        Returns:
            Dict mapping priority to token count
        """
        allocation = custom_allocation or ContextPriority.get_budget_allocation()

        return {
            priority: int(max_tokens * pct)
            for priority, pct in allocation.items()
        }
