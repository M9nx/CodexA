"""Phase 22 — LLM Caching + Rate Limiting.

Tests verify:
  1. LLMCache — in-memory and disk-backed caching with TTL expiration
  2. CacheStats — hit/miss/eviction tracking
  3. RateLimiter — sliding-window RPM/TPM enforcement
  4. RateLimitExceeded — exception behaviour
  5. CachedProvider — transparent wrapper around any LLMProvider
  6. LLMConfig — new cache/rate-limit config fields
  7. _wrap_provider integration — CLI commands wire up caching
  8. End-to-end — full caching + rate limiting flow
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from semantic_code_intelligence.llm.cache import CacheStats, LLMCache
from semantic_code_intelligence.llm.cached_provider import CachedProvider
from semantic_code_intelligence.llm.mock_provider import MockProvider
from semantic_code_intelligence.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
)
from semantic_code_intelligence.llm.rate_limiter import (
    RateLimitExceeded,
    RateLimiter,
    RateLimiterStats,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC = _PROJECT_ROOT / "semantic_code_intelligence"


# ═══════════════════════════════════════════════════════════════════════════
# 1 — LLMCache: core operations
# ═══════════════════════════════════════════════════════════════════════════


class TestLLMCacheBasic:
    """Basic get/put/clear operations."""

    def test_cache_miss_returns_none(self) -> None:
        cache = LLMCache()
        result = cache.get("openai", "gpt-4", prompt="hello")
        assert result is None

    def test_cache_put_and_get(self) -> None:
        cache = LLMCache()
        response = LLMResponse(content="world", model="gpt-4", provider="openai")
        cache.put(response, "openai", "gpt-4", prompt="hello")
        cached = cache.get("openai", "gpt-4", prompt="hello")
        assert cached is not None
        assert cached.content == "world"

    def test_cache_put_get_with_messages(self) -> None:
        cache = LLMCache()
        msgs = [LLMMessage(role=MessageRole.USER, content="hi")]
        response = LLMResponse(content="hello!", model="gpt-4", provider="openai")
        cache.put(response, "openai", "gpt-4", messages=msgs)
        cached = cache.get("openai", "gpt-4", messages=msgs)
        assert cached is not None
        assert cached.content == "hello!"

    def test_cache_different_prompts_separate(self) -> None:
        cache = LLMCache()
        r1 = LLMResponse(content="a", model="m", provider="p")
        r2 = LLMResponse(content="b", model="m", provider="p")
        cache.put(r1, "p", "m", prompt="x")
        cache.put(r2, "p", "m", prompt="y")
        assert cache.get("p", "m", prompt="x") is not None
        assert cache.get("p", "m", prompt="x").content == "a"  # type: ignore[union-attr]
        assert cache.get("p", "m", prompt="y").content == "b"  # type: ignore[union-attr]

    def test_cache_clear(self) -> None:
        cache = LLMCache()
        cache.put(LLMResponse(content="x"), "p", "m", prompt="q")
        assert cache.size == 1
        cache.clear()
        assert cache.size == 0
        assert cache.get("p", "m", prompt="q") is None

    def test_cache_size_property(self) -> None:
        cache = LLMCache()
        assert cache.size == 0
        cache.put(LLMResponse(content="x"), "p", "m", prompt="q1")
        assert cache.size == 1
        cache.put(LLMResponse(content="y"), "p", "m", prompt="q2")
        assert cache.size == 2

    def test_cache_different_temperature_separate_keys(self) -> None:
        cache = LLMCache()
        r1 = LLMResponse(content="cold")
        r2 = LLMResponse(content="hot")
        cache.put(r1, "p", "m", prompt="q", temperature=0.0)
        cache.put(r2, "p", "m", prompt="q", temperature=1.0)
        assert cache.get("p", "m", prompt="q", temperature=0.0).content == "cold"  # type: ignore[union-attr]
        assert cache.get("p", "m", prompt="q", temperature=1.0).content == "hot"  # type: ignore[union-attr]

    def test_cache_different_max_tokens_separate_keys(self) -> None:
        cache = LLMCache()
        r1 = LLMResponse(content="short")
        r2 = LLMResponse(content="long")
        cache.put(r1, "p", "m", prompt="q", max_tokens=100)
        cache.put(r2, "p", "m", prompt="q", max_tokens=4000)
        assert cache.get("p", "m", prompt="q", max_tokens=100).content == "short"  # type: ignore[union-attr]
        assert cache.get("p", "m", prompt="q", max_tokens=4000).content == "long"  # type: ignore[union-attr]


class TestLLMCacheTTL:
    """TTL expiration tests."""

    def test_expired_entry_returns_none(self) -> None:
        cache = LLMCache(ttl_hours=0)  # 0 hours = immediate expiry
        cache.put(LLMResponse(content="old"), "p", "m", prompt="q")
        # Force timestamp to the past
        for key in cache._entries:
            cache._entries[key]["timestamp"] = time.time() - 1
        result = cache.get("p", "m", prompt="q")
        assert result is None

    def test_non_expired_entry_returned(self) -> None:
        cache = LLMCache(ttl_hours=24)
        cache.put(LLMResponse(content="fresh"), "p", "m", prompt="q")
        result = cache.get("p", "m", prompt="q")
        assert result is not None
        assert result.content == "fresh"

    def test_ttl_eviction_increments_stats(self) -> None:
        cache = LLMCache(ttl_hours=0)
        cache.put(LLMResponse(content="old"), "p", "m", prompt="q")
        for key in cache._entries:
            cache._entries[key]["timestamp"] = time.time() - 1
        cache.get("p", "m", prompt="q")  # triggers eviction
        assert cache.stats.evictions == 1
        assert cache.stats.misses == 1


class TestLLMCacheEviction:
    """Max-entry eviction tests."""

    def test_evicts_oldest_when_over_max(self) -> None:
        cache = LLMCache(max_entries=2)
        cache.put(LLMResponse(content="a"), "p", "m", prompt="q1")
        time.sleep(0.01)  # ensure distinct timestamps
        cache.put(LLMResponse(content="b"), "p", "m", prompt="q2")
        time.sleep(0.01)
        cache.put(LLMResponse(content="c"), "p", "m", prompt="q3")
        # "a" should have been evicted
        assert cache.size == 2
        assert cache.get("p", "m", prompt="q1") is None
        assert cache.get("p", "m", prompt="q2") is not None
        assert cache.get("p", "m", prompt="q3") is not None

    def test_eviction_stats_tracked(self) -> None:
        cache = LLMCache(max_entries=1)
        cache.put(LLMResponse(content="a"), "p", "m", prompt="q1")
        cache.put(LLMResponse(content="b"), "p", "m", prompt="q2")
        assert cache.stats.evictions >= 1


class TestCacheStats:
    """CacheStats dataclass."""

    def test_initial_stats(self) -> None:
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.size == 0
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        stats = CacheStats(hits=3, misses=1)
        assert stats.hit_rate == 75.0

    def test_hit_rate_zero_total(self) -> None:
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_to_dict(self) -> None:
        stats = CacheStats(hits=5, misses=2, evictions=1, size=10)
        d = stats.to_dict()
        assert d["hits"] == 5
        assert d["misses"] == 2
        assert d["evictions"] == 1
        assert d["size"] == 10
        assert "hit_rate" in d

    def test_cache_stats_updated_on_hit(self) -> None:
        cache = LLMCache()
        cache.put(LLMResponse(content="x"), "p", "m", prompt="q")
        cache.get("p", "m", prompt="q")
        assert cache.stats.hits == 1

    def test_cache_stats_updated_on_miss(self) -> None:
        cache = LLMCache()
        cache.get("p", "m", prompt="missing")
        assert cache.stats.misses == 1


class TestLLMCachePersistence:
    """Disk persistence (save/load)."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=str(tmp_path), ttl_hours=24)
        cache.put(LLMResponse(content="saved", model="m", provider="p"), "p", "m", prompt="q")
        cache.save()

        cache2 = LLMCache(cache_dir=str(tmp_path), ttl_hours=24)
        result = cache2.get("p", "m", prompt="q")
        assert result is not None
        assert result.content == "saved"

    def test_save_creates_file(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=str(tmp_path))
        cache.put(LLMResponse(content="x"), "p", "m", prompt="q")
        cache.save()
        assert (tmp_path / "llm_cache.json").exists()

    def test_load_skips_expired(self, tmp_path: Path) -> None:
        # Write a cache file with old timestamps
        data = {
            "abc123": {
                "response": {"content": "old", "model": "", "provider": "", "usage": {}},
                "timestamp": time.time() - 100000,
                "provider": "p",
                "model": "m",
            }
        }
        (tmp_path / "llm_cache.json").write_text(json.dumps(data))
        cache = LLMCache(cache_dir=str(tmp_path), ttl_hours=1)
        assert cache.size == 0  # expired entries not loaded

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "llm_cache.json").write_text("not json!")
        cache = LLMCache(cache_dir=str(tmp_path))
        assert cache.size == 0

    def test_load_nonexistent_dir(self, tmp_path: Path) -> None:
        cache = LLMCache(cache_dir=str(tmp_path / "nonexistent"))
        assert cache.size == 0

    def test_no_cache_dir_save_noop(self) -> None:
        cache = LLMCache()
        cache.put(LLMResponse(content="x"), "p", "m", prompt="q")
        cache.save()  # Should not raise


