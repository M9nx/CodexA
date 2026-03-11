"""Claude Desktop configuration helper — auto-generates MCP config."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from semantic_code_intelligence.utils.logging import get_logger, print_info, print_success

logger = get_logger("mcp.claude_config")


def generate_claude_desktop_config(project_root: Path) -> dict:
    """Generate a Claude Desktop MCP server configuration block for CodexA."""
    python = sys.executable
    return {
        "mcpServers": {
            "codexa": {
                "command": python,
                "args": ["-m", "semantic_code_intelligence.cli.main", "mcp", "--path", str(project_root.resolve())],
            }
        }
    }


def print_claude_desktop_config(project_root: Path) -> None:
    """Print the Claude Desktop configuration to stdout."""
    config = generate_claude_desktop_config(project_root)
    print_info("Add this to your Claude Desktop config (~/.config/claude/claude_desktop_config.json):")
    print(json.dumps(config, indent=2))
    print_success("Or run: codexa mcp --path . (stdio mode for Claude Desktop)")
