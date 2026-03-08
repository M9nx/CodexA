"""Repository scanner — walks the file tree and filters indexable files.

Respects ``.gitignore`` and ``.codexaignore`` patterns for fine-grained
exclusion control.
"""

from __future__ import annotations

import fnmatch
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


def _load_ignore_patterns(root: Path) -> list[str]:
    """Load glob patterns from .codexaignore file (if it exists).

    Each non-empty, non-comment line is treated as a glob pattern
    matched against relative paths (similar to .gitignore).
    """
    ignore_file = root / ".codexaignore"
    if not ignore_file.exists():
        return []
    patterns: list[str] = []
    for line in ignore_file.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(stripped)
    return patterns


def _matches_ignore_patterns(relative_path: str, patterns: list[str]) -> bool:
    """Check whether a relative path matches any .codexaignore pattern."""
    for pattern in patterns:
        if fnmatch.fnmatch(relative_path, pattern):
            return True
        # Also check against each path component for directory patterns
        if fnmatch.fnmatch(relative_path.replace("\\", "/"), pattern):
            return True
    return False


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

    Respects both the config-based ``ignore_dirs`` and any patterns
    defined in ``.codexaignore`` at the project root.

    Args:
        root: Root directory to scan.
        index_config: Indexing configuration. Uses defaults if None.

    Returns:
        List of ScannedFile objects for all matching files.
    """
    if index_config is None:
        index_config = IndexConfig()

    root = root.resolve()
    ignore_patterns = _load_ignore_patterns(root)
    results: list[ScannedFile] = []

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue

        if file_path.suffix not in index_config.extensions:
            continue

        if should_ignore(file_path, root, index_config.ignore_dirs):
            continue

        # Check .codexaignore patterns
        try:
            rel = str(file_path.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
        if ignore_patterns and _matches_ignore_patterns(rel, ignore_patterns):
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
