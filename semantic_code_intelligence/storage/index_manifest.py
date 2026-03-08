"""Index manifest — versioned metadata for the persistent intelligence index.

Tracks index schema version, embedding model, creation/update timestamps,
and file counts to enable integrity checks and safe index upgrades.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_FILE = "index_manifest.json"
SCHEMA_VERSION = 1


@dataclass
class IndexManifest:
    """Metadata describing a persisted intelligence index."""

    schema_version: int = SCHEMA_VERSION
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    created_at: float = 0.0
    updated_at: float = 0.0
    total_files: int = 0
    total_chunks: int = 0
    total_symbols: int = 0
    languages: list[str] = field(default_factory=list)
    project_root: str = ""

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndexManifest:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Write the manifest to *directory*/index_manifest.json."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / MANIFEST_FILE).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: str | Path) -> IndexManifest | None:
        """Load an existing manifest, or return ``None`` if absent."""
        path = Path(directory) / MANIFEST_FILE
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

    def touch(self) -> None:
        """Update ``updated_at`` to now; set ``created_at`` if zero."""
        now = time.time()
        if self.created_at == 0.0:
            self.created_at = now
        self.updated_at = now

    def is_compatible(self, model: str, dimension: int) -> bool:
        """Check whether the index was built with the given model/dimension."""
        return self.embedding_model == model and self.embedding_dimension == dimension
