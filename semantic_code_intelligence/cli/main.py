"""Main CLI entry point for Semantic Code Intelligence."""

from __future__ import annotations

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
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Codex - Local semantic code search and AI-assisted code understanding.

    A CLI tool that indexes codebases, performs semantic search, and provides
    structured code context for AI integration.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose=verbose)


# Register all commands via the router
register_commands(cli)


def main() -> None:
    """Entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
