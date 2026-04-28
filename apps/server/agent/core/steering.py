"""
Steering message system for runtime intervention.

Allows users to inject messages into the running agent loop
for mid-execution guidance.
"""

import asyncio
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

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

    async def cleanup(self, session_id: str) -> None:
        """Remove steering queue for a session."""
        async with self._lock:
            if session_id in self._queues:
                del self._queues[session_id]
                log_with_context(
                    logger,
                    20,  # INFO
                    "Steering queue cleaned up for session",
                    session_id=session_id,
                )


# Global queue manager instance
_queue_manager = SteeringQueueManager()


async def get_steering_queue_async(session_id: str) -> SteeringQueue:
    """
    Get or create steering queue for a session (async version).

    This is the recommended method for new code.
    """
    return await _queue_manager.get_queue(session_id)


async def create_steering_queue_async(
    session_id: str,
    owner_user_id: str | None,
) -> SteeringQueue:
    """Create/get queue and bind ownership when available."""
    return await _queue_manager.get_queue(session_id, owner_user_id=owner_user_id)


async def get_steering_queue_for_user_async(session_id: str, user_id: str) -> SteeringQueue:
    """Get existing queue for a specific user without creating new session queues."""
    return await _queue_manager.get_queue_for_user(session_id, user_id)


async def cleanup_steering_queue_async(session_id: str) -> None:
    """
    Remove steering queue for a session (async version).

    This is the recommended method for new code.
    """
    await _queue_manager.cleanup(session_id)
