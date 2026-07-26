"""
Steering message system for runtime intervention.

Allows users to inject messages into the running agent loop
for mid-execution guidance.
"""

import asyncio
import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)

# Constants for message validation
MAX_STEERING_MESSAGE_LENGTH: Final[int] = 10000
CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def sanitize_steering_content(content: str, max_length: int = MAX_STEERING_MESSAGE_LENGTH) -> str:
    """
    Sanitize and validate steering message content.

    Args:
        content: Raw message content
        max_length: Maximum allowed length

    Returns:
        Sanitized content

    Raises:
        ValueError: If content is empty or only whitespace
    """
    if not content or not content.strip():
        raise ValueError("Steering message content cannot be empty")

    # Remove control characters
    sanitized = CONTROL_CHAR_PATTERN.sub('', content)

    # Truncate if too long
    if len(sanitized) > max_length:
        log_with_context(
            logger, 30,  # WARNING
            "Steering message truncated",
            original_length=len(sanitized),
            max_length=max_length,
        )
        sanitized = sanitized[:max_length]

    return sanitized


@dataclass
class SteeringMessage:
    """A steering message from the user."""
    id: str
    content: str
    created_at: datetime
    processed: bool = False
    processed_at: datetime | None = None


@dataclass
class SteeringQueue:
    """
    Async-safe queue for steering messages.
    """
    _messages: deque[SteeringMessage] = field(default_factory=deque)
    _lock: asyncio.Lock = field(init=False)

    def __post_init__(self):
        self._lock = asyncio.Lock()

    async def add(self, content: str) -> SteeringMessage:
        """Add a steering message to the queue with sanitization."""
        # Sanitize content before adding
        sanitized_content = sanitize_steering_content(content)

        async with self._lock:
            msg = SteeringMessage(
                id=f"steer-{datetime.now().timestamp()}",
                content=sanitized_content,
                created_at=datetime.now(),
            )
            self._messages.append(msg)
            log_with_context(
                logger,
                20,  # INFO
                "Steering message added",
                message_id=msg.id,
                content_preview=sanitized_content[:50],
            )
            return msg

    async def get_pending(self) -> list[SteeringMessage]:
        """Get all pending steering messages and mark as processed."""
        async with self._lock:
            pending = [m for m in self._messages if not m.processed]
            for m in pending:
                m.processed = True
                m.processed_at = datetime.now()
            if pending:
                log_with_context(
                    logger,
                    20,  # INFO
                    "Steering messages retrieved and marked processed",
                    count=len(pending),
                )
            return pending

    async def peek(self) -> list[SteeringMessage]:
        """Peek at pending messages without marking processed."""
        async with self._lock:
            return [m for m in self._messages if not m.processed]

    async def clear(self) -> None:
        """Clear all messages."""
        async with self._lock:
            self._messages.clear()
            log_with_context(logger, 20, "Steering queue cleared")


@dataclass
class SteeringQueueEntry:
    """Metadata wrapper for a steering queue session."""

    queue: SteeringQueue
    owner_user_id: str | None = None
    # 同一 chat session 的并发 stream run 共享同一个队列，但生命周期以 run
    # 为单位：cleanup 只在最后一个持有 run 释放后才真正删除队列，避免先结
    # 束的 run 删掉另一个仍在流式生成的 run 正在使用的队列。
    active_run_ids: set[str] = field(default_factory=set)


