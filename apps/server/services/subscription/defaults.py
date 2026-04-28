"""Canonical default values for subscription plans."""

from copy import deepcopy
from typing import Any

DEFAULT_FREE_PLAN_NAME = "free"
DEFAULT_FREE_PLAN_DISPLAY_NAME = "免费试用"
DEFAULT_FREE_PLAN_DISPLAY_NAME_EN = "Free Trial"
DEFAULT_FREE_PLAN_PRICE_MONTHLY_CENTS = 0
DEFAULT_FREE_PLAN_PRICE_YEARLY_CENTS = 0

DEFAULT_FREE_PLAN_FEATURES: dict[str, Any] = {
    "ai_conversations_per_day": 20,
    "context_window_tokens": 4096,
    "file_versions_per_file": 10,
    "max_projects": 3,
    "export_formats": ["txt"],
    "custom_prompts": False,
    "materials_library_access": False,
    "material_uploads": 0,
    "material_decompositions": 0,
    "custom_skills": 3,
    "inspiration_copies_monthly": 10,
    "priority_support": False,
}

SUPPORTED_EXPORT_FORMATS: tuple[str, ...] = ("txt",)


DEFAULT_FREE_TIER: dict[str, Any] = {
    "name": DEFAULT_FREE_PLAN_NAME,
    "display_name": DEFAULT_FREE_PLAN_DISPLAY_NAME,
    "display_name_en": DEFAULT_FREE_PLAN_DISPLAY_NAME_EN,
    "price_monthly_cents": DEFAULT_FREE_PLAN_PRICE_MONTHLY_CENTS,
    "price_yearly_cents": DEFAULT_FREE_PLAN_PRICE_YEARLY_CENTS,
    "features": DEFAULT_FREE_PLAN_FEATURES,
}


def clone_default_free_features() -> dict[str, Any]:
    """Return a mutable copy of free-tier features."""
    return deepcopy(DEFAULT_FREE_PLAN_FEATURES)


def normalize_export_formats(export_formats: Any) -> list[str]:
    """
    Normalize export formats to currently supported, deduplicated values.

    Unsupported/invalid values are dropped to ensure subscription entitlements
    remain aligned with runtime export capability.
    """
    if not isinstance(export_formats, list):
        return []

    normalized: list[str] = []
    for raw_format in export_formats:
        if not isinstance(raw_format, str):
            continue
        candidate = raw_format.strip().lower()
        if candidate in SUPPORTED_EXPORT_FORMATS and candidate not in normalized:
            normalized.append(candidate)

    return normalized
