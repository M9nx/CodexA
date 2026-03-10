"""CLI command: review — AI-powered code review of a file."""

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

logger = get_logger("cli.review")


@click.command("review")
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
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
def review_cmd(
    ctx: click.Context,
    file: str,
    json_mode: bool,
    path: str,
) -> None:
    """Review a source file for issues, bugs, and improvements.

    Uses structural analysis + LLM to perform an AI-assisted code review.

    Examples:

        codexa review src/main.py

        codexa review src/utils.py --json
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codexa init' first.")
        ctx.exit(1)
        return

    config = load_config(root)

    from semantic_code_intelligence.cli.commands.ask_cmd import _get_provider
    from semantic_code_intelligence.llm.reasoning import ReasoningEngine

    provider = _get_provider(config)
    engine = ReasoningEngine(provider, root)
    result = engine.review(file)

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
    else:
        console.print(f"\n[bold cyan]Code Review:[/bold cyan] {result.file_path}\n")
        if result.issues:
            for issue in result.issues:
                sev = issue.get("severity", "info")
                line = issue.get("line", "?")
                msg = issue.get("message", str(issue))
                color = {"error": "red", "warning": "yellow"}.get(sev, "blue")
                console.print(f"  [{color}]{sev.upper()}[/{color}] L{line}: {msg}")
                if issue.get("suggestion"):
                    console.print(f"    [dim]Suggestion: {issue['suggestion']}[/dim]")
            console.print()
        console.print(f"[bold green]Summary:[/bold green]\n{result.summary}")
