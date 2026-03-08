"""Chunk hash store — tracks content hashes at the individual chunk level.

Enables chunk-level incremental indexing: when a file changes, only the
chunks whose content actually differs are re-embedded, while unchanged
chunks keep their existing vectors.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("storage.chunk_hashes")

CHUNK_HASH_FILE = "chunk_hashes.json"


def compute_chunk_hash(content: str) -> str:
    """Compute a fast SHA-256 hash for a chunk's content."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


class ChunkHashStore:
    """Persists a mapping of chunk keys to content hashes.

    Chunk key format: ``"file_path:start_line:end_line"``

    Used for chunk-level incremental indexing: only re-embed chunks
    whose content has actually changed, even if the file was modified.
    """

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    @staticmethod
    def chunk_key(file_path: str, start_line: int, end_line: int) -> str:
        return f"{file_path}:{start_line}:{end_line}"

    @property
    def count(self) -> int:
        return len(self._hashes)

    def get(self, key: str) -> str | None:
        return self._hashes.get(key)

    def set(self, key: str, content_hash: str) -> None:
        self._hashes[key] = content_hash

    def has_changed(self, key: str, content_hash: str) -> bool:
        stored = self._hashes.get(key)
        return stored != content_hash

    def remove(self, key: str) -> None:
        self._hashes.pop(key, None)

    def remove_by_file(self, file_path: str) -> int:
        """Remove all chunk entries whose key starts with file_path."""
        prefix = file_path + ":"
        keys_to_remove = [k for k in self._hashes if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._hashes[k]
        return len(keys_to_remove)

    def keys_for_file(self, file_path: str) -> list[str]:
        prefix = file_path + ":"
        return [k for k in self._hashes if k.startswith(prefix)]

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / CHUNK_HASH_FILE
        path.write_text(
            json.dumps(self._hashes, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "ChunkHashStore":
        store = cls()
        path = Path(directory) / CHUNK_HASH_FILE
        if path.exists():
            store._hashes = json.loads(path.read_text(encoding="utf-8"))
        return store
