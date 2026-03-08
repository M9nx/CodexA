"""Full-section extraction — expands search results to complete functions/classes.

When a search hit lands inside a function or class, this module looks up
the symbol registry to return the *entire* enclosing symbol body, not
just the matching chunk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from semantic_code_intelligence.services.search_service import SearchResult
from semantic_code_intelligence.storage.symbol_registry import SymbolRegistry
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("search.section")


def _read_lines(file_path: str, start: int, end: int) -> str:
    """Read lines [start, end] (1-indexed) from a file."""
    try:
        all_lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, PermissionError):
        return ""
    s = max(0, start - 1)
    e = min(len(all_lines), end)
    return "\n".join(all_lines[s:e])


def expand_to_full_section(
    results: list[SearchResult],
    project_root: Path,
    index_dir: Path,
) -> list[SearchResult]:
    """Expand each search result to the full enclosing function/class.

    If a symbol boundary cannot be found (e.g. unsupported language),
    the original result is returned unchanged.

    Args:
        results: Search results to expand.
        project_root: Root of the project (for resolving paths).
        index_dir: Index directory (for symbol registry).

    Returns:
        New list of SearchResult with expanded content and line ranges.
    """
    try:
        registry = SymbolRegistry.load(index_dir)
    except Exception:
        logger.debug("Symbol registry not found; returning results unchanged.")
        return results

    expanded: list[SearchResult] = []
    seen_keys: set[str] = set()

    for r in results:
        # Normalise to relative path for registry lookup
        try:
            rel = str(Path(r.file_path).relative_to(project_root))
        except ValueError:
            rel = r.file_path

        # Find the tightest enclosing symbol
        file_symbols = registry.find_by_file(rel)
        best = None
        best_span = float("inf")
        for sym in file_symbols:
            if sym.start_line <= r.start_line and sym.end_line >= r.end_line:
                span = sym.end_line - sym.start_line
                if span < best_span:
                    best = sym
                    best_span = span

        if best is not None:
            start = best.start_line
            end = best.end_line
            dedup_key = f"{r.file_path}:{start}:{end}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            content = _read_lines(r.file_path, start, end)
            expanded.append(
                SearchResult(
                    file_path=r.file_path,
                    start_line=start,
                    end_line=end,
                    language=r.language,
                    content=content or r.content,
                    score=r.score,
                    chunk_index=r.chunk_index,
                )
            )
        else:
            dedup_key = f"{r.file_path}:{r.start_line}:{r.end_line}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            expanded.append(r)

    return expanded
