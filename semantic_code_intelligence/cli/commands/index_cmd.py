"""CLI command: index - Index a codebase for semantic search."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig
from semantic_code_intelligence.services.indexing_service import run_indexing
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
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(
            f"Project not initialized at {root}. Run 'codexa init' first."
        )
        ctx.exit(1)
        return

    print_info(f"Indexing codebase at: {root}")

    if force:
        print_info("Force mode: full re-index will be performed.")

    try:
        result = run_indexing(project_root=root, force=force)
    except Exception as e:
        print_error(f"Indexing failed: {e}")
        logger.debug("Indexing error details:", exc_info=True)
        ctx.exit(1)
        return

    if result.files_scanned == 0:
        print_warning("No indexable files found.")
    else:
        print_success(
            f"Indexed {result.files_indexed} files "
            f"({result.chunks_created} chunks, {result.total_vectors} vectors). "
            f"Skipped {result.files_skipped} unchanged files."
        )
