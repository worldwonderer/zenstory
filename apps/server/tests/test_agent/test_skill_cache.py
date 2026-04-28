"""
Tests for skill caching with TTL and LRU eviction.
"""

import asyncio
import time
import pytest

from agent.skills.loader import SkillCache
from agent.skills.schemas import Skill, SkillSource


def make_skill(name: str) -> Skill:
    """Helper to create a test skill."""
    return Skill(
        id=name.lower().replace(" ", "-"),
        name=name,
        description=f"Description for {name}",
        instructions=f"Instructions for {name}",
        source=SkillSource.BUILTIN,
    )


async def async_get(cache: SkillCache, key: str) -> list[Skill] | None:
    """Helper to get from cache asynchronously."""
    return await cache.get(key)


async def async_set(cache: SkillCache, key: str, skills: list[Skill]) -> None:
    """Helper to set cache asynchronously."""
    await cache.set(key, skills)


async def async_invalidate(cache: SkillCache, key: str | None = None) -> None:
    """Helper to invalidate cache asynchronously."""
    await cache.invalidate(key)


@pytest.mark.unit
class TestSkillCacheBasic:
    """Test basic SkillCache operations."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test basic set and get."""
        cache = SkillCache(ttl_seconds=300, max_size=100)
        skills = [make_skill("Test Skill")]

        await async_set(cache, "test-key", skills)
        result = await async_get(cache, "test-key")

        assert result is not None
        assert result == skills

    @pytest.mark.asyncio
    async def test_get_missing_key(self):
        """Test get returns None for missing key."""
        cache = SkillCache()
        result = await async_get(cache, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_single_key(self):
        """Test invalidating a single key."""
        cache = SkillCache()
        await async_set(cache, "key1", [make_skill("Skill 1")])
        await async_set(cache, "key2", [make_skill("Skill 2")])

        await async_invalidate(cache, "key1")

        result1 = await async_get(cache, "key1")
        result2 = await async_get(cache, "key2")
        assert result1 is None
        assert result2 is not None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_key(self):
        """Test invalidating nonexistent key does not raise."""
        cache = SkillCache()
        # Should not raise
        await async_invalidate(cache, "nonexistent")

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Test clearing all cache entries."""
        cache = SkillCache()
        await async_set(cache, "key1", [make_skill("Skill 1")])
        await async_set(cache, "key2", [make_skill("Skill 2")])

        await async_invalidate(cache, None)  # None clears all

        assert await async_get(cache, "key1") is None
        assert await async_get(cache, "key2") is None


@pytest.mark.unit
class TestSkillCacheTTL:
    """Test TTL expiration behavior."""

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self):
        """Test get returns value before TTL expires."""
        cache = SkillCache(ttl_seconds=10, max_size=100)  # 10 second TTL
        skills = [make_skill("Test Skill")]

        await async_set(cache, "test-key", skills)

        # Should still be available immediately
        result = await async_get(cache, "test-key")
        assert result == skills

    @pytest.mark.asyncio
    async def test_ttl_expired(self):
        """Test get returns None after TTL expires."""
        cache = SkillCache(ttl_seconds=0.1, max_size=100)  # 0.1 second TTL
        skills = [make_skill("Test Skill")]

        await async_set(cache, "test-key", skills)

        # Wait for TTL to expire
        await asyncio.sleep(0.2)

        result = await async_get(cache, "test-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_expired_entry_removed_on_get(self):
        """Test that expired entries are removed on access."""
        cache = SkillCache(ttl_seconds=0.1, max_size=100)

        await async_set(cache, "test-key", [make_skill("Test")])
        await asyncio.sleep(0.2)

        # Access should trigger removal
        await async_get(cache, "test-key")

        # Check stats - should be a miss
        stats = cache.get_stats()
        assert stats["misses"] >= 1


@pytest.mark.unit
class TestSkillCacheLRU:
    """Test LRU eviction behavior."""

    @pytest.mark.asyncio
    async def test_lru_eviction_at_capacity(self):
        """Test that LRU evicts oldest entry when at capacity."""
        cache = SkillCache(ttl_seconds=300, max_size=3)

        # Add 3 entries (fills cache)
        await async_set(cache, "key1", [make_skill("Skill 1")])
        await async_set(cache, "key2", [make_skill("Skill 2")])
        await async_set(cache, "key3", [make_skill("Skill 3")])

        # All should be present
        assert await async_get(cache, "key1") is not None
        assert await async_get(cache, "key2") is not None
        assert await async_get(cache, "key3") is not None

        # Add 4th entry - should evict key1 (oldest)
        await async_set(cache, "key4", [make_skill("Skill 4")])

        # key1 should be evicted
        assert await async_get(cache, "key1") is None
        assert await async_get(cache, "key2") is not None
        assert await async_get(cache, "key3") is not None
        assert await async_get(cache, "key4") is not None

    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self):
        """Test that accessing an entry updates its LRU position."""
        cache = SkillCache(ttl_seconds=300, max_size=3)

        await async_set(cache, "key1", [make_skill("Skill 1")])
        await async_set(cache, "key2", [make_skill("Skill 2")])
        await async_set(cache, "key3", [make_skill("Skill 3")])

        # Access key1 - should move it to most recent
        await async_get(cache, "key1")

        # Add 4th entry - should evict key2 (now oldest)
        await async_set(cache, "key4", [make_skill("Skill 4")])

        # key2 should be evicted, key1 should remain
        assert await async_get(cache, "key1") is not None
        assert await async_get(cache, "key2") is None
        assert await async_get(cache, "key3") is not None


@pytest.mark.unit
class TestSkillCacheStats:
    """Test cache statistics."""

    @pytest.mark.asyncio
    async def test_hit_miss_tracking(self):
        """Test that hits and misses are tracked."""
        cache = SkillCache()

        await async_set(cache, "key1", [make_skill("Skill 1")])

        # Hit
        await async_get(cache, "key1")
        # Miss
        await async_get(cache, "nonexistent")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        cache = SkillCache()

        await async_set(cache, "key1", [make_skill("Skill 1")])

        # 2 hits, 2 misses
        await async_get(cache, "key1")  # hit
        await async_get(cache, "key1")  # hit
        await async_get(cache, "nope1")  # miss
        await async_get(cache, "nope2")  # miss

        stats = cache.get_stats()
        assert stats["hit_rate"] == 0.5  # 50%

    @pytest.mark.asyncio
    async def test_stats_entries_count(self):
        """Test that stats reports correct entry count."""
        cache = SkillCache(max_size=10)

        await async_set(cache, "key1", [make_skill("Skill 1")])
        await async_set(cache, "key2", [make_skill("Skill 2")])

        stats = cache.get_stats()
        assert stats["size"] == 2
