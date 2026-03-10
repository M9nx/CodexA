"""CLI command: index - Index a codebase for semantic search."""

from __future__ import annotations

import time
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


def _run_watch_mode(root: Path, force: bool) -> None:
    """Run continuous watch-mode indexing with live incremental updates."""
    from semantic_code_intelligence.daemon.watcher import NativeFileWatcher
    from semantic_code_intelligence.services.indexing_service import run_incremental_indexing

    # Initial index
    print_info("Watch mode: performing initial index...")
    result = run_indexing(project_root=root, force=force)
    print_success(
        f"Initial index: {result.files_indexed} files, "
        f"{result.chunks_created} chunks, {result.total_vectors} vectors."
    )
    print_info("Watching for changes... (press Ctrl+C to stop)")

    update_count = 0

    def _on_changes(events: list) -> None:
        nonlocal update_count
        changed = [str(e.path) for e in events if e.change_type in ("created", "modified")]
        deleted = [str(e.path) for e in events if e.change_type == "deleted"]
        if not changed and not deleted:
            return
        try:
            inc = run_incremental_indexing(root, changed_files=changed, deleted_files=deleted)
            update_count += 1
            print_success(
                f"[update #{update_count}] Re-indexed {inc.files_indexed} files "
                f"({inc.chunks_created} chunks). {len(deleted)} deleted."
            )
        except Exception as exc:
            logger.debug("Incremental indexing error", exc_info=True)
            print_error(f"Incremental indexing failed: {exc}")

    watcher = NativeFileWatcher(root)
    watcher.on_change(_on_changes)
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        watcher.stop()
        print_success(f"Watch mode stopped. {update_count} incremental updates applied.")


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
@click.option(
    "--watch",
    "-w",
    is_flag=True,
    default=False,
    help="Watch for file changes and re-index incrementally.",
)
@click.pass_context
def index_cmd(ctx: click.Context, path: str, force: bool, watch: bool) -> None:
    """Index a codebase for semantic search.

    Scans the target directory, extracts code chunks, generates embeddings,
    and stores them in the vector index.

    Use --watch to enable live incremental re-indexing on file changes.

    \b
    Examples:
        codexa index
        codexa index --force
        codexa index --watch
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(
            f"Project not initialized at {root}. Run 'codexa init' first."
        )
        ctx.exit(1)
        return

    if watch:
        _run_watch_mode(root, force)
        return

    print_info(f"Indexing codebase at: {root}")

    if force:
        print_info("Force mode: full re-index will be performed.")

    try:
        result = run_indexing(project_root=root, force=force)
    except MemoryError as e:
        print_error(f"Indexing failed: {e}")
        print_info("Tip: semantic indexing needs the ML extras and enough RAM. Install with 'pip install codexa[ml]' and prefer ONNX or a machine with at least 2 GB available RAM.")
        ctx.exit(1)
        return
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
