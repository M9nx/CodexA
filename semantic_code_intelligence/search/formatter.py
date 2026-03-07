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


def format_results_rich(query: str, results: list[SearchResult]) -> None:
    """Print search results as rich formatted output to the console.

    Args:
        query: The search query.
        results: List of SearchResult objects.
    """
    if not results:
        console.print(f"\n[yellow]No results found for:[/yellow] \"{query}\"\n")
        return

    console.print(f"\n[bold cyan]Search results for:[/bold cyan] \"{query}\"")
    console.print(f"[dim]Found {len(results)} results[/dim]\n")

    for i, result in enumerate(results, 1):
        # Header with file path, lines, and score
        header = (
            f"[bold]{result.file_path}[/bold] "
            f"[dim]L{result.start_line}-L{result.end_line}[/dim] "
            f"[green]score: {result.score:.4f}[/green]"
        )

        # Code snippet with syntax highlighting
        try:
            syntax = Syntax(
                result.content.rstrip(),
                result.language if result.language != "unknown" else "text",
                line_numbers=True,
                start_line=result.start_line,
                theme="monokai",
            )
        except Exception:
            syntax = result.content.rstrip()

        panel = Panel(
            syntax,
            title=f"[bold]#{i}[/bold]  {header}",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        )
        console.print(panel)
