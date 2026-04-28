from __future__ import annotations

import pytest
from fastapi import Request
from starlette.datastructures import Headers

from middleware import rate_limit as rate_limit_module


def _request(*, headers: dict[str, str] | None = None, client_host: str = "198.51.100.10") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/rate-limit",
        "headers": Headers(headers or {}).raw,
        "scheme": "http",
        "server": ("testserver", 80),
        "client": (client_host, 1234),
        "query_string": b"",
    }
    return Request(scope)


def test_get_client_ip_returns_unknown_for_invalid_client_host():
    assert rate_limit_module.get_client_ip(_request(client_host="not-an-ip")) == "unknown"


def test_get_redis_error_cooldown_seconds_defaults_for_invalid_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REDIS_ERROR_COOLDOWN_SECONDS", "oops")
    assert rate_limit_module._get_redis_error_cooldown_seconds() == 30


def test_require_rate_limit_raises_after_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    rate_limit_module._rate_limit_store.clear()
    dependency = rate_limit_module.require_rate_limit("login", 1, 60)
    request = _request()

    assert dependency(request) == 0

    with pytest.raises(rate_limit_module.HTTPException):
        dependency(request)
