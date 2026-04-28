"""
Tests for steering message system.

Tests queue operations, concurrency, and thread safety.
"""

import asyncio
from datetime import datetime

import pytest

from agent.core.steering import (
    MAX_STEERING_MESSAGE_LENGTH,
    SteeringMessage,
    SteeringQueue,
    cleanup_steering_queue_async,
    create_steering_queue_async,
    get_steering_queue_async,
    get_steering_queue_for_user_async,
    sanitize_steering_content,
)


@pytest.mark.unit
class TestSteeringSanitization:
    """Test steering message sanitization."""

    def test_sanitize_empty_content(self):
        """Test that empty content raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_steering_content("")

    def test_sanitize_whitespace_only(self):
        """Test that whitespace-only content raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_steering_content("   \n\t  ")

    def test_sanitize_control_chars(self):
        """Test that control characters are removed."""
        content = "Hello\x00World\x08Test"
        result = sanitize_steering_content(content)
        assert result == "HelloWorldTest"

    def test_sanitize_truncation(self):
        """Test that long content is truncated."""
        content = "x" * 15000
        result = sanitize_steering_content(content)
        assert len(result) == MAX_STEERING_MESSAGE_LENGTH

    def test_sanitize_preserves_spaces(self):
        """Test that normal spaces are preserved."""
        content = "  Hello World  "
        result = sanitize_steering_content(content)
        assert result == "  Hello World  "

    def test_sanitize_normal_content(self):
        """Test that normal content passes through unchanged."""
        content = "This is a normal steering message."
        result = sanitize_steering_content(content)
        assert result == content

    def test_sanitize_various_control_chars(self):
        """Test removal of various control characters."""
        # Test various control chars: null, backspace, form feed, delete
        content = "Start\x00\x08\x0c\x7fEnd"
        result = sanitize_steering_content(content)
        assert result == "StartEnd"

    def test_sanitize_keeps_newlines_and_tabs(self):
        """Test that newlines and tabs are preserved (they are valid whitespace)."""
        content = "Line1\nLine2\tTabbed"
        result = sanitize_steering_content(content)
        assert result == "Line1\nLine2\tTabbed"


@pytest.mark.unit
class TestSteeringMessage:
    """Test SteeringMessage dataclass."""

    def test_message_creation(self):
        """Test creating a steering message."""
        msg = SteeringMessage(
            id="steer-123",
            content="Change direction",
            created_at=datetime.now(),
        )
        assert msg.id == "steer-123"
        assert msg.content == "Change direction"
        assert msg.processed is False
        assert msg.processed_at is None

    def test_message_processed(self):
        """Test marking message as processed."""
        msg = SteeringMessage(
            id="steer-123",
            content="Test",
            created_at=datetime.now(),
        )
        msg.processed = True
        msg.processed_at = datetime.now()
        assert msg.processed is True
        assert msg.processed_at is not None


