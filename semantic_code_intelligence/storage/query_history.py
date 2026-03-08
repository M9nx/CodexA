"""Query history — cross-session intelligence and search analytics.

Records past search queries, their result counts and scores, enabling
popular-symbol tracking, query suggestions, and analytics on what
developers search for most.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HISTORY_FILE = "query_history.json"
MAX_HISTORY = 500


@dataclass
class QueryRecord:
    """A single recorded search query."""

    query: str
    timestamp: float = 0.0
    result_count: int = 0
    top_score: float = 0.0
    languages: list[str] = field(default_factory=list)
    top_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryRecord:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


class QueryHistory:
    """Persistent query history with analytics.

    Stores the last *max_entries* queries and provides aggregate
    statistics for popular searches, symbols, and files.
    """

    def __init__(self, max_entries: int = MAX_HISTORY) -> None:
        self._records: list[QueryRecord] = []
        self._max_entries = max_entries

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def record(
        self,
        query: str,
        result_count: int = 0,
        top_score: float = 0.0,
        languages: list[str] | None = None,
        top_files: list[str] | None = None,
    ) -> QueryRecord:
        """Record a search query."""
        entry = QueryRecord(
            query=query,
            timestamp=time.time(),
            result_count=result_count,
            top_score=top_score,
            languages=languages or [],
            top_files=top_files or [],
        )
        self._records.append(entry)
        # Evict oldest when exceeding max
        while len(self._records) > self._max_entries:
            self._records.pop(0)
        return entry

    def clear(self) -> None:
        """Remove all history."""
        self._records.clear()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._records)

    @property
    def records(self) -> list[QueryRecord]:
        """Return all records (newest last)."""
        return list(self._records)

    def recent(self, n: int = 10) -> list[QueryRecord]:
        """Return the *n* most recent queries."""
        return list(self._records[-n:])

    def popular_queries(self, n: int = 10) -> list[tuple[str, int]]:
        """Return the *n* most frequent query strings with counts."""
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.query] = counts.get(r.query, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return ranked[:n]

    def popular_files(self, n: int = 10) -> list[tuple[str, int]]:
        """Return the *n* most frequently appearing files in results."""
        counts: dict[str, int] = {}
        for r in self._records:
            for f in r.top_files:
                counts[f] = counts.get(f, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return ranked[:n]

    def avg_result_count(self) -> float:
        """Return the average number of results per query."""
        if not self._records:
            return 0.0
        return sum(r.result_count for r in self._records) / len(self._records)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_entries": self._max_entries,
            "records": [r.to_dict() for r in self._records],
        }

    def __repr__(self) -> str:
        return f"QueryHistory(records={len(self._records)})"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Write history to disk."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / HISTORY_FILE).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: str | Path) -> QueryHistory:
        """Load history from disk.  Returns empty history if absent."""
        history = cls()
        path = Path(directory) / HISTORY_FILE
        if not path.exists():
            return history
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                history._max_entries = data.get("max_entries", MAX_HISTORY)
                for item in data.get("records", []):
                    if isinstance(item, dict):
                        history._records.append(QueryRecord.from_dict(item))
        except (json.JSONDecodeError, OSError):
            pass
        return history
