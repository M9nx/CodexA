"""Search result formatter — renders search results for CLI and JSON output."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from semantic_code_intelligence.services.search_service import SearchResult
from semantic_code_intelligence.utils.logging import console


def format_results_json(query: str, results: list[SearchResult], top_k: int) -> str:
    """Format search results as a JSON string for AI integration.

    Args:
        query: The search query.
        results: List of SearchResult objects.
        top_k: Number of results requested.

    Returns:
        Pretty-printed JSON string.
    """
    output: dict[str, Any] = {
        "query": query,
        "top_k": top_k,
        "result_count": len(results),
        "results": [r.to_dict() for r in results],
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


def format_results_jsonl(results: list[SearchResult], *, scores: bool = False) -> str:
    """Format search results as JSONL (one JSON object per line).

    Each line is a self-contained JSON object suitable for piping into
    ``jq``, ``fzf``, or streaming ingestion.

    When *scores* is True an extra ``"_score_prefix"`` key is included.
    """
    lines: list[str] = []
    for r in results:
        d = r.to_dict()
        if scores:
            d["_score_prefix"] = f"[{r.score:.3f}]"
        lines.append(json.dumps(d, ensure_ascii=False))
    return "\n".join(lines)


def format_results_rich(
    query: str,
    results: list[SearchResult],
    *,
    line_numbers: bool = False,
    context_lines: int = 0,
    show_scores: bool = False,
) -> None:
    """Print search results as rich formatted output to the console.

    Args:
        query: The search query.
        results: List of SearchResult objects.
        line_numbers: If True, prefix code lines with line numbers (grep -n).
        context_lines: Number of extra context lines to display around content.
        show_scores: If True, include score badge in each panel header.
    """
    if not results:
        console.print(f"\n[yellow]No results found for:[/yellow] \"{query}\"\n")
        return

    console.print(f"\n[bold cyan]Search results for:[/bold cyan] \"{query}\"")
    console.print(f"[dim]Found {len(results)} results[/dim]\n")

    for i, result in enumerate(results, 1):
        # Optionally expand context lines from the file on disk
        content = result.content
        start = result.start_line
        if context_lines > 0:
            content, start = _expand_context(result, context_lines)

        # Header with file path, lines, and score
        header = (
            f"[bold]{result.file_path}[/bold] "
            f"[dim]L{start}-L{result.end_line + context_lines}[/dim] "
            f"[green]score: {result.score:.4f}[/green]"
        )

        # Code snippet with syntax highlighting
        try:
            syntax: str | Syntax = Syntax(
                content.rstrip(),
                result.language if result.language != "unknown" else "text",
                line_numbers=True if line_numbers else True,
                start_line=start,
                theme="monokai",
            )
        except Exception:
            syntax = content.rstrip()

        panel = Panel(
            syntax,
            title=f"[bold]#{i}[/bold]  {header}",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        )
        console.print(panel)


def _expand_context(result: SearchResult, ctx: int) -> tuple[str, int]:
    """Read extra context lines from the original file on disk."""
    from pathlib import Path

    fp = Path(result.file_path)
    if not fp.is_file():
        return result.content, result.start_line
    try:
        lines = fp.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError:
        return result.content, result.start_line

    new_start = max(1, result.start_line - ctx)
    new_end = min(len(lines), result.end_line + ctx)
    expanded = "".join(lines[new_start - 1 : new_end])
    return expanded, new_start
