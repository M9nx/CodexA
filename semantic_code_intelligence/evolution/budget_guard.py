"""Budget guard — tracks token usage, iterations, and wall-clock time.

Enforces hard limits so that the evolution loop cannot run away with
unbounded LLM calls.  The guard is passed through every stage and
checked before each LLM invocation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class BudgetGuard:
    """Resource budget tracker for the evolution loop.

    Parameters
    ----------
    max_tokens : int
        Maximum total tokens (prompt + completion) across all LLM calls.
    max_iterations : int
        Maximum evolution iterations to attempt.
    max_seconds : float
        Maximum wall-clock seconds before the loop is force-stopped.
    """

    max_tokens: int = 20_000
    max_iterations: int = 5
    max_seconds: float = 600.0  # 10 minutes default

    # Counters
    tokens_used: int = 0
    iterations_done: int = 0
    _start_time: float = field(default=0.0, repr=False)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Mark the beginning of the evolution run."""
        self._start_time = time.time()

    @property
    def elapsed_seconds(self) -> float:
        """Wall-clock seconds since :meth:`start` was called."""
        if self._start_time == 0.0:
            return 0.0
        return time.time() - self._start_time

    # ------------------------------------------------------------------ #
    # Checks
    # ------------------------------------------------------------------ #

    @property
    def tokens_remaining(self) -> int:
        """Tokens still available before the budget is exhausted."""
        return max(0, self.max_tokens - self.tokens_used)

    @property
    def iterations_remaining(self) -> int:
        """Iterations still available before the limit is hit."""
        return max(0, self.max_iterations - self.iterations_done)

    def can_continue(self) -> bool:
        """Return ``True`` if budget allows another iteration."""
        if self.iterations_done >= self.max_iterations:
            return False
        if self.tokens_used >= self.max_tokens:
            return False
        if self._start_time > 0.0 and self.elapsed_seconds >= self.max_seconds:
            return False
        return True

    def stop_reason(self) -> str | None:
        """Return a human-readable reason if budget is exhausted, else ``None``."""
        if self.iterations_done >= self.max_iterations:
            return f"iteration limit reached ({self.max_iterations})"
        if self.tokens_used >= self.max_tokens:
            return f"token budget exhausted ({self.tokens_used}/{self.max_tokens})"
        if self._start_time > 0.0 and self.elapsed_seconds >= self.max_seconds:
            return f"time limit reached ({self.elapsed_seconds:.0f}s/{self.max_seconds:.0f}s)"
        return None

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record_tokens(self, tokens: int) -> None:
        """Record token usage from an LLM call."""
        self.tokens_used += tokens

    def record_iteration(self) -> None:
        """Mark one iteration as completed."""
        self.iterations_done += 1

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    def summary(self) -> dict[str, object]:
        """Return a dict snapshot of current budget usage."""
        return {
            "tokens_used": self.tokens_used,
            "tokens_max": self.max_tokens,
            "iterations_done": self.iterations_done,
            "iterations_max": self.max_iterations,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "max_seconds": self.max_seconds,
        }
