"""CLI command: suggest — AI-powered intelligent suggestions for a symbol/file."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
)

logger = get_logger("cli.suggest")


@click.command("suggest")
@click.argument("target", type=str)
@click.option(
    "--top-k",
    "-k",
    default=5,
    type=int,
    help="Number of context snippets to consider.",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def suggest_cmd(
    ctx: click.Context,
    target: str,
    top_k: int,
    json_mode: bool,
    path: str,
) -> None:
    """Get intelligent suggestions for a symbol, file, or topic.

    Combines call-graph, dependency, and semantic data with LLM reasoning
    to produce actionable suggestions with "why" reasoning.

    Examples:

        codex suggest search_codebase

        codex suggest "error handling patterns" --json
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codex init' first.")
        ctx.exit(1)
        return

    config = load_config(root)

    from semantic_code_intelligence.cli.commands.ask_cmd import _get_provider
    from semantic_code_intelligence.llm.reasoning import ReasoningEngine

    provider = _get_provider(config)
    engine = ReasoningEngine(provider, root)
    result = engine.suggest(target, top_k=top_k)

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
    else:
        console.print(f"\n[bold cyan]Suggestions for:[/bold cyan] {result.target}\n")
        if result.suggestions:
            for i, sug in enumerate(result.suggestions, 1):
                title = sug.get("title", f"Suggestion {i}")
                desc = sug.get("description", "")
                reason = sug.get("reason", "")
                priority = sug.get("priority", "medium")
                color = {"high": "red", "medium": "yellow", "low": "green"}.get(
                    priority, "blue"
                )
                console.print(f"  [{color}]{priority.upper()}[/{color}] {title}")
                if desc:
                    console.print(f"    {desc}")
                if reason:
                    console.print(f"    [dim]Why: {reason}[/dim]")
                console.print()
        else:
            console.print("[dim]No suggestions generated.[/dim]")
