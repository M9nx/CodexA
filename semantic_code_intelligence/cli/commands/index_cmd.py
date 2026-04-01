"""CLI command: index - Index a codebase for semantic search."""

from __future__ import annotations

import errno
import json
import signal
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


def _inspect_file_index(root: Path, file_path: str) -> None:
    """Show indexing metadata for a specific file."""
    from semantic_code_intelligence.storage.chunk_hash_store import ChunkHashStore
    from semantic_code_intelligence.storage.hash_store import HashStore
    from semantic_code_intelligence.storage.vector_store import VectorStore

    index_dir = AppConfig.index_dir(root)
    full_path = Path(file_path).resolve()
    try:
        rel_path = str(full_path.relative_to(root))
    except ValueError:
        rel_path = str(full_path)

    hash_store = HashStore.load(index_dir)
    chunk_hash_store = ChunkHashStore.load(index_dir)

    file_hash = hash_store._hashes.get(rel_path, "not indexed")

    # Count chunks for this file
    chunk_count = sum(
        1 for k in chunk_hash_store._hashes if k.startswith(str(full_path) + ":")
    )

    # Count vectors
    vector_count = 0
    try:
        store = VectorStore.load(index_dir)
        vector_count = len(store.get_vectors_for_file(str(full_path)))
    except FileNotFoundError:
        pass

    info = {
        "file": rel_path,
        "content_hash": file_hash,
        "chunks": chunk_count,
        "vectors": vector_count,
    }
    click.echo(json.dumps(info, indent=2))


def _add_single_file(root: Path, file_path: str) -> None:
    """Index a single file incrementally."""
    from semantic_code_intelligence.services.indexing_service import run_incremental_indexing

    full_path = Path(file_path).resolve()
    if not full_path.is_file():
        print_error(f"File not found: {file_path}")
        return

    result = run_incremental_indexing(
        root,
        changed_files=[str(full_path)],
        deleted_files=[],
    )
    print_success(
        f"Indexed {full_path.name}: "
        f"{result.chunks_created} chunks, {result.total_vectors} total vectors."
    )


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
    "project_path",
    required=False,
    type=click.Path(
        path_type=Path,
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
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
@click.option(
    "--add",
    "add_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Index a single file incrementally (no full scan).",
)
@click.option(
    "--inspect",
    "inspect_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Show indexing metadata for a specific file.",
)
@click.option(
    "--switch-model",
    "switch_model",
    default=None,
    type=str,
    help="Switch embedding model and re-index in one step.",
)
def index_cmd(project_path: Path | None, force: bool, watch: bool, add_file: str | None, inspect_file: str | None, switch_model: str | None) -> int:
    """Index a codebase for semantic search.

    Scans the target directory, extracts code chunks, generates embeddings,
    and stores them in the vector index.

    Use --watch to enable live incremental re-indexing on file changes.
    Use --add to index a single file without a full scan.
    Use --inspect to view indexing metadata for a file.
    Use --switch-model to change models and re-index in one step.

    \b
    Examples:
        codexa index
        codexa index --force
        codexa index --watch
        codexa index --add src/auth.py
        codexa index --inspect src/auth.py
        codexa index --switch-model jina-code
    """
    root = (project_path or Path.cwd()).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        raise click.ClickException(
            f"Project not initialized at {root}. Run 'codexa init' first."
        )

    # --- Inspect mode: show metadata for a file ---
    if inspect_file:
        _inspect_file_index(root, inspect_file)
        return

    # --- Add single file mode ---
    if add_file:
        _add_single_file(root, add_file)
        return

    # --- Switch model inline: update config + force re-index ---
    if switch_model:
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        from semantic_code_intelligence.config.settings import load_config, save_config

        resolved = resolve_model_name(switch_model)
        config = load_config(root)
        old_model = config.embedding.model_name
        if old_model == resolved:
            print_info(f"Model already set to '{resolved}' — running normal index.")
        else:
            config.embedding.model_name = resolved
            save_config(config, root)
            print_success(f"Switched model: {old_model} → {resolved}")
        force = True  # force re-index with new model

    # --- Model consistency guard ---
    if not force:
        from semantic_code_intelligence.storage.index_manifest import IndexManifest
        from semantic_code_intelligence.config.settings import load_config
        index_dir = AppConfig.index_dir(root)
        manifest = IndexManifest.load(index_dir)
        if manifest:
            config = load_config(root)
            if manifest.embedding_model != config.embedding.model_name:
                raise click.ClickException(
                    f"Embedding model changed: index uses '{manifest.embedding_model}' "
                    f"but config specifies '{config.embedding.model_name}'. "
                    f"Use --force to re-index with the new model."
                )

    if watch:
        _run_watch_mode(root, force)
        return

    print_info(f"Indexing codebase at: {root}")

    if force:
        print_info("Force mode: full re-index will be performed.")

    try:
        # Install Ctrl+C handler for partial-save safety
        _interrupted = False

        def _handle_sigint(signum, frame):  # type: ignore[no-untyped-def]
            nonlocal _interrupted
            _interrupted = True
            print_warning("\nInterrupted — saving partial index...")

        prev_handler = signal.signal(signal.SIGINT, _handle_sigint)
        try:
            result = run_indexing(project_root=root, force=force)
        finally:
            signal.signal(signal.SIGINT, prev_handler)

        if _interrupted:
            print_warning("Partial index saved. Re-run to complete.")
            return 0
    except MemoryError as e:
        print_warning(
            "Indexing skipped embedding generation due to insufficient memory. "
            "Try a smaller profile (e.g., --profile fast) or reduce embedding.batch_size."
        )
        return 0
    except Exception as e:
        message = f"{type(e).__name__}: {e}"
        msg_lower = str(e).lower()
        network_errnos = {
            errno.ENETUNREACH,
            errno.EHOSTUNREACH,
            errno.ECONNREFUSED,
            errno.ECONNRESET,
            errno.ETIMEDOUT,
        }
        err_no = getattr(e, "errno", None)
        network_like = isinstance(e, (ConnectionError, TimeoutError)) or (
            isinstance(e, OSError) and err_no in network_errnos
        )
        embedding_module = e.__class__.__module__ or ""
        embedding_like = isinstance(e, (ImportError, ValueError, RuntimeError)) and (
            embedding_module.startswith(("transformers", "sentence_transformers"))
            or any(
                key in msg_lower
                for key in ("embedding", "attn_implementation", "tokenizer")
            )
        )
        if network_like or "request" in msg_lower:
            print_warning(
                "Indexing encountered a network issue while fetching embeddings; "
                "skipping embeddings and completing with existing index. "
                f"Details: {message}"
            )
            logger.debug("Indexing error details:", exc_info=True)
            return 0
        if embedding_like:
            print_warning(
                "Embedding model setup failed; skipping embeddings and completing with existing index. "
                f"Details: {message}"
            )
            logger.debug("Embedding load error details:", exc_info=True)
            return 0
        raise click.ClickException(f"Indexing failed: {message}") from e

    if result.files_scanned == 0:
        print_warning("No indexable files found.")
    else:
        print_success(
            f"Indexed {result.files_indexed} files "
            f"({result.chunks_created} chunks, {result.total_vectors} vectors). "
            f"Skipped {result.files_skipped} unchanged files."
        )
    return 0
