"""Tests for rate limit helper IP extraction behavior."""

import pytest
from starlette.requests import Request

import middleware.rate_limit as rate_limit_module
from middleware.rate_limit import _rate_limit_store, check_rate_limit, get_client_ip


def _build_request(
    *,
    headers: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> Request:
    encoded_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": encoded_headers,
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _clear_rate_limit_store(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("RATE_LIMIT_REDIS_PREFIX", raising=False)
    monkeypatch.setattr(rate_limit_module, "_redis_retry_after_monotonic", 0.0)
    _rate_limit_store.clear()
    yield
    _rate_limit_store.clear()


@pytest.mark.unit
def test_get_client_ip_prefers_x_real_ip():
    request = _build_request(
        headers={
            "X-Real-IP": "198.51.100.8",
            "X-Forwarded-For": "203.0.113.1, 70.41.3.18",
        },
        client_host="10.0.0.9",
    )
    assert get_client_ip(request) == "198.51.100.8"


@pytest.mark.unit
def test_get_client_ip_uses_x_forwarded_for_when_x_real_missing():
    request = _build_request(
        headers={"X-Forwarded-For": "203.0.113.1, 70.41.3.18"},
        client_host="10.0.0.9",
    )
    assert get_client_ip(request) == "203.0.113.1"


@pytest.mark.unit
def test_get_client_ip_ignores_invalid_x_real_and_uses_forwarded():
    request = _build_request(
        headers={
            "X-Real-IP": "not-an-ip",
            "X-Forwarded-For": "invalid, 198.51.100.11",
        },
        client_host="10.0.0.9",
    )
    assert get_client_ip(request) == "198.51.100.11"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"X-Real-IP": "[2001:db8::1]"}, "2001:db8::1"),
        ({"X-Real-IP": "198.51.100.12:443"}, "198.51.100.12"),
    ],
)
def test_get_client_ip_normalizes_ipv6_and_ipv4_port_formats(headers, expected):
    request = _build_request(headers=headers, client_host="10.0.0.9")
    assert get_client_ip(request) == expected


@pytest.mark.unit
def test_get_client_ip_falls_back_to_request_client_host():
    request = _build_request(client_host="192.0.2.77")
    assert get_client_ip(request) == "192.0.2.77"


@pytest.mark.unit
def test_check_rate_limit_uses_resolved_client_ip_key():
    request = _build_request(headers={"X-Real-IP": "198.51.100.10"})
    allowed1, remaining1 = check_rate_limit(request, "auth_login_ip", 1, 60)
    allowed2, remaining2 = check_rate_limit(request, "auth_login_ip", 1, 60)

    assert allowed1 is True
    assert remaining1 == 0
    assert allowed2 is False
    assert remaining2 == 0


@pytest.mark.unit
def test_check_rate_limit_can_scope_without_client_ip():
    request_from_ip1 = _build_request(headers={"X-Real-IP": "198.51.100.11"})
    request_from_ip2 = _build_request(headers={"X-Real-IP": "198.51.100.12"})

    allowed1, remaining1 = check_rate_limit(
        request_from_ip1,
        "auth_login_identifier:test@example.com",
        1,
        60,
        include_client_ip=False,
    )
    allowed2, remaining2 = check_rate_limit(
        request_from_ip2,
        "auth_login_identifier:test@example.com",
        1,
        60,
        include_client_ip=False,
    )

    assert allowed1 is True
    assert remaining1 == 0
    assert allowed2 is False
    assert remaining2 == 0


class _FakeRedisClient:
    def __init__(self):
        self._counts: dict[str, int] = {}
        self._ttls: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def expire(self, key: str, seconds: int) -> bool:
        self._ttls[key] = seconds
        return True

    def ttl(self, key: str) -> int:
        return self._ttls.get(key, -1)


@pytest.mark.unit
def test_check_rate_limit_uses_redis_when_backend_enabled(monkeypatch):
    request = _build_request(headers={"X-Real-IP": "198.51.100.20"})
    fake_redis = _FakeRedisClient()

    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")
    monkeypatch.setattr(rate_limit_module, "get_redis_client", lambda: fake_redis)

    allowed1, remaining1 = check_rate_limit(request, "auth_login_ip", 1, 60)
    allowed2, remaining2 = check_rate_limit(request, "auth_login_ip", 1, 60)

    assert allowed1 is True
    assert remaining1 == 0
    assert allowed2 is False
    assert remaining2 == 0
    assert _rate_limit_store == {}


