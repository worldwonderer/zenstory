"""
World-model visibility helpers for context item routing.

Routing contract:
- hidden: do not inject into any world-model channel
- reference: inject to world_model_surface only
- active: inject to world_model_truth by default
- explicit truth/surface metadata can override defaults
"""

from __future__ import annotations

from typing import Any

_TRUTH_ITEM_TYPES = {"character", "lore", "quote"}
_SURFACE_ITEM_TYPES = {"outline", "draft", "snippet"}

_VIS_HIDDEN = {"hidden", "none", "off", "disabled"}
_VIS_REFERENCE = {"reference", "ref", "surface"}
_VIS_ACTIVE = {"active", "default", "main"}

_ROUTE_TRUTH = {"truth", "core", "canonical"}
_ROUTE_SURFACE = {"surface", "scene", "reference", "ref"}
_ROUTE_BOTH = {"both", "all", "dual", "truth+surface", "surface+truth"}
_ROUTE_NONE = {"none", "hidden", "off", "disabled"}


def extract_item_metadata(raw_item: dict[str, Any]) -> dict[str, Any]:
    """Return safe metadata dict from a raw context item payload."""
    metadata = raw_item.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def resolve_world_model_channels(
    *,
    item_type: str,
    metadata: dict[str, Any] | None,
) -> tuple[bool, bool]:
    """
    Resolve whether a context item should be routed to truth/surface channels.

    Returns:
        (inject_truth, inject_surface)
    """
    safe_metadata = metadata if isinstance(metadata, dict) else {}
    visibility = _resolve_visibility(safe_metadata)
    if visibility in _VIS_HIDDEN:
        return (False, False)

    explicit_route = _resolve_explicit_route(safe_metadata)
    if explicit_route is not None:
        return explicit_route

    if visibility in _VIS_REFERENCE:
        return (False, True)
    if visibility in _VIS_ACTIVE:
        return (True, False)

    normalized_type = str(item_type or "").strip().lower()
    if normalized_type in _TRUTH_ITEM_TYPES:
        return (True, False)
    if normalized_type in _SURFACE_ITEM_TYPES:
        return (False, True)

    return (False, False)


def _resolve_visibility(metadata: dict[str, Any]) -> str:
    for key in ("visibility", "context_visibility", "world_model_visibility"):
        value = _normalize_label(metadata.get(key))
        if value:
            return value

    world_model = metadata.get("world_model")
    if isinstance(world_model, dict):
        value = _normalize_label(world_model.get("visibility"))
        if value:
            return value

    return ""


def _resolve_explicit_route(metadata: dict[str, Any]) -> tuple[bool, bool] | None:
    truth_flag = _resolve_flag(metadata, keys=("truth", "world_model_truth", "inject_truth"))
    surface_flag = _resolve_flag(
        metadata,
        keys=("surface", "world_model_surface", "inject_surface"),
    )

    world_model = metadata.get("world_model")
    if isinstance(world_model, dict):
        if truth_flag is None:
            truth_flag = _resolve_flag(world_model, keys=("truth", "world_model_truth"))
        if surface_flag is None:
            surface_flag = _resolve_flag(world_model, keys=("surface", "world_model_surface"))

    if truth_flag is not None or surface_flag is not None:
        return (bool(truth_flag), bool(surface_flag))

    route = _resolve_route_label(metadata)
    if not route:
        return None
    if route in _ROUTE_BOTH:
        return (True, True)
    if route in _ROUTE_TRUTH:
        return (True, False)
    if route in _ROUTE_SURFACE:
        return (False, True)
    if route in _ROUTE_NONE:
        return (False, False)

    return None


def _resolve_route_label(metadata: dict[str, Any]) -> str:
    for key in ("route", "world_model_route", "channel", "layer"):
        label = _normalize_label(metadata.get(key))
        if label:
            return label

    world_model = metadata.get("world_model")
    if isinstance(world_model, dict):
        for key in ("route", "channel", "layer"):
            label = _normalize_label(world_model.get(key))
            if label:
                return label

    return ""


def _resolve_flag(source: dict[str, Any], *, keys: tuple[str, ...]) -> bool | None:
    for key in keys:
        if key not in source:
            continue
        value = _normalize_bool(source.get(key))
        if value is not None:
            return value
    return None


def _normalize_label(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)

    label = _normalize_label(value)
    if label in {"true", "1", "yes", "y", "on"}:
        return True
    if label in {"false", "0", "no", "n", "off"}:
        return False

    return None