class TestLLMCacheKeyDeterminism:
    """Cache key generation is deterministic."""

    def test_same_input_same_key(self) -> None:
        msgs = [LLMMessage(role=MessageRole.USER, content="hello")]
        k1 = LLMCache._make_key("openai", "gpt-4", msgs, None, 0.2, 2048)
        k2 = LLMCache._make_key("openai", "gpt-4", msgs, None, 0.2, 2048)
        assert k1 == k2

    def test_different_provider_different_key(self) -> None:
        k1 = LLMCache._make_key("openai", "gpt-4", None, "hi", 0.2, 2048)
        k2 = LLMCache._make_key("ollama", "gpt-4", None, "hi", 0.2, 2048)
        assert k1 != k2

    def test_different_model_different_key(self) -> None:
        k1 = LLMCache._make_key("openai", "gpt-4", None, "hi", 0.2, 2048)
        k2 = LLMCache._make_key("openai", "gpt-3.5", None, "hi", 0.2, 2048)
        assert k1 != k2

    def test_key_is_sha256(self) -> None:
        key = LLMCache._make_key("p", "m", None, "prompt", 0.2, 2048)
        assert len(key) == 64  # SHA-256 hex digest length


# ═══════════════════════════════════════════════════════════════════════════
# 2 — RateLimiter: sliding window enforcement
# ═══════════════════════════════════════════════════════════════════════════


