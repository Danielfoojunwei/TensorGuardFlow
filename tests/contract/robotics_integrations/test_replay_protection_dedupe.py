"""
Contract tests for replay protection and deduplication.

Verifies that the dedupe cache correctly prevents replay attacks.
"""

import pytest
import time

from tensorguard.integrations.connectors.robotics.base import BoundedDedupeCache


class TestReplayProtectionDedupe:
    """Test replay protection via dedupe cache."""

    def test_dedupe_cache_basic_operation(self):
        """Test basic cache add and contains."""
        cache = BoundedDedupeCache(max_size=100, ttl_sec=60)

        # First add should succeed
        assert cache.add("key1") is True

        # Same key should already exist
        assert cache.contains("key1") is True

        # Second add of same key should fail
        assert cache.add("key1") is False

    def test_dedupe_cache_different_keys(self):
        """Test different keys are tracked independently."""
        cache = BoundedDedupeCache(max_size=100, ttl_sec=60)

        assert cache.add("key1") is True
        assert cache.add("key2") is True
        assert cache.add("key3") is True

        assert cache.contains("key1") is True
        assert cache.contains("key2") is True
        assert cache.contains("key3") is True
        assert cache.contains("key4") is False

    def test_dedupe_cache_expiry(self):
        """Test that entries expire after TTL."""
        cache = BoundedDedupeCache(max_size=100, ttl_sec=1)  # 1 second TTL

        assert cache.add("key1") is True
        assert cache.contains("key1") is True

        # Wait for expiry
        time.sleep(1.1)

        # Should have expired
        assert cache.contains("key1") is False

        # Should be able to add again
        assert cache.add("key1") is True

    def test_dedupe_cache_bounded_size(self):
        """Test that cache evicts when at capacity."""
        cache = BoundedDedupeCache(max_size=10, ttl_sec=60)

        # Add max_size entries
        for i in range(10):
            assert cache.add(f"key{i}") is True

        assert cache.size() == 10

        # Add more - should evict old entries
        for i in range(10, 20):
            cache.add(f"key{i}")

        # Size should still be bounded
        assert cache.size() <= 10

    def test_dedupe_cache_clear(self):
        """Test clearing the cache."""
        cache = BoundedDedupeCache(max_size=100, ttl_sec=60)

        cache.add("key1")
        cache.add("key2")

        assert cache.size() == 2

        cache.clear()

        assert cache.size() == 0
        assert cache.contains("key1") is False

    def test_dedupe_prevents_replay(self):
        """Test that dedupe effectively prevents replays."""
        cache = BoundedDedupeCache(max_size=1000, ttl_sec=300)

        # Simulate receiving a signal
        signal_dedupe_key = "inorbit:evt_123:robot-001:1706443200"

        # First time - should be allowed
        is_new = cache.add(signal_dedupe_key)
        assert is_new is True

        # Same signal again (replay) - should be blocked
        is_new = cache.add(signal_dedupe_key)
        assert is_new is False

    def test_dedupe_key_format_variations(self):
        """Test different dedupe key formats."""
        cache = BoundedDedupeCache(max_size=100, ttl_sec=60)

        # Different key formats should all work
        keys = [
            "inorbit:evt_123",
            "formant:device-001:12345",
            "foxglove:abc123:safety_stop:1706443200",
            "generic:sha256:abcdef123456",
        ]

        for key in keys:
            assert cache.add(key) is True
            assert cache.contains(key) is True

    def test_dedupe_cache_thread_safety_note(self):
        """Verify cache is designed for single-threaded use."""
        cache = BoundedDedupeCache()

        # The _lock_free attribute indicates single-threaded design
        assert cache._lock_free is True

        # For production multi-instance deployments, would need
        # distributed cache (Redis, etc.)

    def test_eviction_removes_oldest_entries(self):
        """Test that eviction removes oldest entries."""
        cache = BoundedDedupeCache(max_size=5, ttl_sec=60)

        # Add entries with small delays
        for i in range(5):
            cache.add(f"key{i}")
            time.sleep(0.01)

        # All 5 should exist
        for i in range(5):
            assert cache.contains(f"key{i}") is True

        # Add more to trigger eviction
        for i in range(5, 10):
            cache.add(f"key{i}")

        # Newer keys should exist
        for i in range(5, 10):
            assert cache.contains(f"key{i}") is True

        # Some older keys should have been evicted
        existing_old = sum(1 for i in range(5) if cache.contains(f"key{i}"))
        assert existing_old < 5