class SteeringQueueManager:
    """
    Async manager for all session steering queues.

    Uses asyncio.Lock for consistent concurrency model.
    """

    def __init__(self):
        self._queues: dict[str, SteeringQueueEntry] = {}
        self._lock = asyncio.Lock()

    async def get_queue(
        self,
        session_id: str,
        owner_user_id: str | None = None,
        create_if_missing: bool = True,
        run_id: str | None = None,
    ) -> SteeringQueue:
        """Get or create steering queue for a session."""
        async with self._lock:
            entry = self._queues.get(session_id)
            if entry is None:
                if not create_if_missing:
                    raise KeyError(session_id)
                entry = SteeringQueueEntry(
                    queue=SteeringQueue(),
                    owner_user_id=owner_user_id,
                )
                self._queues[session_id] = entry
                log_with_context(
                    logger,
                    20,  # INFO
                    "Steering queue created for session",
                    session_id=session_id,
                    owner_user_id=owner_user_id,
                )

            if (
                owner_user_id is not None
                and entry.owner_user_id is not None
                and entry.owner_user_id != owner_user_id
            ):
                log_with_context(
                    logger,
                    30,  # WARNING
                    "Steering queue owner mismatch",
                    session_id=session_id,
                    requested_owner_user_id=owner_user_id,
                    bound_owner_user_id=entry.owner_user_id,
                )
                raise PermissionError(
                    f"Steering session {session_id} does not belong to user {owner_user_id}"
                )

            # Backfill legacy ownerless sessions when an owner is first known.
            if entry.owner_user_id is None and owner_user_id is not None:
                entry.owner_user_id = owner_user_id
                log_with_context(
                    logger,
                    20,
                    "Steering queue owner bound",
                    session_id=session_id,
                    owner_user_id=owner_user_id,
                )

            if run_id:
                entry.active_run_ids.add(run_id)

            return entry.queue

    async def get_queue_for_user(self, session_id: str, user_id: str) -> SteeringQueue:
        """Get queue only if it belongs to the requesting user."""
        async with self._lock:
            entry = self._queues.get(session_id)
            if entry is None:
                raise KeyError(session_id)
            if entry.owner_user_id is not None and entry.owner_user_id != user_id:
                raise PermissionError(
                    f"Steering session {session_id} does not belong to user {user_id}"
                )
            # Backfill ownerless entry to first authenticated owner.
            if entry.owner_user_id is None:
                entry.owner_user_id = user_id
                log_with_context(
                    logger,
                    20,
                    "Steering queue owner bound from authorized access",
                    session_id=session_id,
                    owner_user_id=user_id,
                )
            return entry.queue

    async def cleanup(self, session_id: str, run_id: str | None = None) -> None:
        """Release a run's hold on the queue; delete only when no runs remain.

        run_id 为 None 时保持旧语义：无条件删除整个队列。
        """
        async with self._lock:
            entry = self._queues.get(session_id)
            if entry is None:
                return
            if run_id is not None:
                entry.active_run_ids.discard(run_id)
                if entry.active_run_ids:
                    log_with_context(
                        logger,
                        20,  # INFO
                        "Steering queue retained; other runs still active",
                        session_id=session_id,
                        run_id=run_id,
                        active_runs=len(entry.active_run_ids),
                    )
                    return
            del self._queues[session_id]
            log_with_context(
                logger,
                20,  # INFO
                "Steering queue cleaned up for session",
                session_id=session_id,
            )


# ---------------------------------------------------------------------------
# Redis-backed steering (cross-worker)
#
# The in-memory SteeringQueueManager above only works within a SINGLE process.
# Production runs multiple uvicorn workers (WEB_CONCURRENCY), so the worker that
# serves POST /agent/steer is usually NOT the worker running the SSE stream that
# created the queue — the lookup misses and the user gets a 404 "对话会话不存在".
# When Redis is configured we keep the per-session owner + pending messages in
# Redis so every worker sees the same queue. Dev without REDIS_URL falls back to
# the in-memory manager, which is correct for a single worker.
# ---------------------------------------------------------------------------

_STEERING_TTL_S: Final[int] = 3600  # session keys expire after 1h of inactivity
_REDIS_HEALTH_TTL_S: Final[float] = 30.0

_redis_health_checked_at: float = 0.0
_redis_is_healthy: bool = False


def _owner_key(session_id: str) -> str:
    return f"steering:owner:{session_id}"


def _msgs_key(session_id: str) -> str:
    return f"steering:msgs:{session_id}"


def _runs_key(session_id: str) -> str:
    return f"steering:runs:{session_id}"


def _redis_available_sync() -> bool:
    """Whether to use Redis for steering (configured + reachable), cached briefly."""
    global _redis_health_checked_at, _redis_is_healthy
    # Mirror the rate-limiter's "auto" rule: only use Redis when explicitly
    # configured, so dev without a local Redis doesn't pay a connect timeout.
    if not os.getenv("REDIS_URL"):
        return False
    now = time.monotonic()
    if now < _redis_health_checked_at + _REDIS_HEALTH_TTL_S:
        return _redis_is_healthy
    try:
        from services.infra.redis_client import get_redis_client

        get_redis_client().ping()
        healthy = True
    except Exception as exc:  # noqa: BLE001 — any failure means fall back to memory
        healthy = False
        log_with_context(
            logger,
            30,  # WARNING
            "Steering Redis unavailable; falling back to in-memory queue "
            "(cross-worker steering will not work under multiple workers)",
            error=str(exc),
            error_type=type(exc).__name__,
        )
    _redis_is_healthy = healthy
    _redis_health_checked_at = now
    return healthy


async def _redis_available() -> bool:
    return await asyncio.to_thread(_redis_available_sync)


def _parse_created_at(raw: Any) -> datetime:
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now()


