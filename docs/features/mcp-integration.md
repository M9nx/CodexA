# MCP Integration

CodexA implements a **Model Context Protocol (MCP)** server, enabling
direct integration with Claude Desktop, Cursor, and other MCP-compatible
AI tools.

## Quick Start

```bash
codex mcp --path /your/project
```

This starts a JSON-RPC server over stdio that exposes all 8 CodexA tools.

## Claude Desktop Setup

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codex": {
      "command": "codex",
      "args": ["mcp", "--path", "/your/project"]
    }
  }
}
```

After restarting Claude Desktop, CodexA tools appear in the tool picker.

## Cursor Setup

In Cursor settings, add CodexA as an MCP server:

```json
{
  "mcp": {
    "servers": {
      "codex": {
        "command": "codex",
        "args": ["mcp", "--path", "/your/project"]
      }
    }
  }
}
```

## Exposed Tools

| Tool | Arguments | Description |
|------|-----------|-------------|
| `semantic_search` | `query`, `top_k` | Natural language code search |
| `explain_symbol` | `symbol_name`, `file_path` | Structural symbol explanation |
| `explain_file` | `file_path` | All symbols in a file |
| `summarize_repo` | *(none)* | Repository overview |
| `find_references` | `symbol_name` | Cross-reference lookup |
| `get_dependencies` | `file_path` | File dependency map |
| `get_call_graph` | `symbol_name` | Call graph traversal |
| `get_context` | `symbol_name`, `file_path` | Rich AI context window |

## Protocol Details

The MCP server implements the official MCP SDK protocol:

- **Transport**: stdio (stdin/stdout)
- **Format**: JSON-RPC 2.0
- **Tool schemas**: Auto-generated from CodexA's tool definitions
- **Error handling**: Typed errors with machine-readable codes

## Requirements

The MCP SDK (`mcp`) is an optional dependency. If not installed, `codex mcp`
raises a helpful error:

```bash
pip install mcp
# or install CodexA with MCP support
```

::: tip
The MCP import is optional — CodexA works fine without it. Only the `codex mcp`
command requires the MCP SDK.
:::

## Architecture

```
Claude/Cursor  ←→  stdio  ←→  MCP Server  ←→  ToolExecutor  ←→  CodexA Core
```

The MCP server is a thin adapter that:

1. Receives JSON-RPC tool invocation requests
2. Routes them to the same `ToolExecutor` used by CLI and bridge
3. Returns structured results via JSON-RPC responses

This means all MCP tools behave identically to their CLI and bridge counterparts.
