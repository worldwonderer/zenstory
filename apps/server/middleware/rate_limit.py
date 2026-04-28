"""
Rate Limiting - Simple in-memory rate limiter with proxy support.
"""
import logging
import os
import time
from collections import defaultdict
from ipaddress import ip_address

from fastapi import HTTPException, Request, status

from services.infra.redis_client import get_redis_client
from utils.logger import get_logger, log_with_context

# In-memory fallback store
_rate_limit_store: dict = defaultdict(list)
_redis_retry_after_monotonic: float = 0.0

logger = get_logger(__name__)


def _parse_ip(candidate: str | None) -> str | None:
    """Return normalized IP if valid, otherwise None."""
    if not candidate:
        return None

    raw = candidate.strip()
    if not raw:
        return None

    if raw.startswith("[") and "]" in raw:
        raw = raw[1:raw.index("]")]

    try:
        return str(ip_address(raw))
    except ValueError:
        # Handle common IPv4 with port format: "1.2.3.4:5678"
        if raw.count(":") == 1:
            maybe_host, _sep, _port = raw.partition(":")
            try:
                return str(ip_address(maybe_host))
            except ValueError:
                return None
        return None


def get_client_ip(request: Request) -> str:
    """Extract client IP with Railway-aware proxy header priority."""
    # Railway sets X-Real-IP to the original client IP.
    real_ip = _parse_ip(request.headers.get("X-Real-IP"))
    if real_ip:
        return real_ip

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        for token in forwarded.split(","):
            parsed = _parse_ip(token)
            if parsed:
                return parsed

    client_host = request.client.host if request.client else None
    return _parse_ip(client_host) or "unknown"


def _get_rate_limit_backend() -> str:
    """
    Read rate-limit storage backend.

    - memory: in-process dict
    - redis: redis first, memory fallback on errors
    - auto: redis when REDIS_URL is configured, otherwise memory
    """
    return os.getenv("RATE_LIMIT_BACKEND", "auto").strip().lower()


def _get_redis_error_cooldown_seconds() -> int:
    raw = os.getenv("RATE_LIMIT_REDIS_ERROR_COOLDOWN_SECONDS", "30").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def _build_redis_rate_key(rate_key: str) -> str:
    prefix = os.getenv("RATE_LIMIT_REDIS_PREFIX", "rate_limit").strip() or "rate_limit"
    return f"{prefix}:{rate_key}"


def _should_try_redis() -> bool:
    global _redis_retry_after_monotonic

    backend = _get_rate_limit_backend()
    if backend == "memory":
        return False

    if backend == "redis":
        return True

    # auto mode: use redis only when REDIS_URL exists and retry window is open
    if not os.getenv("REDIS_URL"):
        return False

    return time.monotonic() >= _redis_retry_after_monotonic


def _record_redis_failure(error: Exception) -> None:
    global _redis_retry_after_monotonic
    _redis_retry_after_monotonic = (
        time.monotonic() + _get_redis_error_cooldown_seconds()
    )
    log_with_context(
        logger,
        logging.WARNING,
        "Rate limit Redis backend unavailable; falling back to in-memory store",
        error=str(error),
        error_type=type(error).__name__,
        retry_after_seconds=_get_redis_error_cooldown_seconds(),
    )


def _check_rate_limit_redis(
    rate_key: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int] | None:
    """
    Check rate limit via Redis.

    Returns None when Redis backend should be skipped/fallback.
    """
    if not _should_try_redis():
        return None

    try:
        client = get_redis_client()
        redis_key = _build_redis_rate_key(rate_key)

        current_count = int(client.incr(redis_key))
        if current_count == 1:
            client.expire(redis_key, window_seconds)
        else:
            ttl = int(client.ttl(redis_key))
            if ttl < 0:
                client.expire(redis_key, window_seconds)

        if current_count > max_requests:
            return False, 0

        return True, max_requests - current_count
    except Exception as exc:  # pragma: no cover - depends on runtime infra
        _record_redis_failure(exc)
        return None


def check_rate_limit(
    request: Request,
    key: str,
    max_requests: int,
    window_seconds: int,
    *,
    include_client_ip: bool = True,
) -> tuple[bool, int]:
    """
    Check rate limit for a key.

    For API-key-authenticated requests (X-Agent-API-Key header present),
    rate limits per API key prefix instead of client IP.

    Returns: (allowed, remaining_requests)
    """
    agent_key = request.headers.get("X-Agent-API-Key")
    if agent_key:
        rate_key = f"{key}:ak_{agent_key[:8]}"
    elif include_client_ip:
        client_ip = get_client_ip(request)
        rate_key = f"{key}:{client_ip}"
    else:
        rate_key = key

    redis_result = _check_rate_limit_redis(
        rate_key=rate_key,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    if redis_result is not None:
        return redis_result

    now = time.time()
    window_start = now - window_seconds

    # Clean old entries
    _rate_limit_store[rate_key] = [
        t for t in _rate_limit_store[rate_key] if t > window_start
    ]

    # Check limit
    if len(_rate_limit_store[rate_key]) >= max_requests:
        return False, 0

    # Record request
    _rate_limit_store[rate_key].append(now)
    return True, max_requests - len(_rate_limit_store[rate_key])


def require_rate_limit(key: str, max_requests: int, window_seconds: int):
    """Decorator-like function to enforce rate limiting."""
    def check(request: Request):
        allowed, remaining = check_rate_limit(request, key, max_requests, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
        return remaining
    return check