@pytest.mark.asyncio
@pytest.mark.unit
class TestSteeringQueue:
    """Test SteeringQueue operations."""

    async def test_queue_creation(self):
        """Test creating a steering queue."""
        queue = SteeringQueue()
        messages = await queue.peek()
        assert len(messages) == 0

    async def test_add_message(self):
        """Test adding a message to queue."""
        queue = SteeringQueue()
        msg = await queue.add("Test message")

        assert msg.id.startswith("steer-")
        assert msg.content == "Test message"
        assert msg.processed is False

    async def test_peek_messages(self):
        """Test peeking at messages."""
        queue = SteeringQueue()
        await queue.add("Message 1")
        await queue.add("Message 2")

        messages = await queue.peek()
        assert len(messages) == 2
        assert all(not m.processed for m in messages)

        # Peek again - messages should still be unprocessed
        messages2 = await queue.peek()
        assert len(messages2) == 2

    async def test_get_pending_marks_processed(self):
        """Test that get_pending marks messages as processed."""
        queue = SteeringQueue()
        await queue.add("Message 1")
        await queue.add("Message 2")

        messages = await queue.get_pending()
        assert len(messages) == 2
        assert all(m.processed for m in messages)

        # Second call should return empty (all processed)
        messages2 = await queue.get_pending()
        assert len(messages2) == 0

    async def test_get_pending_only_unprocessed(self):
        """Test get_pending only returns unprocessed messages."""
        queue = SteeringQueue()
        await queue.add("Message 1")
        await queue.add("Message 2")

        # Get one batch
        first_batch = await queue.get_pending()
        assert len(first_batch) == 2

        # Add more messages
        await queue.add("Message 3")

        # Should only get the new unprocessed one
        second_batch = await queue.get_pending()
        assert len(second_batch) == 1
        assert second_batch[0].content == "Message 3"

    async def test_clear_queue(self):
        """Test clearing the queue."""
        queue = SteeringQueue()
        await queue.add("Message 1")
        await queue.add("Message 2")

        await queue.clear()

        messages = await queue.peek()
        assert len(messages) == 0

    async def test_empty_queue_operations(self):
        """Test operations on empty queue."""
        queue = SteeringQueue()

        messages = await queue.peek()
        assert messages == []

        pending = await queue.get_pending()
        assert pending == []

        # Clear empty queue should not error
        await queue.clear()

    async def test_add_with_sanitization(self):
        """Test that add() applies sanitization."""
        queue = SteeringQueue()
        msg = await queue.add("  Hello World  \x00")
        assert msg.content == "  Hello World  "  # Control char removed, spaces kept

    async def test_add_empty_raises_error(self):
        """Test that adding empty content raises error."""
        queue = SteeringQueue()
        with pytest.raises(ValueError, match="cannot be empty"):
            await queue.add("")

    async def test_add_whitespace_raises_error(self):
        """Test that adding whitespace-only content raises error."""
        queue = SteeringQueue()
        with pytest.raises(ValueError, match="cannot be empty"):
            await queue.add("   \n\t  ")

    async def test_add_truncates_long_content(self):
        """Test that long content is truncated when added."""
        queue = SteeringQueue()
        long_content = "x" * 15000
        msg = await queue.add(long_content)
        assert len(msg.content) == MAX_STEERING_MESSAGE_LENGTH


@pytest.mark.asyncio
@pytest.mark.unit
class TestSteeringQueueConcurrency:
    """Test thread safety of steering queue."""

    async def test_concurrent_adds(self):
        """Test concurrent adds to queue."""
        queue = SteeringQueue()

        # Add messages concurrently
        tasks = [queue.add(f"Message {i}") for i in range(10)]
        messages = await asyncio.gather(*tasks)

        assert len(messages) == 10
        all_messages = await queue.peek()
        assert len(all_messages) == 10

    async def test_concurrent_add_and_get(self):
        """Test concurrent add and get operations."""
        queue = SteeringQueue()

        async def add_messages():
            for i in range(5):
                await queue.add(f"Add {i}")
                await asyncio.sleep(0.01)

        async def get_messages():
            await asyncio.sleep(0.02)
            return await queue.get_pending()

        # Run add and get concurrently
        add_task = asyncio.create_task(add_messages())
        get_task = asyncio.create_task(get_messages())

        await add_task
        messages = await get_task

        # Should have received some messages
        # (exact count depends on timing)
        assert isinstance(messages, list)

    async def test_concurrent_get_pending(self):
        """Test concurrent get_pending calls."""
        queue = SteeringQueue()
        for i in range(5):
            await queue.add(f"Message {i}")

        # Multiple concurrent get_pending calls
        results = await asyncio.gather(
            queue.get_pending(),
            queue.get_pending(),
            queue.get_pending(),
        )

        # First call gets all 5, subsequent calls get 0
        total_retrieved = sum(len(r) for r in results)
        assert total_retrieved == 5


@pytest.mark.asyncio
@pytest.mark.unit
class TestGlobalSteeringQueues:
    """Test global queue management."""

    async def test_get_steering_queue_async_creates(self):
        """Test get_steering_queue_async creates new queue."""
        # Clean up first
        await cleanup_steering_queue_async("test-session-1")

        queue = await get_steering_queue_async("test-session-1")
        assert queue is not None
        assert isinstance(queue, SteeringQueue)

        # Clean up
        await cleanup_steering_queue_async("test-session-1")

    async def test_get_steering_queue_async_returns_same(self):
        """Test get_steering_queue_async returns same queue for same session."""
        await cleanup_steering_queue_async("test-session-2")

        queue1 = await get_steering_queue_async("test-session-2")
        queue2 = await get_steering_queue_async("test-session-2")

        assert queue1 is queue2

        await cleanup_steering_queue_async("test-session-2")

    async def test_different_sessions_different_queues(self):
        """Test different sessions get different queues."""
        await cleanup_steering_queue_async("session-a")
        await cleanup_steering_queue_async("session-b")

        queue_a = await get_steering_queue_async("session-a")
        queue_b = await get_steering_queue_async("session-b")

        assert queue_a is not queue_b

        await cleanup_steering_queue_async("session-a")
        await cleanup_steering_queue_async("session-b")

    async def test_cleanup_removes_queue(self):
        """Test cleanup removes the queue."""
        # Create queue
        await get_steering_queue_async("test-session-3")

        # Cleanup
        await cleanup_steering_queue_async("test-session-3")

        # Queue should be removed from global manager
        from agent.core.steering import _queue_manager

        assert "test-session-3" not in _queue_manager._queues

    async def test_cleanup_nonexistent_queue(self):
        """Test cleanup of nonexistent queue doesn't error."""
        # Should not raise
        await cleanup_steering_queue_async("nonexistent-session")


