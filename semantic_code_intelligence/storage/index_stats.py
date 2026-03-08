"""Index statistics — health metrics, coverage, and staleness tracking.

Provides detailed statistics about the intelligence index including
per-language coverage, chunk distribution, and staleness metrics
for monitoring index quality.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STATS_FILE = "index_stats.json"


@dataclass
class LanguageCoverage:
    """Per-language indexing statistics."""

    language: str = ""
    files: int = 0
    chunks: int = 0
    symbols: int = 0
    total_lines: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LanguageCoverage:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class IndexStats:
    """Comprehensive index health and coverage statistics."""

    # Counts
    total_files: int = 0
    total_chunks: int = 0
    total_symbols: int = 0
    total_vectors: int = 0

    # Timing
    last_indexed_at: float = 0.0
    indexing_duration_seconds: float = 0.0

    # Per-language breakdown
    language_coverage: list[LanguageCoverage] = field(default_factory=list)

    # Staleness
    stale_files: int = 0  # files changed since last index

    # Quality
    avg_chunk_size: float = 0.0
    embedding_model: str = ""
    embedding_dimension: int = 0

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["language_coverage"] = [lc.to_dict() for lc in self.language_coverage]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndexStats:
        lang_data = data.pop("language_coverage", [])
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known and k != "language_coverage"}
        stats = cls(**filtered)
        stats.language_coverage = [
            LanguageCoverage.from_dict(lc) if isinstance(lc, dict) else lc
            for lc in lang_data
        ]
        return stats

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Write stats to disk."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / STATS_FILE).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: str | Path) -> IndexStats | None:
        """Load stats from disk, or return ``None`` if absent."""
        path = Path(directory) / STATS_FILE
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def staleness_seconds(self) -> float:
        """Seconds since the last indexing run."""
        if self.last_indexed_at == 0.0:
            return 0.0
        return time.time() - self.last_indexed_at

    @property
    def languages(self) -> list[str]:
        """Return all indexed languages."""
        return [lc.language for lc in self.language_coverage]

    def get_language(self, language: str) -> LanguageCoverage | None:
        """Return coverage for a specific language."""
        for lc in self.language_coverage:
            if lc.language == language:
                return lc
        return None

    def set_language(self, coverage: LanguageCoverage) -> None:
        """Add or replace per-language coverage entry."""
        for i, lc in enumerate(self.language_coverage):
            if lc.language == coverage.language:
                self.language_coverage[i] = coverage
                return
        self.language_coverage.append(coverage)
