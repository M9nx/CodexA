"""Repository-wide index scaffolding.

Single source for "which files does CodexA consider indexable" so that
consumers building an ad-hoc index (ToolRegistry, ContextProvider, ...)
scan and parse an identical set of files.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from semantic_code_intelligence.utils.logging import get_logger

if TYPE_CHECKING:
    from semantic_code_intelligence.context.engine import ContextBuilder

logger = get_logger("indexing")


def scan_indexable_files(root: Path) -> list[str]:
    """Return absolute paths of all indexable files under *root*.

    Applies the project's :class:`~semantic_code_intelligence.config.
    settings.IndexConfig` (extensions, ignore dirs, ``.codexaignore``) —
    the same filter the full indexing pipeline uses.
    """
    from semantic_code_intelligence.config.settings import load_config
    from semantic_code_intelligence.indexing.scanner import scan_repository

    root = Path(root).resolve()
    config = load_config(root)
    return [str(root / sf.relative_path) for sf in scan_repository(root, config.index)]


def index_repository(
    builder: ContextBuilder, root: Path
) -> int:
    """Index every indexable file under *root* into *builder* (once).

    Files already present in *builder* are skipped.  Returns the number
    of newly indexed files.
    """
    count = 0
    for path in scan_indexable_files(root):
        if builder.has_file(path):
            continue
        try:
            builder.index_file(path)
            count += 1
        except Exception:
            logger.debug("Failed to index %s", path)
    return count
