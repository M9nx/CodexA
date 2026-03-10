"""Raw filesystem grep — search files directly without requiring an index.

Provides ripgrep-compatible grep that works on raw files, not just indexed
chunks.  Uses ``ripgrep`` if available on PATH for maximum speed, falling
back to a pure-Python implementation.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("search.grep")


@dataclass
class GrepMatch:
    """A single grep match."""

    file_path: str
    line_number: int
    line_content: str
    column: int = 0
    is_context: bool = False  # True for -A/-B context lines

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "line_content": self.line_content,
            "column": self.column,
        }
        if self.is_context:
            d["is_context"] = True
        return d


@dataclass
class GrepResult:
    """Results of a grep operation."""

    pattern: str
    matches: list[GrepMatch]
    files_searched: int
    files_matched: int
    backend: str  # "ripgrep" or "python"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "match_count": len(self.matches),
            "files_searched": self.files_searched,
            "files_matched": self.files_matched,
            "backend": self.backend,
            "matches": [m.to_dict() for m in self.matches],
        }


def _has_ripgrep() -> str | None:
    """Return path to ripgrep binary if available."""
    return shutil.which("rg")


def _ripgrep_search(
    pattern: str,
    root: Path,
    *,
    case_insensitive: bool = True,
    max_results: int = 100,
    file_glob: str | None = None,
    context_before: int = 0,
    context_after: int = 0,
    word_match: bool = False,
    invert_match: bool = False,
    include_hidden: bool = False,
    count_only: bool = False,
) -> GrepResult:
    """Run ripgrep and parse JSON output."""
    rg = _has_ripgrep()
    if not rg:
        raise RuntimeError("ripgrep not found")

    cmd = [rg, "--json", "--max-count", str(max_results)]
    if case_insensitive:
        cmd.append("-i")
    if file_glob:
        cmd.extend(["-g", file_glob])
    if context_before > 0:
        cmd.extend(["-B", str(context_before)])
    if context_after > 0:
        cmd.extend(["-A", str(context_after)])
    if word_match:
        cmd.append("-w")
    if invert_match:
        cmd.append("--invert-match")
    if include_hidden:
        cmd.append("--hidden")
    if count_only:
        cmd.append("--count")

    cmd.append(pattern)
    cmd.append(str(root))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        logger.warning("ripgrep timed out after 30s")
        return GrepResult(pattern=pattern, matches=[], files_searched=0,
                          files_matched=0, backend="ripgrep")

    matches: list[GrepMatch] = []
    files_matched: set[str] = set()

    for line in result.stdout.splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        dtype = data.get("type")
        if dtype == "match":
            match_data = data["data"]
            path_text = match_data["path"]["text"]
            for submatch in match_data.get("submatches", []):
                matches.append(GrepMatch(
                    file_path=path_text,
                    line_number=match_data["line_number"],
                    line_content=match_data["lines"]["text"].rstrip("\n"),
                    column=submatch.get("start", 0),
                ))
            files_matched.add(path_text)
        elif dtype == "context":
            ctx_data = data["data"]
            path_text = ctx_data["path"]["text"]
            matches.append(GrepMatch(
                file_path=path_text,
                line_number=ctx_data["line_number"],
                line_content=ctx_data["lines"]["text"].rstrip("\n"),
                column=0,
                is_context=True,
            ))

    return GrepResult(
        pattern=pattern,
        matches=matches[:max_results],
        files_searched=0,  # ripgrep doesn't report this easily
        files_matched=len(files_matched),
        backend="ripgrep",
    )


def _python_grep(
    pattern: str,
    root: Path,
    *,
    case_insensitive: bool = True,
    max_results: int = 100,
    extensions: set[str] | None = None,
    context_before: int = 0,
    context_after: int = 0,
    word_match: bool = False,
    invert_match: bool = False,
    include_hidden: bool = False,
) -> GrepResult:
    """Pure-Python grep fallback over raw files."""
    actual_pattern = rf"\b{pattern}\b" if word_match else pattern
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(actual_pattern, flags)
    except re.error as exc:
        logger.warning("Invalid regex pattern %r: %s", pattern, exc)
        return GrepResult(pattern=pattern, matches=[], files_searched=0,
                          files_matched=0, backend="python")

    if extensions is None:
        try:
            config = load_config(root)
            extensions = set(config.index.extensions)
        except Exception:
            extensions = {".py", ".js", ".ts", ".java", ".go", ".rs", ".rb", ".cpp", ".cs"}

    matches: list[GrepMatch] = []
    files_searched = 0
    files_matched: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden directories unless include_hidden
        if not include_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(root)
        if str(rel_dir).startswith(("node_modules", "__pycache__")):
            continue
        if not include_hidden and str(rel_dir).startswith(".git"):
            continue

        for fname in filenames:
            if Path(fname).suffix not in extensions:
                continue

            fpath = Path(dirpath) / fname
            files_searched += 1

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue

            lines = content.splitlines()
            rel_path = str(fpath.relative_to(root))
            file_had_match = False

            # Collect matching line numbers first
            matching_linenos: set[int] = set()
            for lineno_idx, line in enumerate(lines):
                found = compiled.search(line)
                if (found and not invert_match) or (not found and invert_match):
                    matching_linenos.add(lineno_idx)

            if not matching_linenos:
                continue

            file_had_match = True
            files_matched.add(rel_path)

            # Build output with context
            emitted: set[int] = set()
            for lineno_idx in sorted(matching_linenos):
                # Context before
                for ctx_idx in range(max(0, lineno_idx - context_before), lineno_idx):
                    if ctx_idx not in emitted:
                        emitted.add(ctx_idx)
                        matches.append(GrepMatch(
                            file_path=rel_path,
                            line_number=ctx_idx + 1,
                            line_content=lines[ctx_idx],
                            column=0,
                            is_context=True,
                        ))
                # Matching line
                if lineno_idx not in emitted:
                    emitted.add(lineno_idx)
                    m = compiled.search(lines[lineno_idx])
                    matches.append(GrepMatch(
                        file_path=rel_path,
                        line_number=lineno_idx + 1,
                        line_content=lines[lineno_idx],
                        column=m.start() if m else 0,
                    ))
                # Context after
                for ctx_idx in range(lineno_idx + 1, min(len(lines), lineno_idx + 1 + context_after)):
                    if ctx_idx not in emitted:
                        emitted.add(ctx_idx)
                        matches.append(GrepMatch(
                            file_path=rel_path,
                            line_number=ctx_idx + 1,
                            line_content=lines[ctx_idx],
                            column=0,
                            is_context=True,
                        ))

                if len(matches) >= max_results:
                    return GrepResult(
                        pattern=pattern,
                        matches=matches[:max_results],
                        files_searched=files_searched,
                        files_matched=len(files_matched),
                        backend="python",
                    )

    return GrepResult(
        pattern=pattern,
        matches=matches,
        files_searched=files_searched,
        files_matched=len(files_matched),
        backend="python",
    )


def grep_search(
    pattern: str,
    root: Path,
    *,
    case_insensitive: bool = True,
    max_results: int = 100,
    use_ripgrep: bool = True,
    file_glob: str | None = None,
    context_before: int = 0,
    context_after: int = 0,
    word_match: bool = False,
    invert_match: bool = False,
    include_hidden: bool = False,
    count_only: bool = False,
) -> GrepResult:
    """Search raw files using ripgrep (if available) or Python fallback.

    Unlike indexed search modes, this searches the actual filesystem
    without requiring an index. Instant results, zero setup.

    Args:
        pattern: Regex pattern to search for.
        root: Project root to search.
        case_insensitive: Case-insensitive matching.
        max_results: Maximum matches to return.
        use_ripgrep: Try ripgrep first (recommended).
        file_glob: Optional glob to filter files (e.g., "*.py").
        context_before: Lines of context before each match (-B).
        context_after: Lines of context after each match (-A).
        word_match: Match whole words only (-w).
        invert_match: Show non-matching lines (-v).
        include_hidden: Include hidden files/directories.
        count_only: Only return match counts per file (-c).
    """
    if use_ripgrep and _has_ripgrep():
        try:
            return _ripgrep_search(
                pattern, root,
                case_insensitive=case_insensitive,
                max_results=max_results,
                file_glob=file_glob,
                context_before=context_before,
                context_after=context_after,
                word_match=word_match,
                invert_match=invert_match,
                include_hidden=include_hidden,
                count_only=count_only,
            )
        except Exception:
            logger.debug("ripgrep failed, falling back to Python grep")

    extensions = None
    if file_glob:
        # Convert glob like "*.py" to extension set
        import fnmatch
        extensions = {Path(file_glob.lstrip("*")).suffix} if "." in file_glob else None

    return _python_grep(
        pattern, root,
        case_insensitive=case_insensitive,
        max_results=max_results,
        extensions=extensions,
        context_before=context_before,
        context_after=context_after,
        word_match=word_match,
        invert_match=invert_match,
        include_hidden=include_hidden,
    )
