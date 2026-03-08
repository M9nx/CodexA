"""Interactive TUI — terminal user interface for code search.

Provides a real-time search interface with live preview, powered by
``prompt_toolkit`` (available via ``rich`` dependency chain) or falls
back to a simple input loop if not available.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.services.search_service import SearchMode, search_codebase
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("tui")


def _format_result_line(i: int, r: Any) -> str:
    """Format a single result as a compact line for TUI display."""
    path = r.file_path
    try:
        path = str(Path(r.file_path).name)
    except Exception:
        pass
    return f"  {i:>3}. [{r.score:.3f}] {path}:L{r.start_line}-{r.end_line}  {r.language}"


def _print_results(results: list[Any], query: str) -> None:
    """Print results in a compact format."""
    if not results:
        print(f"\n  No results for: {query!r}\n")
        return
    print(f"\n  Found {len(results)} results for: {query!r}\n")
    for i, r in enumerate(results, 1):
        print(_format_result_line(i, r))
    print()


def _show_detail(results: list[Any], index: int) -> None:
    """Show full content of a result."""
    if index < 1 or index > len(results):
        print(f"  Invalid selection. Enter 1-{len(results)}.")
        return
    r = results[index - 1]
    print(f"\n  === {r.file_path} L{r.start_line}-{r.end_line} ===\n")
    for i, line in enumerate(r.content.splitlines(), start=r.start_line):
        print(f"  {i:>5} | {line}")
    print()


def run_tui(
    project_root: Path,
    mode: SearchMode = "hybrid",
    top_k: int = 10,
) -> None:
    """Run the interactive TUI search loop.

    Commands inside the TUI:
    - Type a query to search
    - ``/mode <semantic|keyword|regex|hybrid>`` to change mode
    - ``/view <n>`` to view result details
    - ``/quit`` or ``Ctrl-C`` to exit

    Args:
        project_root: Project root directory.
        mode: Default search mode.
        top_k: Number of results per query.
    """
    project_root = project_root.resolve()
    print(f"\n  CodexA Interactive Search  (mode={mode}, top_k={top_k})")
    print(f"  Project: {project_root}")
    print("  Commands: /mode <m>  /view <n>  /quit\n")

    current_mode: SearchMode = mode
    last_results: list[Any] = []

    while True:
        try:
            line = input("  search> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!\n")
            break

        if not line:
            continue

        if line.lower() in ("/quit", "/exit", "/q"):
            print("  Bye!\n")
            break

        if line.lower().startswith("/mode "):
            new_mode = line.split(maxsplit=1)[1].lower()
            if new_mode in ("semantic", "keyword", "regex", "hybrid"):
                current_mode = new_mode  # type: ignore[assignment]
                print(f"  Mode set to: {current_mode}")
            else:
                print("  Valid modes: semantic, keyword, regex, hybrid")
            continue

        if line.lower().startswith("/view "):
            try:
                idx = int(line.split()[1])
                _show_detail(last_results, idx)
            except (ValueError, IndexError):
                print("  Usage: /view <number>")
            continue

        # Execute search
        try:
            results = search_codebase(
                query=line,
                project_root=project_root,
                top_k=top_k,
                mode=current_mode,
                auto_index=True,
            )
            last_results = results
            _print_results(results, line)
        except FileNotFoundError:
            print("  Index not found. Run 'codex index' first.")
        except Exception as e:
            print(f"  Search error: {e}")
