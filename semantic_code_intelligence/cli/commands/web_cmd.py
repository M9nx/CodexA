"""CLI command: web — start the CodexA web interface and REST API."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import get_logger, print_info

logger = get_logger("cli.web")


@click.command("web")
@click.option(
    "--host",
    "-h",
    default="127.0.0.1",
    type=str,
    help="Host to bind the web server to.",
)
@click.option(
    "--port",
    "-p",
    default=8080,
    type=int,
    help="Port to bind the web server to.",
)
@click.option(
    "--path",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def web_cmd(
    ctx: click.Context,
    host: str,
    port: int,
    path: str,
) -> None:
    """Start the CodexA web interface and REST API server.

    Provides a browser-based search UI and JSON REST endpoints
    for programmatic access.  Uses only the Python standard library.

    Examples:

        codex web

        codex web --port 9000

        codex web --host 0.0.0.0 --port 8080 --path /my/project
    """
    from semantic_code_intelligence.web.server import WebServer

    project_root = Path(path)
    server = WebServer(project_root, host=host, port=port)
    print_info(f"Starting CodexA web server on {server.url}")
    print_info("Press Ctrl+C to stop.")
    server.start()
