"""CLI command: tui - Launch interactive terminal search interface."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig
from semantic_code_intelligence.utils.logging import get_logger, print_error

logger = get_logger("cli.tui")


@click.command("tui")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["semantic", "keyword", "regex", "hybrid"], case_sensitive=False),
    default="hybrid",
    help="Default search mode.",
)
@click.option(
    "--top-k",
    "-k",
    default=10,
    type=int,
    help="Results per query.",
)
@click.pass_context
def tui_cmd(ctx: click.Context, path: str, mode: str, top_k: int) -> None:
    """Launch the interactive terminal search interface.

    Provides a live search REPL with mode switching and result preview.

    Examples:

    \b
        codexa tui
        codexa tui --mode hybrid -k 20
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codexa init' first.")
        ctx.exit(1)
        return

    from semantic_code_intelligence.tui import run_tui
    run_tui(root, mode=mode, top_k=top_k)  # type: ignore[arg-type]
