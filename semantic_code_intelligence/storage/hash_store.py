"""Hash store — tracks file content hashes for incremental indexing."""

from __future__ import annotations

import json
from pathlib import Path

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("storage.hashes")

HASH_FILE_NAME = "file_hashes.json"


class HashStore:
    """Persists a mapping of file paths to content hashes.

    Used for incremental indexing: only re-index files whose hash has changed.
    """

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    @property
    def count(self) -> int:
        """Number of tracked files."""
        return len(self._hashes)

    def get(self, file_path: str) -> str | None:
        """Get the stored hash for a file path."""
        return self._hashes.get(file_path)

    def set(self, file_path: str, content_hash: str) -> None:
        """Store or update the hash for a file path."""
        self._hashes[file_path] = content_hash

    def has_changed(self, file_path: str, content_hash: str) -> bool:
        """Check if a file's content has changed since last indexed.

        Returns True if the file is new or its hash differs.
        """
        stored = self._hashes.get(file_path)
        return stored != content_hash

    def remove(self, file_path: str) -> None:
        """Remove a file from the hash store."""
        self._hashes.pop(file_path, None)

    def save(self, directory: Path) -> None:
        """Save hashes to disk."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / HASH_FILE_NAME
        path.write_text(
            json.dumps(self._hashes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "HashStore":
        """Load hashes from disk. Returns empty store if file doesn't exist."""
        store = cls()
        path = Path(directory) / HASH_FILE_NAME
        if path.exists():
            store._hashes = json.loads(path.read_text(encoding="utf-8"))
        return store
