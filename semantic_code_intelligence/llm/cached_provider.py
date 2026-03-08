"""Cached LLM provider wrapper — adds caching and rate limiting to any provider.

``CachedProvider`` wraps an existing :class:`LLMProvider` and transparently
adds response caching and API-call rate limiting.  It is the primary
integration point for the Phase 22 caching + rate limiting feature.
"""

from __future__ import annotations

from typing import Any

from semantic_code_intelligence.llm.cache import LLMCache
from semantic_code_intelligence.llm.provider import LLMMessage, LLMProvider, LLMResponse
from semantic_code_intelligence.llm.rate_limiter import RateLimiter


class CachedProvider(LLMProvider):
    """LLM provider wrapper that adds transparent caching and rate limiting.

    Parameters
    ----------
    provider : LLMProvider
        The underlying LLM provider to wrap.
    cache : LLMCache | None
        Response cache instance.  ``None`` disables caching.
    rate_limiter : RateLimiter | None
        Rate limiter instance.  ``None`` disables rate limiting.
    """

    def __init__(
        self,
        provider: LLMProvider,
        cache: LLMCache | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._rate_limiter = rate_limiter

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._provider.name

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        temperature = kwargs.get("temperature", 0.2)
        max_tokens = kwargs.get("max_tokens", 2048)

        # 1. Check cache
        if self._cache is not None:
            cached = self._cache.get(
                provider=self._provider.name,
                model=getattr(self._provider, "model", ""),
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if cached is not None:
                return cached

        # 2. Rate limit
        if self._rate_limiter is not None and self._rate_limiter.is_enabled:
            self._rate_limiter.acquire(estimated_tokens=max_tokens)

        # 3. Call underlying provider
        response = self._provider.complete(prompt, **kwargs)

        # 4. Record token usage
        if self._rate_limiter is not None and self._rate_limiter.is_enabled:
            total_tokens = response.usage.get("total_tokens", 0)
            self._rate_limiter.record_usage(total_tokens)

        # 5. Store in cache
        if self._cache is not None:
            self._cache.put(
                response=response,
                provider=self._provider.name,
                model=getattr(self._provider, "model", ""),
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        return response

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        temperature = kwargs.get("temperature", 0.2)
        max_tokens = kwargs.get("max_tokens", 2048)

        # 1. Check cache
        if self._cache is not None:
            cached = self._cache.get(
                provider=self._provider.name,
                model=getattr(self._provider, "model", ""),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if cached is not None:
                return cached

        # 2. Rate limit
        if self._rate_limiter is not None and self._rate_limiter.is_enabled:
            self._rate_limiter.acquire(estimated_tokens=max_tokens)

        # 3. Call underlying provider
        response = self._provider.chat(messages, **kwargs)

        # 4. Record token usage
        if self._rate_limiter is not None and self._rate_limiter.is_enabled:
            total_tokens = response.usage.get("total_tokens", 0)
            self._rate_limiter.record_usage(total_tokens)

        # 5. Store in cache
        if self._cache is not None:
            self._cache.put(
                response=response,
                provider=self._provider.name,
                model=getattr(self._provider, "model", ""),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        return response

    def is_available(self) -> bool:
        return self._provider.is_available()

    # ------------------------------------------------------------------
    # Extra helpers
    # ------------------------------------------------------------------

    @property
    def inner(self) -> LLMProvider:
        """Return the wrapped provider."""
        return self._provider

    def save_cache(self) -> None:
        """Persist the cache to disk (no-op when caching is disabled)."""
        if self._cache is not None:
            self._cache.save()
