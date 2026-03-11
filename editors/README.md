# CodexA Editor Integrations

Native plugins and configuration files for every major code editor,
all sharing the same MCP server / HTTP bridge protocol.

## Supported Editors

| Editor | Type | Directory |
|--------|------|-----------|
| **VS Code** | Extension (TypeScript) | `../vscode-extension/` |
| **Zed** | Extension manifest | `zed/` |
| **JetBrains** | Plugin (Kotlin) | `jetbrains/` |
| **Neovim** | Lua plugin | `neovim/` |
| **Vim** | Vimscript plugin | `vim/` |
| **Sublime Text** | Python plugin | `sublime/` |
| **Emacs** | Elisp package | `emacs/` |
| **Helix** | LSP/MCP config | `helix/` |
| **Eclipse** | Plugin stub | `eclipse/` |

## Shared Architecture

All editors communicate with CodexA through the same interface:

```
┌──────────────┐          ┌───────────────┐
│ Editor Plugin│──HTTP───→│ codexa serve  │ (port 24842)
│              │          │ Bridge Server │
└──────────────┘          └───────────────┘
       or
┌──────────────┐          ┌───────────────┐
│ Editor Plugin│──stdio──→│ codexa mcp    │ (MCP protocol)
│              │          │ MCP Server    │
└──────────────┘          └───────────────┘
```

## Quick Start

1. Start the CodexA server: `codexa serve`
2. Install the plugin for your editor
3. The plugin connects to `http://localhost:24842`

For MCP-native editors (Cursor, Windsurf, Zed), use `codexa mcp` directly.

## Cursor / Windsurf Setup

Add to your MCP settings (`.cursor/mcp.json` or equivalent):

```json
{
  "mcpServers": {
    "codexa": {
      "command": "codexa",
      "args": ["mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```
