"""CLI command: init - Initialize a new project for semantic code intelligence."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import (
    AppConfig,
    init_project,
    load_config,
)
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_success,
)

logger = get_logger("cli.init")


@click.command("init")
@click.argument(
    "path",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
@click.pass_context
def init_cmd(ctx: click.Context, path: str) -> None:
    """Initialize a project for semantic code indexing.

    Creates a .codex/ directory with default configuration and an empty index.
    """
    root = Path(path).resolve()

    # Check if already initialized
    config_dir = AppConfig.config_dir(root)
    if config_dir.exists():
        print_info(f"Project already initialized at {root}")
        print_info(f"Config directory: {config_dir}")
        return

    try:
        config, config_path = init_project(root)
        print_success(f"Initialized project at {root}")
        print_info(f"Config file: {config_path}")
        print_info(f"Index directory: {AppConfig.index_dir(root)}")
        logger.debug("Default config: %s", config.model_dump())
    except OSError as e:
        print_error(f"Failed to initialize project: {e}")
        ctx.exit(1)
