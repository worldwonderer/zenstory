"""
Route introspection for SKILL.md generation.

Extracts endpoint metadata from FastAPI routers to auto-generate
accurate API documentation, eliminating manual sync drift.
"""

from dataclasses import dataclass, field

from fastapi.routing import APIRoute

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EndpointInfo:
    """Extracted metadata for a single API endpoint."""

    method: str
    path: str
    summary: str
    scope: str
    request_schema: dict | None = None
    response_schema: dict | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "path": self.path,
            "summary": self.summary,
            "scope": self.scope,
            "request_schema": self.request_schema,
            "response_schema": self.response_schema,
            "tags": self.tags,
        }


def _extract_scope_from_dependencies(route: APIRoute) -> str:
    """Extract required scope from route dependencies by inspecting closure vars."""
    for dep in route.dependant.dependencies:
        if dep.call is None:
            continue
        closure = getattr(dep.call, "__closure__", None)
        if not closure:
            continue
        for cell in closure:
            val = cell.cell_contents
            if isinstance(val, str) and val in ("read", "write"):
                return val
    return "unknown"


def _extract_schema(model_class: type | None) -> dict | None:
    """Extract JSON schema from a Pydantic model class."""
    if model_class is None:
        return None
    try:
        return model_class.model_json_schema()
    except (AttributeError, Exception):
        return None


def extract_agent_endpoints(router) -> list[EndpointInfo]:
    """
    Extract endpoint metadata from a FastAPI router.

    Iterates all APIRoute entries and extracts method, path, summary,
    required scope, request/response schemas.
    """
    endpoints: list[EndpointInfo] = []

    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue

        methods = list(route.methods or set())
        if not methods:
            continue

        method = methods[0]
        path = route.path
        summary = route.summary or route.name or ""
        scope = _extract_scope_from_dependencies(route)
        tags = list(route.tags) if route.tags else []

        request_schema = None
        if route.dependant and route.dependant.body_params:
            body_param = route.dependant.body_params[0]
            request_schema = _extract_schema(body_param.field_info.annotation) if body_param.field_info else None

        response_schema = None
        if route.response_model:
            response_schema = _extract_schema(route.response_model)

        endpoints.append(
            EndpointInfo(
                method=method,
                path=path,
                summary=summary,
                scope=scope,
                request_schema=request_schema,
                response_schema=response_schema,
                tags=tags,
            )
        )

    endpoints.sort(key=lambda e: (e.path, e.method))
    return endpoints
