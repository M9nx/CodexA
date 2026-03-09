"""Main CLI entry point for Semantic Code Intelligence."""

from __future__ import annotations

import sys

import click

from semantic_code_intelligence import __version__
from semantic_code_intelligence.cli.router import register_commands
from semantic_code_intelligence.utils.logging import setup_logging


@click.group()
@click.version_option(version=__version__, prog_name="codex")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output.",
)
@click.option(
    "--pipe",
    is_flag=True,
    default=False,
    help="Pipeline mode — plain text output, no colors or spinners.",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, pipe: bool) -> None:
    """Codex - Local semantic code search and AI-assisted code understanding.

    A CLI tool that indexes codebases, performs semantic search, and provides
    structured code context for AI integration.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["pipe"] = pipe
    setup_logging(verbose=verbose)


# Register all commands via the router
register_commands(cli)


def main() -> None:
    """Entry point for the CLI application."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nInterrupted.", err=True)
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        from semantic_code_intelligence.utils.logging import error_console
        error_console.print(f"[bold red]Fatal error:[/bold red] {exc}")
        error_console.print("[dim]Run with --verbose for full traceback.[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
