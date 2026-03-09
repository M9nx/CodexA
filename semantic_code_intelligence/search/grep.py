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

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "line_content": self.line_content,
            "column": self.column,
        }


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

        if data.get("type") == "match":
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
) -> GrepResult:
    """Pure-Python grep fallback over raw files."""
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(pattern, flags)
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
        # Skip hidden directories
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(root)
        if str(rel_dir).startswith(("node_modules", "__pycache__", ".git")):
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

            for lineno, line in enumerate(content.splitlines(), start=1):
                m = compiled.search(line)
                if m:
                    rel_path = str(fpath.relative_to(root))
                    matches.append(GrepMatch(
                        file_path=rel_path,
                        line_number=lineno,
                        line_content=line,
                        column=m.start(),
                    ))
                    files_matched.add(rel_path)

                    if len(matches) >= max_results:
                        return GrepResult(
                            pattern=pattern,
                            matches=matches,
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
    """
    if use_ripgrep and _has_ripgrep():
        try:
            return _ripgrep_search(
                pattern, root,
                case_insensitive=case_insensitive,
                max_results=max_results,
                file_glob=file_glob,
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
    )