@pytest.mark.asyncio
@pytest.mark.integration
class TestSteeringIntegration:
    """Integration tests for steering system."""

    async def test_full_workflow(self):
        """Test complete steering workflow."""
        session_id = "workflow-test"
        await cleanup_steering_queue_async(session_id)

        queue = await get_steering_queue_async(session_id)

        # Add steering message
        msg = await queue.add("Focus on the main character")
        assert msg.processed is False

        # Check pending
        pending = await queue.peek()
        assert len(pending) == 1

        # Get and process
        to_process = await queue.get_pending()
        assert len(to_process) == 1
        assert to_process[0].content == "Focus on the main character"

        # Mark processed (simulated)
        to_process[0].processed = True
        to_process[0].processed_at = datetime.now()

        # Verify no more pending
        remaining = await queue.peek()
        assert len(remaining) == 0

        await cleanup_steering_queue_async(session_id)

    async def test_multiple_sessions(self):
        """Test multiple sessions with separate queues."""
        await cleanup_steering_queue_async("multi-1")
        await cleanup_steering_queue_async("multi-2")

        queue1 = await get_steering_queue_async("multi-1")
        queue2 = await get_steering_queue_async("multi-2")

        await queue1.add("Session 1 message")
        await queue2.add("Session 2 message")

        p1 = await queue1.peek()
        p2 = await queue2.peek()

        assert len(p1) == 1
        assert len(p2) == 1
        assert p1[0].content == "Session 1 message"
        assert p2[0].content == "Session 2 message"

        await cleanup_steering_queue_async("multi-1")
        await cleanup_steering_queue_async("multi-2")

    async def test_message_lifecycle(self):
        """Test message lifecycle from creation to processed."""
        queue = SteeringQueue()

        # Create
        msg = await queue.add("Test lifecycle")
        assert msg.processed is False
        assert msg.created_at is not None
        assert msg.processed_at is None

        # Process
        pending = await queue.get_pending()
        assert len(pending) == 1
        processed_msg = pending[0]

        assert processed_msg.processed is True
        assert processed_msg.processed_at is not None
        assert processed_msg.processed_at >= processed_msg.created_at

    async def test_get_queue_for_user_authorized(self):
        """Test owned steering queue can be retrieved by owner."""
        session_id = "owned-session"
        await cleanup_steering_queue_async(session_id)
        await create_steering_queue_async(session_id, "user-a")

        try:
            queue = await get_steering_queue_for_user_async(session_id, "user-a")
            assert isinstance(queue, SteeringQueue)
        finally:
            await cleanup_steering_queue_async(session_id)

    async def test_get_queue_for_user_forbidden(self):
        """Test steering queue access is denied for non-owner."""
        session_id = "owned-session-forbidden"
        await cleanup_steering_queue_async(session_id)
        await create_steering_queue_async(session_id, "owner-user")

        try:
            with pytest.raises(PermissionError):
                await get_steering_queue_for_user_async(session_id, "intruder-user")
        finally:
            await cleanup_steering_queue_async(session_id)

    async def test_create_queue_rejects_conflicting_owner(self):
        """Creating/rebinding an existing queue with another owner should fail."""
        session_id = "owned-session-conflict"
        await cleanup_steering_queue_async(session_id)
        await create_steering_queue_async(session_id, "owner-user")

        try:
            with pytest.raises(PermissionError):
                await create_steering_queue_async(session_id, "intruder-user")
        finally:
            await cleanup_steering_queue_async(session_id)
