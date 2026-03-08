"""CLI command: mcp - Start the MCP (Model Context Protocol) server."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig
from semantic_code_intelligence.utils.logging import get_logger, print_error, print_info

logger = get_logger("cli.mcp")


@click.command("mcp")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def mcp_cmd(ctx: click.Context, path: str) -> None:
    """Start the MCP server for AI agent integration.

    Runs a JSON-RPC server over stdio, compatible with Claude Desktop,
    Cursor, and other MCP-compatible AI tools.

    \b
    Configuration for Claude Desktop (claude_desktop_config.json):
      {
        "mcpServers": {
          "codex": {
            "command": "codex",
            "args": ["mcp", "--path", "/your/project"]
          }
        }
      }
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codex init' first.")
        ctx.exit(1)
        return

    from semantic_code_intelligence.mcp import run_mcp_server
    run_mcp_server(root)
