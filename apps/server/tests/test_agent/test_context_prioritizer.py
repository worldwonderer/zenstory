from __future__ import annotations

from agent.context.prioritizer import ContextPrioritizer
from agent.schemas.context import ContextItem, ContextPriority


def _item(
    *,
    item_type: str,
    title: str,
    relevance_score: float | None = None,
    metadata: dict | None = None,
    priority: ContextPriority = ContextPriority.INSPIRATION,
) -> ContextItem:
    return ContextItem(
        id=f"{item_type}-{title}",
        type=item_type,
        title=title,
        content=f"content for {title}",
        relevance_score=relevance_score,
        metadata=metadata or {},
        priority=priority,
    )


def test_classify_priority_uses_focus_flag_and_outline_relations():
    prioritizer = ContextPrioritizer()

    focus_outline = _item(item_type="outline", title="focus", metadata={"is_focus": True, "relation": "child"})
    sibling_outline = _item(item_type="outline", title="sibling", metadata={"relation": "sibling"})
    other_outline = _item(item_type="outline", title="other", metadata={"relation": "other"})

    assert prioritizer.classify_priority(focus_outline) == ContextPriority.CRITICAL
    assert prioritizer.classify_priority(sibling_outline) == ContextPriority.CONSTRAINT
    assert prioritizer.classify_priority(other_outline) == ContextPriority.RELEVANT


def test_classify_priority_handles_lore_and_snippet_thresholds():
    prioritizer = ContextPrioritizer()

    high_lore = _item(item_type="lore", title="law", metadata={"importance": "high"})
    medium_lore = _item(item_type="lore", title="history", metadata={"importance": "medium"})
    weak_snippet = _item(item_type="snippet", title="weak", relevance_score=0.3)
    strong_snippet = _item(item_type="snippet", title="strong", relevance_score=0.8)

    assert prioritizer.classify_priority(high_lore) == ContextPriority.CONSTRAINT
    assert prioritizer.classify_priority(medium_lore) == ContextPriority.RELEVANT
    assert prioritizer.classify_priority(weak_snippet) == ContextPriority.INSPIRATION
    assert prioritizer.classify_priority(strong_snippet) == ContextPriority.RELEVANT


def test_prioritize_sorts_by_priority_then_relevance_then_type():
    prioritizer = ContextPrioritizer()
    items = [
        _item(item_type="lore", title="lore", relevance_score=0.9, metadata={"importance": "low"}),
        _item(item_type="snippet", title="snippet", relevance_score=0.95),
        _item(item_type="character", title="character", relevance_score=0.1),
        _item(item_type="outline", title="outline", relevance_score=0.4, metadata={"relation": "parent"}),
    ]

    result = prioritizer.prioritize(items)

    assert [item.title for item in result] == ["outline", "character", "snippet", "lore"]


def test_group_by_priority_and_budget_allocation():
    prioritizer = ContextPrioritizer()
    items = [
        _item(item_type="snippet", title="high-snippet", relevance_score=0.9),
        _item(item_type="snippet", title="low-snippet", relevance_score=0.45),
        _item(item_type="character", title="hero"),
    ]

    groups = prioritizer.group_by_priority(items)
    allocation = prioritizer.get_budget_allocation(
        1000,
        {ContextPriority.CRITICAL: 0.1, ContextPriority.CONSTRAINT: 0.2},
    )

    assert [item.title for item in groups[ContextPriority.RELEVANT]] == ["high-snippet"]
    assert [item.title for item in groups[ContextPriority.INSPIRATION]] == ["low-snippet"]
    assert [item.title for item in groups[ContextPriority.CONSTRAINT]] == ["hero"]
    assert allocation == {
        ContextPriority.CRITICAL: 100,
        ContextPriority.CONSTRAINT: 200,
    }