class RedisSteeringQueue:
    """Steering queue backed by Redis so all workers share the same messages."""

    def __init__(self, session_id: str):
        self.session_id = session_id

    async def add(self, content: str) -> SteeringMessage:
        sanitized = sanitize_steering_content(content)
        msg = SteeringMessage(
            id=f"steer-{datetime.now().timestamp()}",
            content=sanitized,
            created_at=datetime.now(),
        )
        await asyncio.to_thread(self._add_sync, msg)
        log_with_context(
            logger, 20, "Steering message added (redis)",
            session_id=self.session_id, message_id=msg.id,
            content_preview=sanitized[:50],
        )
        return msg

    def _add_sync(self, msg: SteeringMessage) -> None:
        from services.infra.redis_client import get_redis_client

        client = get_redis_client()
        payload = json.dumps(
            {"id": msg.id, "content": msg.content, "created_at": msg.created_at.isoformat()}
        )
        pipe = client.pipeline()
        pipe.rpush(_msgs_key(self.session_id), payload)
        pipe.expire(_msgs_key(self.session_id), _STEERING_TTL_S)
        pipe.expire(_owner_key(self.session_id), _STEERING_TTL_S)
        pipe.expire(_runs_key(self.session_id), _STEERING_TTL_S)
        pipe.execute()

    async def get_pending(self) -> list[SteeringMessage]:
        raws = await asyncio.to_thread(self._pop_all_sync)
        messages = [m for m in (self._deserialize(raw) for raw in raws) if m is not None]
        if messages:
            log_with_context(
                logger, 20, "Steering messages retrieved (redis)",
                session_id=self.session_id, count=len(messages),
            )
        return messages

    def _pop_all_sync(self) -> list[str]:
        from services.infra.redis_client import get_redis_client

        client = get_redis_client()
        # Atomically read all queued messages and clear them in one transaction.
        # get_pending() is polled when an agent run starts (initial injection),
        # at tool-output boundaries inside a run, at agent boundaries in the
        # workflow graph, and once more before the stream saves history, so
        # refreshing the owner/runs key TTLs here acts as a poll-driven
        # heartbeat that keeps the session alive for the whole stream instead
        # of letting it expire after the fixed 1h TTL mid-run (which would 404
        # subsequent steering posts).
        pipe = client.pipeline(transaction=True)
        pipe.lrange(_msgs_key(self.session_id), 0, -1)
        pipe.delete(_msgs_key(self.session_id))
        pipe.expire(_owner_key(self.session_id), _STEERING_TTL_S)
        pipe.expire(_runs_key(self.session_id), _STEERING_TTL_S)
        results = pipe.execute()
        return list(results[0] or [])

    async def peek(self) -> list[SteeringMessage]:
        raws = await asyncio.to_thread(self._peek_sync)
        return [m for m in (self._deserialize(raw) for raw in raws) if m is not None]

    def _peek_sync(self) -> list[str]:
        from services.infra.redis_client import get_redis_client

        return list(get_redis_client().lrange(_msgs_key(self.session_id), 0, -1) or [])

    async def clear(self) -> None:
        from services.infra.redis_client import get_redis_client

        await asyncio.to_thread(lambda: get_redis_client().delete(_msgs_key(self.session_id)))

    @staticmethod
    def _deserialize(raw: str) -> SteeringMessage | None:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
        content = str(data.get("content") or "")
        if not content:
            return None
        return SteeringMessage(
            id=str(data.get("id") or ""),
            content=content,
            created_at=_parse_created_at(data.get("created_at")),
            processed=True,
            processed_at=datetime.now(),
        )


def _redis_create_sync(
    session_id: str,
    owner_user_id: str | None,
    run_id: str | None = None,
) -> None:
    from services.infra.redis_client import get_redis_client

    # 注册必须和释放（_RELEASE_RUN_SCRIPT）互相原子：若拆成 SET owner 与
    # SADD runs 两次 round-trip，另一个 worker 上并发结束的 run 会整段插在
    # 中间执行释放（SREM → SCARD==0 → DEL owner/msgs/runs），结果本 run 注册
    # 完成后 runs={本 run} 而 owner 已被删——本 run 剩余时间里所有
    # POST /agent/steer 都 404（_add_sync/_pop_all_sync 只 EXPIRE，不会重建
    # owner 键），并且已排队未消费的 steering 消息随 msgs 键一起丢失。
    # MULTI/EXEC 让释放脚本只能看到「注册前」或「注册后」两种状态。
    client = get_redis_client()
    pipe = client.pipeline(transaction=True)
    if run_id:
        # 记录持有队列的 run：同一 session 的并发 run 共享 owner/msgs 键，
        # cleanup 只在最后一个 run 释放时才真正删除（见 _RELEASE_RUN_SCRIPT）。
        # 先写 runs 再写 owner：即使将来被拆回多条命令，也不会留下
        # 「owner 已写、runs 未写」这个最坏顺序。
        pipe.sadd(_runs_key(session_id), run_id)
        pipe.expire(_runs_key(session_id), _STEERING_TTL_S)
    if owner_user_id:
        # The session owner starts the stream they own (session_id is their
        # chat_session.id), so binding the owner here is authoritative.
        pipe.set(_owner_key(session_id), owner_user_id, ex=_STEERING_TTL_S)
    else:
        # 调用方不知道 owner 时（get_steering_queue_async）只在键缺失时占位：
        # nx=True 保证不会把已绑定的真实 owner 降级成空串，否则
        # get_steering_queue_for_user_async 会跳过 owner 校验并把队列
        # backfill 给任意请求者。
        pipe.set(_owner_key(session_id), "", ex=_STEERING_TTL_S, nx=True)
        pipe.expire(_owner_key(session_id), _STEERING_TTL_S)
    pipe.execute()


