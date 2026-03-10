"""CLI command: serve — start the CodexA bridge server.

Supports MCP-over-SSE via ``--mcp`` flag for AI agent integration.
"""

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
@click.option(
    "--mcp",
    "mcp_mode",
    is_flag=True,
    default=False,
    help="Expose MCP tools over HTTP+SSE (for AI agent integration).",
)
@click.pass_context
def serve_cmd(
    ctx: click.Context,
    host: str,
    port: int,
    path: str,
    mcp_mode: bool,
) -> None:
    """Start the CodexA bridge server for external AI integration.

    Use --mcp to expose MCP-compliant tools over HTTP with SSE streaming.

    \b
    Examples:
        codexa serve
        codexa serve --port 8080
        codexa serve --mcp
    """
    project_root = Path(path)

    if mcp_mode:
        _run_mcp_http(project_root, host, port)
        return

    from semantic_code_intelligence.bridge.server import BridgeServer

    server = BridgeServer(project_root, host=host, port=port)

    print_info(f"Starting CodexA bridge server on {server.url}")
    print_info("Press Ctrl+C to stop.")

    server.start()


def _run_mcp_http(project_root: Path, host: str, port: int) -> None:
    """Run MCP tools over HTTP+SSE using the streamable-http transport."""
    try:
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        import uvicorn
    except ImportError:
        # Fallback: just run MCP stdio server
        print_info("SSE/Starlette not installed — falling back to stdio MCP.")
        from semantic_code_intelligence.mcp import run_mcp_server
        run_mcp_server(project_root)
        return

    from semantic_code_intelligence.mcp import _create_server

    server = _create_server(project_root)
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(
                streams[0], streams[1],
                server.create_initialization_options(),
            )

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    print_info(f"MCP-over-SSE server on http://{host}:{port}/sse")
    print_info("Press Ctrl+C to stop.")
    uvicorn.run(app, host=host, port=port, log_level="info")
