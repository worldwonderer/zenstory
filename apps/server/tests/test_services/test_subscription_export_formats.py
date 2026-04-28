"""Unit tests for export-format entitlement consistency."""

from api.subscription import _normalize_plan_entitlements, _normalize_plan_features_for_response
from services.subscription.defaults import normalize_export_formats


def test_normalize_export_formats_filters_to_supported_values() -> None:
    assert normalize_export_formats(["txt", "md", "PDF", "txt", 1, " "]) == ["txt"]


def test_normalize_export_formats_rejects_invalid_type() -> None:
    assert normalize_export_formats("txt") == []


def test_catalog_entitlements_keep_only_runtime_supported_export_format() -> None:
    entitlements = _normalize_plan_entitlements(
        "pro",
        {
            "export_formats": ["txt", "md", "docx", "pdf"],
        },
    )

    assert entitlements["export_formats"] == ["txt"]


def test_me_or_plans_response_features_are_normalized() -> None:
    assert _normalize_plan_features_for_response(None)["export_formats"] == ["txt"]
    assert _normalize_plan_features_for_response({"export_formats": ["txt", "md"]})["export_formats"] == ["txt"]
