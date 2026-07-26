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

    @staticmethod
    def _is_user_attached(item: ContextItem) -> bool:
        """Whether the user explicitly attached/quoted this item."""
        metadata = item.metadata or {}
        return bool(metadata.get("attached") or metadata.get("is_quote"))

    @classmethod
    def _intent_rank(cls, item: ContextItem) -> int:
        """
        Ordering rank inside a priority group: user intent before relevance.

        组内顺序决定预算耗尽时谁被截断/丢弃，因此焦点文件必须排在最前
        （否则 query recall 加成可能把相关度抬到 1.0 以上的其他条目排到
        焦点之前），其次是用户显式附加/引用的内容。
        """
        if item.is_focus:
            return 0
        return 1 if cls._is_user_attached(item) else 2

    @classmethod
    def _allows_parent_upgrade(cls, items: list[ContextItem]) -> bool:
        """
        父大纲能否升级到 CRITICAL：批次里没有用户显式附加/引用的内容时才可以。

        升级的唯一目的是借用 TokenBudget.select_items 里 CRITICAL 的池化预算；
        但池化额度本来就是留给用户显式附加内容的，一旦两者同处 CRITICAL，
        相关度更高的父大纲会把附加文件截断甚至整体挤出上下文。此时让父大纲
        留在 CONSTRAINT 档，它仍有该档的保底份额。
        """
        return not any(
            cls._is_user_attached(item) and not item.is_focus for item in items
        )

    def classify_priority(
        self,
        item: ContextItem,
        *,
        allow_parent_upgrade: bool = True,
    ) -> ContextPriority:
        """
        Classify the priority of a context item.

        Args:
            item: Context item to classify
            allow_parent_upgrade: Whether relation="parent" outlines may be
                upgraded to CRITICAL (see _allows_parent_upgrade)

        Returns:
            ContextPriority level
        """
        # Focus content is always critical
        if item.is_focus:
            return ContextPriority.CRITICAL

        # Type/relation rules may upgrade a preset priority (e.g. parent
        # outlines carry whole-story background and must reach CRITICAL so
        # they can draw on the pooled budget in TokenBudget.select_items),
        # but never downgrade one — user-attached files and retrieval
        # snippets keep the tier the assembler explicitly assigned.
        type_priority = self._classify_by_type(item)

        # CRITICAL 是 _classify_by_type 里唯一的升级目标（relation="parent"）；
        # 拒绝升级时退到 CONSTRAINT（与 sibling/child 同档）而不是回落到预设，
        # 以保持"只升不降"不变式。
        if not allow_parent_upgrade and type_priority == ContextPriority.CRITICAL:
            type_priority = ContextPriority.CONSTRAINT

        order = ContextPriority.priority_order()
        if order.index(type_priority) < order.index(item.priority):
            return type_priority
        return item.priority

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
        allow_parent_upgrade = self._allows_parent_upgrade(items)
        for item in items:
            item.priority = self.classify_priority(
                item, allow_parent_upgrade=allow_parent_upgrade
            )

        # Priority order
        priority_order = {
            ContextPriority.CRITICAL: 0,
            ContextPriority.CONSTRAINT: 1,
            ContextPriority.RELEVANT: 2,
            ContextPriority.INSPIRATION: 3,
        }

        # Sort by:
        # 1. Priority (CRITICAL first)
        # 2. User intent (focus, then user-attached/quoted content)
        # 3. Relevance score (higher first)
        # 4. Type (outline > snippet > character > lore)
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
                self._intent_rank(x),
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

        allow_parent_upgrade = self._allows_parent_upgrade(items)
        for item in items:
            priority = self.classify_priority(
                item, allow_parent_upgrade=allow_parent_upgrade
            )
            groups[priority].append(item)

        # Sort within each group by user intent, then relevance.
        # TokenBudget.select_items 按这个顺序花预算，靠后的条目才会被截断/丢弃。
        for priority in groups:
            groups[priority].sort(
                key=lambda x: (self._intent_rank(x), -(x.relevance_score or 0))
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
