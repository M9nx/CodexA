"""CLI command: index - Index a codebase for semantic search."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger("cli.index")


@click.command("index")
@click.argument(
    "path",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force full re-index, ignoring cache.",
)
@click.pass_context
def index_cmd(ctx: click.Context, path: str, force: bool) -> None:
    """Index a codebase for semantic search.

    Scans the target directory, extracts code chunks, generates embeddings,
    and stores them in the vector index.

    This is a Phase 1 stub. Full indexing is implemented in Phase 2.
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(
            f"Project not initialized at {root}. Run 'codex init' first."
        )
        ctx.exit(1)
        return

    config = load_config(root)
    logger.debug("Loaded config: %s", config.model_dump())

    print_info(f"Indexing codebase at: {root}")

    if force:
        print_info("Force mode: full re-index will be performed.")

    # Phase 1 stub - actual indexing will be implemented in Phase 2
    # For now, scan files and report what would be indexed
    extensions = config.index.extensions
    ignore_dirs = config.index.ignore_dirs

    file_count = 0
    for file_path in root.rglob("*"):
        if file_path.is_file() and file_path.suffix in extensions:
            # Check if any parent is in ignore list
            parts = file_path.relative_to(root).parts
            if any(part in ignore_dirs for part in parts):
                continue
            file_count += 1

    if file_count == 0:
        print_warning("No indexable files found.")
    else:
        print_success(f"Found {file_count} files to index.")
        print_info(
            "Full indexing with embeddings will be available in Phase 2."
        )
