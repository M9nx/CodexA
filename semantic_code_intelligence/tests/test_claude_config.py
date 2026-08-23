from pathlib import Path
import sys
import json
from unittest.mock import patch, call

from semantic_code_intelligence.mcp.claude_config import (
    generate_claude_desktop_config,
    print_claude_desktop_config,
)

def test_generate_claude_desktop_config():
    root = Path("/fake/project").resolve()
    config = generate_claude_desktop_config(root)
    
    assert "mcpServers" in config
    assert "codexa" in config["mcpServers"]
    
    server_config = config["mcpServers"]["codexa"]
    assert server_config["command"] == sys.executable
    assert server_config["args"] == [
        "-m",
        "semantic_code_intelligence.cli.main",
        "mcp",
        "--path",
        str(root)
    ]

@patch("semantic_code_intelligence.mcp.claude_config.print")
@patch("semantic_code_intelligence.mcp.claude_config.print_info")
@patch("semantic_code_intelligence.mcp.claude_config.print_success")
def test_print_claude_desktop_config(mock_print_success, mock_print_info, mock_print):
    root = Path("/fake/project").resolve()
    print_claude_desktop_config(root)
    
    config = generate_claude_desktop_config(root)
    
    mock_print_info.assert_called_once_with(
        "Add this to your Claude Desktop config (~/.config/claude/claude_desktop_config.json):"
    )
    mock_print.assert_called_once_with(json.dumps(config, indent=2))
    mock_print_success.assert_called_once_with(
        "Or run: codexa mcp --path . (stdio mode for Claude Desktop)"
    )