class TestRateLimiterBasic:
    """Basic rate limiter operations."""

    def test_unlimited_always_allows(self) -> None:
        rl = RateLimiter(rpm=0, tpm=0)
        rl.acquire()  # Should not raise
        assert not rl.is_enabled

    def test_is_enabled_rpm(self) -> None:
        rl = RateLimiter(rpm=10)
        assert rl.is_enabled

    def test_is_enabled_tpm(self) -> None:
        rl = RateLimiter(tpm=1000)
        assert rl.is_enabled

    def test_acquire_within_limit(self) -> None:
        rl = RateLimiter(rpm=100, blocking=False)
        rl.acquire()  # Should not raise

    def test_acquire_exceeds_rpm_nonblocking(self) -> None:
        rl = RateLimiter(rpm=2, blocking=False)
        rl.acquire()
        rl.acquire()
        with pytest.raises(RateLimitExceeded):
            rl.acquire()

    def test_record_usage(self) -> None:
        rl = RateLimiter(rpm=100)
        rl.acquire()
        rl.record_usage(500)
        assert rl.stats.total_tokens == 500

    def test_stats_tracking(self) -> None:
        rl = RateLimiter(rpm=100)
        rl.acquire()
        rl.acquire()
        assert rl.stats.total_requests == 2


class TestRateLimiterTPM:
    """Tokens-per-minute enforcement."""

    def test_tpm_limit_nonblocking(self) -> None:
        rl = RateLimiter(tpm=100, blocking=False)
        rl.acquire(estimated_tokens=80)
        with pytest.raises(RateLimitExceeded):
            rl.acquire(estimated_tokens=80)

    def test_tpm_allows_within_limit(self) -> None:
        rl = RateLimiter(tpm=1000, blocking=False)
        rl.acquire(estimated_tokens=400)
        rl.acquire(estimated_tokens=400)  # 800 total, within 1000

    def test_tpm_stats_current(self) -> None:
        rl = RateLimiter(tpm=10000)
        rl.acquire(estimated_tokens=500)
        assert rl.stats.current_tpm == 500