def _redis_get_owner_sync(session_id: str) -> str | None:
    from services.infra.redis_client import get_redis_client

    return get_redis_client().get(_owner_key(session_id))


def _redis_backfill_owner_sync(session_id: str, user_id: str) -> None:
    from services.infra.redis_client import get_redis_client

    # xx=True: only set when the key still exists (don't resurrect a cleaned session).
    get_redis_client().set(_owner_key(session_id), user_id, ex=_STEERING_TTL_S, xx=True)


# Lua 脚本保证「移除本 run 的持有 → 判断是否还有其它 run → 删除」在 Redis
# 端原子执行：非原子的 SREM/SCARD/DEL 序列之间，另一个 worker 上的并发 run
# 可能刚完成注册，会把它正在使用的队列误删。
_RELEASE_RUN_SCRIPT: Final[str] = """
redis.call('SREM', KEYS[1], ARGV[1])
if redis.call('SCARD', KEYS[1]) == 0 then
    redis.call('DEL', KEYS[1], KEYS[2], KEYS[3])
    return 1
end
return 0
"""


def _redis_cleanup_sync(session_id: str, run_id: str | None = None) -> None:
    from services.infra.redis_client import get_redis_client

    client = get_redis_client()
    if not run_id:
        # 旧语义：无条件删除（测试/运维路径）。
        client.delete(_owner_key(session_id), _msgs_key(session_id), _runs_key(session_id))
        return
    client.eval(
        _RELEASE_RUN_SCRIPT,
        3,
        _runs_key(session_id),
        _owner_key(session_id),
        _msgs_key(session_id),
        run_id,
    )


# Global in-memory queue manager (fallback for single-worker / no-Redis dev).
_queue_manager = SteeringQueueManager()


async def get_steering_queue_async(session_id: str) -> Any:
    """Get or create steering queue for a session (async version).

    不绑定 owner：仅在 owner 键缺失时占位，已绑定的 owner 保持不变。生产入口
    请用 create_steering_queue_async（写入真实 owner）或
    get_steering_queue_for_user_async（校验 owner）。
    """
    if await _redis_available():
        await asyncio.to_thread(_redis_create_sync, session_id, None)
        return RedisSteeringQueue(session_id)
    return await _queue_manager.get_queue(session_id)


async def create_steering_queue_async(
    session_id: str,
    owner_user_id: str | None,
    run_id: str | None = None,
) -> Any:
    """Create/get queue and bind ownership when available.

    run_id 标识一次 stream run 对队列的持有：同一 session 的并发 run 共享
    队列，cleanup 传入相同 run_id 时只释放自己的持有。
    """
    if await _redis_available():
        await asyncio.to_thread(_redis_create_sync, session_id, owner_user_id, run_id)
        return RedisSteeringQueue(session_id)
    return await _queue_manager.get_queue(
        session_id, owner_user_id=owner_user_id, run_id=run_id
    )


async def get_steering_queue_for_user_async(session_id: str, user_id: str) -> Any:
    """Get an existing queue for a user; KeyError if absent, PermissionError on mismatch."""
    if await _redis_available():
        owner = await asyncio.to_thread(_redis_get_owner_sync, session_id)
        if owner is None:
            raise KeyError(session_id)
        if owner and owner != user_id:
            raise PermissionError(
                f"Steering session {session_id} does not belong to user {user_id}"
            )
        if not owner:
            await asyncio.to_thread(_redis_backfill_owner_sync, session_id, user_id)
        return RedisSteeringQueue(session_id)
    return await _queue_manager.get_queue_for_user(session_id, user_id)


async def cleanup_steering_queue_async(session_id: str, run_id: str | None = None) -> None:
    """Release a run's hold on the steering queue (async version).

    带 run_id 时只释放该 run 的持有，最后一个持有者退出才真正删除；
    不带 run_id 保持旧语义，无条件删除——会连带删掉其它并发 run 正在使用的
    队列，因此仅用于测试/运维清理，生产路径（service.py）始终传 run_id。
    """
    if await _redis_available():
        await asyncio.to_thread(_redis_cleanup_sync, session_id, run_id)
        return
    await _queue_manager.cleanup(session_id, run_id=run_id)