@pytest.mark.unit
def test_check_rate_limit_falls_back_to_memory_when_redis_unavailable(monkeypatch):
    request = _build_request(headers={"X-Real-IP": "198.51.100.30"})

    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")

    def _raise_redis_error():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(rate_limit_module, "get_redis_client", _raise_redis_error)

    allowed1, remaining1 = check_rate_limit(request, "auth_login_ip", 1, 60)
    allowed2, remaining2 = check_rate_limit(request, "auth_login_ip", 1, 60)

    assert allowed1 is True
    assert remaining1 == 0
    assert allowed2 is False
    assert remaining2 == 0


@pytest.mark.unit
def test_check_rate_limit_auto_backend_skips_redis_when_redis_url_missing(monkeypatch):
    request = _build_request(headers={"X-Real-IP": "198.51.100.31"})

    monkeypatch.setenv("RATE_LIMIT_BACKEND", "auto")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(
        rate_limit_module,
        "get_redis_client",
        lambda: (_ for _ in ()).throw(AssertionError("redis client should not be requested")),
    )

    allowed1, remaining1 = check_rate_limit(request, "auth_login_ip", 2, 60)
    allowed2, remaining2 = check_rate_limit(request, "auth_login_ip", 2, 60)
    allowed3, remaining3 = check_rate_limit(request, "auth_login_ip", 2, 60)

    assert allowed1 is True and remaining1 == 1
    assert allowed2 is True and remaining2 == 0
    assert allowed3 is False and remaining3 == 0


@pytest.mark.unit
def test_check_rate_limit_auto_backend_cooldown_skips_second_redis_attempt(monkeypatch):
    request = _build_request(headers={"X-Real-IP": "198.51.100.32"})
    calls = {"redis": 0}

    monkeypatch.setenv("RATE_LIMIT_BACKEND", "auto")
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")
    monkeypatch.setenv("RATE_LIMIT_REDIS_ERROR_COOLDOWN_SECONDS", "60")

    def _raise_redis_error():
        calls["redis"] += 1
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(rate_limit_module, "get_redis_client", _raise_redis_error)

    # First call attempts Redis and falls back to memory.
    allowed1, remaining1 = check_rate_limit(request, "auth_login_ip", 2, 60)
    # Second call should use cooldown path and skip Redis entirely.
    allowed2, remaining2 = check_rate_limit(request, "auth_login_ip", 2, 60)

    assert calls["redis"] == 1
    assert allowed1 is True and remaining1 == 1
    assert allowed2 is True and remaining2 == 0


class _FakeRedisClientNoTTL(_FakeRedisClient):
    def __init__(self):
        super().__init__()
        self.expire_calls: list[tuple[str, int]] = []

    def expire(self, key: str, seconds: int) -> bool:
        self.expire_calls.append((key, seconds))
        return super().expire(key, seconds)

    def ttl(self, key: str) -> int:
        # Force ttl<0 branch on non-first requests.
        return -1


@pytest.mark.unit
def test_check_rate_limit_redis_repairs_missing_ttl(monkeypatch):
    request = _build_request(headers={"X-Real-IP": "198.51.100.40"})
    fake_redis = _FakeRedisClientNoTTL()

    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")
    monkeypatch.setattr(rate_limit_module, "get_redis_client", lambda: fake_redis)

    allowed1, _ = check_rate_limit(request, "auth_login_ip", 3, 60)
    allowed2, _ = check_rate_limit(request, "auth_login_ip", 3, 60)

    assert allowed1 is True
    assert allowed2 is True
    assert len(fake_redis.expire_calls) >= 2


@pytest.mark.unit
def test_build_redis_rate_key_uses_custom_prefix(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REDIS_PREFIX", "zenstory_rl")
    key = rate_limit_module._build_redis_rate_key("auth_login_ip:198.51.100.50")
    assert key == "zenstory_rl:auth_login_ip:198.51.100.50"