class TestRateLimitExceeded:
    """RateLimitExceeded exception."""

    def test_exception_message(self) -> None:
        exc = RateLimitExceeded("too fast")
        assert str(exc) == "too fast"

    def test_retry_after(self) -> None:
        exc = RateLimitExceeded("slow down", retry_after=5.0)
        assert exc.retry_after == 5.0

    def test_default_retry_after(self) -> None:
        exc = RateLimitExceeded()
        assert exc.retry_after == 0.0

    def test_rejected_requests_tracked(self) -> None:
        rl = RateLimiter(rpm=1, blocking=False)
        rl.acquire()
        with pytest.raises(RateLimitExceeded):
            rl.acquire()
        assert rl.stats.rejected_requests == 1


class TestRateLimiterStats:
    """RateLimiterStats dataclass."""

    def test_initial_stats(self) -> None:
        stats = RateLimiterStats()
        assert stats.total_requests == 0
        assert stats.total_tokens == 0
        assert stats.rejected_requests == 0

    def test_to_dict(self) -> None:
        stats = RateLimiterStats(total_requests=5, total_tokens=1000)
        d = stats.to_dict()
        assert d["total_requests"] == 5
        assert d["total_tokens"] == 1000
        assert "current_rpm" in d
        assert "current_tpm" in d


class TestRateLimiterSlidingWindow:
    """Sliding window prune behaviour."""

    def test_old_events_pruned(self) -> None:
        rl = RateLimiter(rpm=2, blocking=False)
        rl.acquire()
        rl.acquire()
        # Manually age the events
        for ev in rl._events:
            ev.timestamp -= 61.0
        rl.acquire()  # Should succeed because old events were pruned


# ═══════════════════════════════════════════════════════════════════════════
# 3 — CachedProvider: wrapper for any LLMProvider
# ═══════════════════════════════════════════════════════════════════════════


class TestCachedProviderBasic:
    """CachedProvider wraps an LLMProvider with caching and rate limiting."""

    def _make_mock(self, content: str = "mock response") -> MockProvider:
        provider = MockProvider()
        provider.enqueue_response(content)
        return provider

    def test_name_delegates_to_inner(self) -> None:
        mock = self._make_mock()
        cp = CachedProvider(mock)
        assert cp.name == mock.name

    def test_is_available_delegates(self) -> None:
        mock = self._make_mock()
        cp = CachedProvider(mock)
        assert cp.is_available() == mock.is_available()

    def test_inner_property(self) -> None:
        mock = self._make_mock()
        cp = CachedProvider(mock)
        assert cp.inner is mock

    def test_complete_without_cache(self) -> None:
        mock = self._make_mock("hello")
        cp = CachedProvider(mock)
        result = cp.complete("test prompt")
        assert result.content == "hello"

    def test_chat_without_cache(self) -> None:
        mock = self._make_mock("hi there")
        cp = CachedProvider(mock)
        msgs = [LLMMessage(role=MessageRole.USER, content="say hi")]
        result = cp.chat(msgs)
        assert result.content == "hi there"


class TestCachedProviderCaching:
    """Caching behaviour through CachedProvider."""

    def _make_provider(self) -> tuple[MockProvider, CachedProvider]:
        mock = MockProvider()
        mock.enqueue_response("first")
        mock.enqueue_response("second")
        cache = LLMCache(ttl_hours=24)
        return mock, CachedProvider(mock, cache=cache)

    def test_complete_caches_response(self) -> None:
        mock, cp = self._make_provider()
        r1 = cp.complete("query")
        r2 = cp.complete("query")
        assert r1.content == "first"
        assert r2.content == "first"  # same, from cache

    def test_chat_caches_response(self) -> None:
        mock, cp = self._make_provider()
        msgs = [LLMMessage(role=MessageRole.USER, content="hello")]
        r1 = cp.chat(msgs)
        r2 = cp.chat(msgs)
        assert r1.content == "first"
        assert r2.content == "first"  # cached

    def test_different_prompts_not_cached(self) -> None:
        mock, cp = self._make_provider()
        r1 = cp.complete("query1")
        r2 = cp.complete("query2")
        assert r1.content == "first"
        assert r2.content == "second"  # different prompt → different result

    def test_save_cache_delegates(self, tmp_path: Path) -> None:
        mock = MockProvider()
        mock.enqueue_response("data")
        cache = LLMCache(cache_dir=str(tmp_path), ttl_hours=24)
        cp = CachedProvider(mock, cache=cache)
        cp.complete("test")
        cp.save_cache()
        assert (tmp_path / "llm_cache.json").exists()

    def test_save_cache_noop_without_cache(self) -> None:
        mock = MockProvider()
        cp = CachedProvider(mock)
        cp.save_cache()  # Should not raise


