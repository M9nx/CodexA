"""Repository scanner — walks the file tree and filters indexable files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from semantic_code_intelligence.config.settings import AppConfig, IndexConfig


@dataclass
class ScannedFile:
    """Represents a single file discovered during scanning."""

    path: Path
    relative_path: str
    extension: str
    size_bytes: int
    content_hash: str


def compute_file_hash(file_path: Path) -> str:
    """Compute a SHA-256 hash of a file's contents for change detection.

    Args:
        file_path: Path to the file.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def should_ignore(path: Path, root: Path, ignore_dirs: set[str]) -> bool:
    """Check if a path should be ignored based on directory names.

    Args:
        path: The file or directory path to check.
        root: The project root path.
        ignore_dirs: Set of directory names to ignore.

    Returns:
        True if the path should be skipped.
    """
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in ignore_dirs for part in parts)


def scan_repository(
    root: Path,
    index_config: IndexConfig | None = None,
) -> list[ScannedFile]:
    """Scan a repository and return a list of indexable files.

    Args:
        root: Root directory to scan.
        index_config: Indexing configuration. Uses defaults if None.

    Returns:
        List of ScannedFile objects for all matching files.
    """
    if index_config is None:
        index_config = IndexConfig()

    root = root.resolve()
    results: list[ScannedFile] = []

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue

        if file_path.suffix not in index_config.extensions:
            continue

        if should_ignore(file_path, root, index_config.ignore_dirs):
            continue

        try:
            size = file_path.stat().st_size
            content_hash = compute_file_hash(file_path)
            results.append(
                ScannedFile(
                    path=file_path,
                    relative_path=str(file_path.relative_to(root)),
                    extension=file_path.suffix,
                    size_bytes=size,
                    content_hash=content_hash,
                )
            )
        except (OSError, PermissionError):
            continue

    return results
