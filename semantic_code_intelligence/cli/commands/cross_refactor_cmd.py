"""CLI command: cross-refactor — cross-repository refactoring suggestions."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
)

logger = get_logger("cli.cross_refactor")


@click.command("cross-refactor")
@click.option(
    "--json-output", "--json", "json_mode",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
@click.option(
    "--threshold", "-t",
    default=0.70,
    type=float,
    help="Similarity threshold for duplicate detection (0.0-1.0).",
)
@click.option(
    "--path", "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Workspace root path.",
)
@click.option("--pipe", is_flag=True, default=False, hidden=True)
@click.pass_context
def cross_refactor_cmd(
    ctx: click.Context,
    json_mode: bool,
    threshold: float,
    path: str,
    pipe: bool,
) -> None:
    """Analyse workspace repos for cross-repo refactoring opportunities.

    Scans all registered repositories in the workspace for duplicate logic,
    inconsistent patterns, and symbols that could be extracted into a shared
    library.  When an LLM is configured, generates actionable suggestions.
    """
    from semantic_code_intelligence.llm.cross_refactor import analyze_cross_repo

    root = Path(path).resolve()
    pipe = pipe or ctx.obj.get("pipe", False)

    # Optionally get LLM provider for suggestions
    provider = None
    try:
        from semantic_code_intelligence.config.settings import load_config

        config = load_config(root)
        if config.llm.provider != "none":
            from semantic_code_intelligence.cli.commands.chat_cmd import _get_provider

            provider = _get_provider(config)
    except Exception:
        logger.debug("LLM provider not available; running without AI suggestions")

    result = analyze_cross_repo(root, provider=provider, threshold=threshold)

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
    elif pipe:
        click.echo(f"Repos: {', '.join(result.repos_analyzed)}")
        click.echo(f"Symbols: {result.total_symbols}")
        click.echo(f"Matches: {len(result.matches)}")
        for m in result.matches:
            click.echo(f"  {m.repo_a}/{m.symbol_a} <-> {m.repo_b}/{m.symbol_b} ({m.similarity_note})")
        for s in result.suggestions:
            click.echo(f"  Suggestion: {s.get('title', 'N/A')}")
    else:
        from rich.table import Table
        from rich.panel import Panel

        if not result.repos_analyzed:
            print_info("No workspace found. Use 'codex workspace init' first.")
            return

        console.print(f"[bold]Cross-repo analysis[/] — {result.total_symbols} symbols across {len(result.repos_analyzed)} repos")

        if result.matches:
            table = Table(title="Cross-Repo Duplicates")
            table.add_column("Repo A")
            table.add_column("Symbol A")
            table.add_column("Repo B")
            table.add_column("Symbol B")
            table.add_column("Similarity")
            for m in result.matches[:20]:
                table.add_row(m.repo_a, m.symbol_a, m.repo_b, m.symbol_b, m.similarity_note)
            console.print(table)
        else:
            print_info("No cross-repo duplicates detected.")

        if result.suggestions:
            console.print()
            for s in result.suggestions:
                console.print(Panel(
                    f"{s.get('description', '')}",
                    title=f"[bold]{s.get('title', 'Suggestion')}[/] [{s.get('priority', 'medium')}]",
                ))
