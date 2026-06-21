"""Tests for the Redis-backed (cross-worker) steering queue.

These simulate the production failure mode: the worker serving POST /agent/steer
is a different process from the one running the SSE stream. With the in-memory
queue that lookup misses (404 "对话会话不存在"); with Redis both workers share state.
"""

import pytest


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.ops: list[tuple[str, tuple]] = []

    def rpush(self, *args):
        self.ops.append(("rpush", args))
        return self

    def lrange(self, *args):
        self.ops.append(("lrange", args))
        return self

    def delete(self, *args):
        self.ops.append(("delete", args))
        return self

    def expire(self, *args):
        self.ops.append(("expire", args))
        return self

    def execute(self):
        results = [getattr(self.client, name)(*args) for name, args in self.ops]
        self.ops = []
        return results


class FakeRedis:
    """Minimal in-process Redis stand-in shared across "workers" in a test."""

    def __init__(self):
        self.store: dict = {}

    def ping(self):
        return True

    def set(self, key, value, ex=None, xx=False, nx=False):
        if xx and key not in self.store:
            return None
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def get(self, key):
        v = self.store.get(key)
        return v if isinstance(v, str) else None

    def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    def rpush(self, key, *vals):
        lst = self.store.get(key)
        if not isinstance(lst, list):
            lst = []
            self.store[key] = lst
        lst.extend(vals)
        return len(lst)

    def lrange(self, key, start, end):
        lst = self.store.get(key, [])
        if not isinstance(lst, list):
            return []
        return list(lst[start:]) if end == -1 else list(lst[start : end + 1])

    def expire(self, key, ttl):
        return key in self.store

    def pipeline(self, transaction=True):
        return FakePipeline(self)


@pytest.fixture
def redis_steering(monkeypatch):
    """Route steering through a single shared FakeRedis and force the Redis path."""
    import agent.core.steering as st

    fake = FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://fake:6379/0")
    monkeypatch.setattr(
        "services.infra.redis_client.get_redis_client", lambda: fake, raising=True
    )
    # Force a fresh health check (and that it resolves to "healthy").
    st._redis_health_checked_at = 0.0
    st._redis_is_healthy = False
    return st, fake


@pytest.mark.unit
@pytest.mark.asyncio
async def test_steering_message_crosses_workers(redis_steering):
    st, _fake = redis_steering

    # Worker A (the SSE stream) creates the queue.
    queue_a = await st.create_steering_queue_async("sess-1", "user-1")
    assert isinstance(queue_a, st.RedisSteeringQueue)

    # Worker B (a DIFFERENT process serving POST /steer) finds the same session
    # and enqueues a steering message.
    queue_b = await st.get_steering_queue_for_user_async("sess-1", "user-1")
    assert isinstance(queue_b, st.RedisSteeringQueue)
    await queue_b.add("把主角改名为林川")

    # Worker A's running stream drains what worker B added — the whole point.
    pending = await queue_a.get_pending()
    assert [m.content for m in pending] == ["把主角改名为林川"]

    # Draining is destructive: a second poll is empty.
    assert await queue_a.get_pending() == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_session_raises_keyerror(redis_steering):
    st, _fake = redis_steering
    # No create_* call -> the /steer endpoint must get KeyError (-> 404), not crash.
    with pytest.raises(KeyError):
        await st.get_steering_queue_for_user_async("does-not-exist", "user-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owner_mismatch_raises_permissionerror(redis_steering):
    st, _fake = redis_steering
    await st.create_steering_queue_async("sess-2", "owner-user")
    with pytest.raises(PermissionError):
        await st.get_steering_queue_for_user_async("sess-2", "attacker-user")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cleanup_removes_session(redis_steering):
    st, fake = redis_steering
    await st.create_steering_queue_async("sess-3", "user-1")
    q = await st.get_steering_queue_for_user_async("sess-3", "user-1")
    await q.add("msg")
    await st.cleanup_steering_queue_async("sess-3")
    # After cleanup the session no longer exists.
    assert fake.store == {}
    with pytest.raises(KeyError):
        await st.get_steering_queue_for_user_async("sess-3", "user-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_falls_back_to_memory_without_redis_url(monkeypatch):
    """No REDIS_URL -> in-memory path (correct for a single-worker dev server)."""
    import agent.core.steering as st

    monkeypatch.delenv("REDIS_URL", raising=False)
    st._redis_health_checked_at = 0.0
    st._redis_is_healthy = False

    queue = await st.create_steering_queue_async("sess-mem", "user-1")
    assert isinstance(queue, st.SteeringQueue)  # in-memory, not RedisSteeringQueue
    await queue.add("hi")
    same = await st.get_steering_queue_for_user_async("sess-mem", "user-1")
    pending = await same.get_pending()
    assert [m.content for m in pending] == ["hi"]
    await st.cleanup_steering_queue_async("sess-mem")