class TestCachedProviderRateLimiting:
    """Rate limiting through CachedProvider."""

    def test_rate_limited_requests(self) -> None:
        mock = MockProvider()
        for r in ["a", "b", "c"]:
            mock.enqueue_response(r)
        rl = RateLimiter(rpm=2, blocking=False)
        cp = CachedProvider(mock, rate_limiter=rl)
        cp.complete("q1")
        cp.complete("q2")
        with pytest.raises(RateLimitExceeded):
            cp.complete("q3")

    def test_rate_limiter_records_usage(self) -> None:
        mock = MockProvider()
        mock.enqueue_response("result")
        rl = RateLimiter(rpm=100)
        cp = CachedProvider(mock, rate_limiter=rl)
        cp.complete("test")
        assert rl.stats.total_requests == 1

    def test_cached_response_skips_rate_limit(self) -> None:
        mock = MockProvider()
        mock.enqueue_response("first")
        mock.enqueue_response("second")
        cache = LLMCache(ttl_hours=24)
        rl = RateLimiter(rpm=1, blocking=False)
        cp = CachedProvider(mock, cache=cache, rate_limiter=rl)
        cp.complete("same-query")  # Uses rate limit slot
        cp.complete("same-query")  # Cache hit — no rate limit needed


class TestCachedProviderChat:
    """Chat-specific caching and rate limiting."""

    def test_chat_cache_and_rate_limit_combined(self) -> None:
        mock = MockProvider()
        mock.enqueue_response("resp1")
        mock.enqueue_response("resp2")
        cache = LLMCache(ttl_hours=24)
        rl = RateLimiter(rpm=100)
        cp = CachedProvider(mock, cache=cache, rate_limiter=rl)
        msgs = [LLMMessage(role=MessageRole.USER, content="hi")]
        r1 = cp.chat(msgs)
        r2 = cp.chat(msgs)
        assert r1.content == "resp1"
        assert r2.content == "resp1"  # from cache
        assert rl.stats.total_requests == 1  # only one actual API call


# ═══════════════════════════════════════════════════════════════════════════
# 4 — LLMConfig: new cache/rate-limit fields
# ═══════════════════════════════════════════════════════════════════════════


