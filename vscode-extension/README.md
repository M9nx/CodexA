# CodexA VS Code Extension

Sidebar semantic search, call-graph visualisation, and AI-powered Q&A
for your codebase — powered by the `codex` CLI.

## Features

| Feature              | Command palette             | Keybinding      |
| -------------------- | --------------------------- | --------------- |
| Semantic search      | **CodexA: Search Codebase** | `Ctrl+Shift+F5` |
| Ask a question       | **CodexA: Ask a Question**  | —               |
| Show call graph      | **CodexA: Show Call Graph** | —               |
| List models          | **CodexA: List Models**     | —               |
| Sidebar search panel | Activity bar → **CodexA**   | —               |

## Prerequisites

* The `codex` CLI must be installed and available on `PATH`,
  or set `codexa.binaryPath` in VS Code settings.

## Development

```bash
cd vscode-extension
npm install
npm run compile   # or npm run watch
```

Press **F5** in VS Code to open a new Extension Development Host.
