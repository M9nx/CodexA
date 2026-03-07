"""CLI command: serve — start the CodexA bridge server."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_info,
)

logger = get_logger("cli.serve")


@click.command("serve")
@click.option(
    "--host",
    "-h",
    default="127.0.0.1",
    type=str,
    help="Host to bind the bridge server to.",
)
@click.option(
    "--port",
    "-p",
    default=24842,
    type=int,
    help="Port to bind the bridge server to.",
)
@click.option(
    "--path",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def serve_cmd(
    ctx: click.Context,
    host: str,
    port: int,
    path: str,
) -> None:
    """Start the CodexA bridge server for external AI integration."""
    from semantic_code_intelligence.bridge.server import BridgeServer

    project_root = Path(path)
    server = BridgeServer(project_root, host=host, port=port)

    print_info(f"Starting CodexA bridge server on {server.url}")
    print_info("Press Ctrl+C to stop.")

    server.start()