class TestLLMConfigFields:
    """LLMConfig has cache and rate limit configuration fields."""

    def test_cache_enabled_default(self) -> None:
        from semantic_code_intelligence.config.settings import LLMConfig
        cfg = LLMConfig()
        assert cfg.cache_enabled is True

    def test_cache_ttl_hours_default(self) -> None:
        from semantic_code_intelligence.config.settings import LLMConfig
        cfg = LLMConfig()
        assert cfg.cache_ttl_hours == 24

    def test_cache_max_entries_default(self) -> None:
        from semantic_code_intelligence.config.settings import LLMConfig
        cfg = LLMConfig()
        assert cfg.cache_max_entries == 1000

    def test_rate_limit_rpm_default(self) -> None:
        from semantic_code_intelligence.config.settings import LLMConfig
        cfg = LLMConfig()
        assert cfg.rate_limit_rpm == 0

    def test_rate_limit_tpm_default(self) -> None:
        from semantic_code_intelligence.config.settings import LLMConfig
        cfg = LLMConfig()
        assert cfg.rate_limit_tpm == 0

    def test_custom_values(self) -> None:
        from semantic_code_intelligence.config.settings import LLMConfig
        cfg = LLMConfig(
            cache_enabled=False,
            cache_ttl_hours=48,
            cache_max_entries=500,
            rate_limit_rpm=30,
            rate_limit_tpm=50000,
        )
        assert cfg.cache_enabled is False
        assert cfg.cache_ttl_hours == 48
        assert cfg.cache_max_entries == 500
        assert cfg.rate_limit_rpm == 30
        assert cfg.rate_limit_tpm == 50000

    def test_serialization_roundtrip(self) -> None:
        from semantic_code_intelligence.config.settings import LLMConfig
        cfg = LLMConfig(cache_enabled=True, rate_limit_rpm=60)
        data = json.loads(cfg.model_dump_json())
        restored = LLMConfig.model_validate(data)
        assert restored.cache_enabled is True
        assert restored.rate_limit_rpm == 60

    def test_config_in_appconfig(self) -> None:
        from semantic_code_intelligence.config.settings import AppConfig
        app = AppConfig()
        assert hasattr(app.llm, "cache_enabled")
        assert hasattr(app.llm, "rate_limit_rpm")
        assert hasattr(app.llm, "rate_limit_tpm")

    def test_config_json_persistence(self, tmp_path: Path) -> None:
        from semantic_code_intelligence.config.settings import AppConfig, save_config, load_config
        cfg = AppConfig(project_root=str(tmp_path))
        cfg.llm.cache_enabled = False
        cfg.llm.rate_limit_rpm = 42
        save_config(cfg, tmp_path)
        loaded = load_config(tmp_path)
        assert loaded.llm.cache_enabled is False
        assert loaded.llm.rate_limit_rpm == 42


# ═══════════════════════════════════════════════════════════════════════════
# 5 — CLI _wrap_provider integration
# ═══════════════════════════════════════════════════════════════════════════


class TestWrapProviderIntegration:
    """_wrap_provider correctly builds CachedProvider from config."""

    def _make_config(
        self,
        cache_enabled: bool = True,
        rpm: int = 0,
        tpm: int = 0,
    ) -> Any:
        from semantic_code_intelligence.config.settings import AppConfig, LLMConfig
        cfg = AppConfig()
        cfg.llm.cache_enabled = cache_enabled
        cfg.llm.rate_limit_rpm = rpm
        cfg.llm.rate_limit_tpm = tpm
        return cfg

    def test_wrap_returns_cached_provider(self) -> None:
        from semantic_code_intelligence.cli.commands.ask_cmd import _wrap_provider
        cfg = self._make_config(cache_enabled=True)
        provider = MockProvider()
        result = _wrap_provider(provider, cfg.llm, cfg)
        assert isinstance(result, CachedProvider)

    def test_wrap_no_cache_no_rate_limit(self) -> None:
        from semantic_code_intelligence.cli.commands.ask_cmd import _wrap_provider
        cfg = self._make_config(cache_enabled=False, rpm=0, tpm=0)
        provider = MockProvider()
        result = _wrap_provider(provider, cfg.llm, cfg)
        assert result is provider  # No wrapping

    def test_wrap_rate_limit_only(self) -> None:
        from semantic_code_intelligence.cli.commands.ask_cmd import _wrap_provider
        cfg = self._make_config(cache_enabled=False, rpm=60)
        provider = MockProvider()
        result = _wrap_provider(provider, cfg.llm, cfg)
        assert isinstance(result, CachedProvider)

    def test_wrap_chat_cmd(self) -> None:
        from semantic_code_intelligence.cli.commands.chat_cmd import _wrap_provider
        cfg = self._make_config(cache_enabled=True)
        provider = MockProvider()
        result = _wrap_provider(provider, cfg.llm, cfg)
        assert isinstance(result, CachedProvider)

    def test_wrap_investigate_cmd(self) -> None:
        from semantic_code_intelligence.cli.commands.investigate_cmd import _wrap_provider
        cfg = self._make_config(cache_enabled=True)
        provider = MockProvider()
        result = _wrap_provider(provider, cfg.llm, cfg)
        assert isinstance(result, CachedProvider)


# ═══════════════════════════════════════════════════════════════════════════
# 6 — Module exports and imports
# ═══════════════════════════════════════════════════════════════════════════


