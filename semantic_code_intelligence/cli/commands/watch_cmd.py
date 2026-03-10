"""CLI command: watch — run the background indexing daemon."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig
from semantic_code_intelligence.daemon.watcher import IndexingDaemon
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_success,
)

logger = get_logger("cli.watch")


@click.command("watch")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.option(
    "--interval",
    "-i",
    default=2.0,
    type=float,
    help="Polling interval in seconds.",
)
@click.pass_context
def watch_cmd(ctx: click.Context, path: str, interval: float) -> None:
    """Watch the repository for changes and re-index automatically.

    Starts a background daemon that polls for file changes and triggers
    incremental re-indexing.

    Press Ctrl+C to stop.

    Examples:

        codexa watch

        codexa watch --interval 5
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error("Project not initialized. Run 'codexa init' first.")
        return

    print_info(f"Starting watch daemon for {root} (poll every {interval}s)")
    print_info("Press Ctrl+C to stop.")

    daemon = IndexingDaemon(root, poll_interval=interval)
    daemon.start()

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        daemon.stop()
        print_success("Watch daemon stopped.")
