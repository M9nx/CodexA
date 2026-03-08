"""LLM response cache — disk-backed cache with TTL expiration.

Caches LLM responses keyed by a deterministic hash of the request
parameters (provider, model, messages/prompt, temperature, max_tokens).
Supports time-to-live (TTL) expiration and max-entry eviction.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.llm.provider import LLMMessage, LLMResponse


@dataclass
class CacheEntry:
    """A single cached LLM response with metadata."""

    response: dict[str, Any]
    timestamp: float
    provider: str
    model: str


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate as a percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "hit_rate": round(self.hit_rate, 2),
        }


class LLMCache:
    """Disk-backed LLM response cache with TTL and max-entry limits.

    Cache entries are evicted when they exceed ``ttl_hours`` or when
    the total number of entries exceeds ``max_entries`` (oldest first).
    The cache is persisted as a JSON file to survive process restarts.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        ttl_hours: int = 24,
        max_entries: int = 1000,
    ) -> None:
        self._entries: dict[str, dict[str, Any]] = {}
        self._ttl_seconds: float = ttl_hours * 3600.0
        self._max_entries: int = max_entries
        self._stats = CacheStats()
        self._cache_path: Path | None = None
        if cache_dir is not None:
            self._cache_path = Path(cache_dir) / "llm_cache.json"
            self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        provider: str,
        model: str,
        messages: list[LLMMessage] | None = None,
        prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse | None:
        """Look up a cached response.  Returns ``None`` on cache miss."""
        key = self._make_key(provider, model, messages, prompt, temperature, max_tokens)
        entry = self._entries.get(key)
        if entry is None:
            self._stats.misses += 1
            return None

        # Check TTL
        age = time.time() - entry["timestamp"]
        if age > self._ttl_seconds:
            del self._entries[key]
            self._stats.misses += 1
            self._stats.evictions += 1
            return None

        self._stats.hits += 1
        return self._dict_to_response(entry["response"])

    def put(
        self,
        response: LLMResponse,
        provider: str,
        model: str,
        messages: list[LLMMessage] | None = None,
        prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> None:
        """Store a response in the cache."""
        key = self._make_key(provider, model, messages, prompt, temperature, max_tokens)
        self._entries[key] = {
            "response": self._response_to_dict(response),
            "timestamp": time.time(),
            "provider": provider,
            "model": model,
        }
        self._evict_if_needed()
        self._stats.size = len(self._entries)

    def clear(self) -> None:
        """Remove all cache entries."""
        self._entries.clear()
        self._stats = CacheStats()

    def save(self) -> None:
        """Persist cache to disk."""
        if self._cache_path is None:
            return
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(self._entries, indent=2, ensure_ascii=False)
        self._cache_path.write_text(data, encoding="utf-8")

    @property
    def stats(self) -> CacheStats:
        """Return current cache statistics."""
        self._stats.size = len(self._entries)
        return self._stats

    @property
    def size(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load cache entries from disk, dropping expired entries."""
        if self._cache_path is None or not self._cache_path.exists():
            return
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            now = time.time()
            for key, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                ts = entry.get("timestamp", 0.0)
                if now - ts <= self._ttl_seconds:
                    self._entries[key] = entry
        except (json.JSONDecodeError, OSError):
            pass

    def _evict_if_needed(self) -> None:
        """Evict oldest entries when the cache exceeds max size."""
        while len(self._entries) > self._max_entries:
            oldest_key = min(self._entries, key=lambda k: self._entries[k]["timestamp"])
            del self._entries[oldest_key]
            self._stats.evictions += 1

    @staticmethod
    def _make_key(
        provider: str,
        model: str,
        messages: list[LLMMessage] | None,
        prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Create a deterministic cache key from request parameters."""
        parts: list[str] = [provider, model, str(temperature), str(max_tokens)]
        if messages is not None:
            for msg in messages:
                parts.append(f"{msg.role.value}:{msg.content}")
        if prompt is not None:
            parts.append(f"prompt:{prompt}")
        raw = "\n".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _response_to_dict(response: LLMResponse) -> dict[str, Any]:
        return {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }

    @staticmethod
    def _dict_to_response(data: dict[str, Any]) -> LLMResponse:
        return LLMResponse(
            content=data.get("content", ""),
            model=data.get("model", ""),
            provider=data.get("provider", ""),
            usage=data.get("usage", {}),
        )