class TestModuleExports:
    """Verify new classes are exported from the llm package."""

    def test_cache_exported(self) -> None:
        from semantic_code_intelligence.llm import LLMCache
        assert LLMCache is not None

    def test_cache_stats_exported(self) -> None:
        from semantic_code_intelligence.llm import CacheStats
        assert CacheStats is not None

    def test_cached_provider_exported(self) -> None:
        from semantic_code_intelligence.llm import CachedProvider
        assert CachedProvider is not None

    def test_rate_limiter_exported(self) -> None:
        from semantic_code_intelligence.llm import RateLimiter
        assert RateLimiter is not None

    def test_rate_limit_exceeded_exported(self) -> None:
        from semantic_code_intelligence.llm import RateLimitExceeded
        assert RateLimitExceeded is not None

    def test_rate_limiter_stats_exported(self) -> None:
        from semantic_code_intelligence.llm import RateLimiterStats
        assert RateLimiterStats is not None

    def test_all_list_includes_new_classes(self) -> None:
        import semantic_code_intelligence.llm as llm_mod
        for name in ["CachedProvider", "LLMCache", "CacheStats",
                      "RateLimiter", "RateLimitExceeded", "RateLimiterStats"]:
            assert name in llm_mod.__all__


# ═══════════════════════════════════════════════════════════════════════════
# 7 — End-to-end flow
# ═══════════════════════════════════════════════════════════════════════════


class TestEndToEndFlow:
    """Full caching + rate limiting pipeline."""

    def test_full_flow_complete(self) -> None:
        mock = MockProvider()
        mock.enqueue_response("answer1")
        mock.enqueue_response("answer2")
        cache = LLMCache(ttl_hours=24)
        rl = RateLimiter(rpm=100)
        cp = CachedProvider(mock, cache=cache, rate_limiter=rl)

        # First call — cache miss, hits provider
        r1 = cp.complete("what is 2+2?")
        assert r1.content == "answer1"
        assert cache.stats.misses == 1
        assert cache.stats.hits == 0

        # Second call — cache hit
        r2 = cp.complete("what is 2+2?")
        assert r2.content == "answer1"
        assert cache.stats.hits == 1

        # Different query — cache miss
        r3 = cp.complete("what is 3+3?")
        assert r3.content == "answer2"
        assert cache.stats.misses == 2

    def test_full_flow_chat(self) -> None:
        mock = MockProvider()
        mock.enqueue_response("reply1")
        mock.enqueue_response("reply2")
        cache = LLMCache(ttl_hours=24)
        cp = CachedProvider(mock, cache=cache)

        msgs = [LLMMessage(role=MessageRole.USER, content="greet me")]
        r1 = cp.chat(msgs)
        r2 = cp.chat(msgs)
        assert r1.content == "reply1"
        assert r2.content == "reply1"

    def test_full_flow_with_persistence(self, tmp_path: Path) -> None:
        mock = MockProvider()
        mock.enqueue_response("persisted")
        cache = LLMCache(cache_dir=str(tmp_path), ttl_hours=24)
        cp = CachedProvider(mock, cache=cache)
        cp.complete("save me")
        cp.save_cache()

        # New provider instance loads from disk
        cache2 = LLMCache(cache_dir=str(tmp_path), ttl_hours=24)
        cp2 = CachedProvider(MockProvider(), cache=cache2)
        result = cp2.complete("save me")
        assert result is not None
        assert result.content == "persisted"

    def test_rate_limit_protects_provider(self) -> None:
        mock = MockProvider()
        for r in ["a", "b", "c", "d", "e"]:
            mock.enqueue_response(r)
        rl = RateLimiter(rpm=3, blocking=False)
        cp = CachedProvider(mock, rate_limiter=rl)
        cp.complete("q1")
        cp.complete("q2")
        cp.complete("q3")
        with pytest.raises(RateLimitExceeded):
            cp.complete("q4")


# ═══════════════════════════════════════════════════════════════════════════
# 8 — Version check
# ═══════════════════════════════════════════════════════════════════════════


class TestVersion:
    """Version should reflect Phase 22."""

    def test_version_is_0_22_0(self) -> None:
        from semantic_code_intelligence import __version__
        assert __version__ == "0.23.0"
