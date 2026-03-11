"""LLM rate limiter — sliding-window rate limiting for API calls.

Enforces requests-per-minute (RPM) and tokens-per-minute (TPM) limits
using a sliding window of recent events.  Callers can either block
until capacity is available or receive a ``RateLimitExceeded`` error.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any


class RateLimitExceeded(Exception):
    """Raised when a rate limit has been exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class RateLimiterStats:
    """Rate limiter statistics."""

    total_requests: int = 0
    total_tokens: int = 0
    rejected_requests: int = 0
    current_rpm: int = 0
    current_tpm: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _Event:
    """Internal record of a single API call."""

    timestamp: float
    tokens: int = 0


class RateLimiter:
    """Sliding-window rate limiter for LLM API calls.

    Parameters
    ----------
    rpm : int
        Maximum requests per minute.  0 = unlimited.
    tpm : int
        Maximum tokens per minute.  0 = unlimited.
    blocking : bool
        If ``True``, :meth:`acquire` will sleep until capacity is
        available instead of raising :class:`RateLimitExceeded`.
    """

    def __init__(
        self,
        rpm: int = 0,
        tpm: int = 0,
        blocking: bool = True,
    ) -> None:
        self._rpm = rpm
        self._tpm = tpm
        self._blocking = blocking
        self._events: list[_Event] = []
        self._lock = threading.Lock()
        self._stats = RateLimiterStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(self, estimated_tokens: int = 0) -> None:
        """Acquire permission to make an API call.

        If the rate limit would be exceeded and ``blocking`` is True,
        this method sleeps until capacity is available.  Otherwise it
        raises :class:`RateLimitExceeded`.
        """
        while True:
            with self._lock:
                self._prune()
                rpm_ok = self._check_rpm()
                tpm_ok = self._check_tpm(estimated_tokens)
                if rpm_ok and tpm_ok:
                    # Record the request event (token count updated later via record_usage)
                    self._events.append(_Event(timestamp=time.monotonic(), tokens=estimated_tokens))
                    self._stats.total_requests += 1
                    return

                # Calculate wait time
                wait = self._wait_time()

            if not self._blocking:
                self._stats.rejected_requests += 1
                raise RateLimitExceeded(
                    f"Rate limit exceeded (RPM={self._rpm}, TPM={self._tpm})",
                    retry_after=wait,
                )

            # Sleep outside the lock
            time.sleep(min(wait, 1.0))

    def record_usage(self, tokens: int) -> None:
        """Record the actual token usage after a response is received."""
        with self._lock:
            self._stats.total_tokens += tokens
            # Update the last event's token count with actual usage
            if self._events:
                self._events[-1].tokens = tokens

    @property
    def stats(self) -> RateLimiterStats:
        """Return current rate limiter statistics."""
        with self._lock:
            self._prune()
            self._stats.current_rpm = len(self._events)
            self._stats.current_tpm = sum(e.tokens for e in self._events)
        return self._stats

    @property
    def is_enabled(self) -> bool:
        """Return True if any rate limit is configured."""
        return self._rpm > 0 or self._tpm > 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune(self) -> None:
        """Remove events older than 60 seconds."""
        cutoff = time.monotonic() - 60.0
        self._events = [e for e in self._events if e.timestamp > cutoff]

    def _check_rpm(self) -> bool:
        """Check whether adding one more request is within the RPM limit."""
        if self._rpm <= 0:
            return True
        return len(self._events) < self._rpm

    def _check_tpm(self, estimated_tokens: int) -> bool:
        """Check whether adding tokens is within the TPM limit."""
        if self._tpm <= 0:
            return True
        current = sum(e.tokens for e in self._events)
        return (current + estimated_tokens) <= self._tpm

    def _wait_time(self) -> float:
        """Estimate how long to wait before capacity is available."""
        if not self._events:
            return 0.1
        oldest = self._events[0].timestamp
        elapsed = time.monotonic() - oldest
        return max(60.0 - elapsed, 0.1)
