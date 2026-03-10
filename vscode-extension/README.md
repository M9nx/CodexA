# CodexA VS Code Extension

Multi-panel developer intelligence sidebar — semantic search, symbol
exploration, code quality analysis, AI agent tooling, and more — powered
by the `codexa` CLI.

## Features

### Sidebar Panels

| Panel | What it does |
|-------|-------------|
| **Search** | Multi-mode search (semantic / keyword / hybrid / regex) with top-K selector, click-to-open results |
| **Symbols & Graphs** | Explain any symbol, view call graphs, file dependency maps — all inline |
| **Quality** | One-click quality analysis, code metrics dashboard (LOC, complexity, maintainability), risk hotspots |
| **Tools** | Doctor health check, re-index, list models, list tools, run any of the 8 agent tools with custom args |

### Commands

| Command | Keybinding | Description |
|---------|------------|-------------|
| **CodexA: Search Codebase** | `Ctrl+Shift+F5` | Semantic search via input box |
| **CodexA: Ask a Question** | — | Natural-language Q&A about the codebase |
| **CodexA: Show Call Graph** | — | Call graph of symbol at cursor |
| **CodexA: List Models** | — | Quick-pick list of embedding models |
| **CodexA: Code Quality Analysis** | `Ctrl+Shift+Q` | Full quality report |
| **CodexA: Explain Symbol at Cursor** | `Ctrl+Shift+E` | Structural explanation of symbol under cursor |
| **CodexA: Doctor (Health Check)** | — | Run `codexa doctor` and show results |
| **CodexA: Re-Index Codebase** | — | Trigger a full re-index |

### Editor Integration

- **Context menu**: Right-click → *Explain Symbol* / *Show Call Graph*
- **CodeLens**: Python `def`/`class` definitions show an inline *Explain* link
- **Status bar**: Clickable CodexA icon with live operation status

## Prerequisites

* The `codexa` CLI must be installed and available on `PATH`,
  or configure `codexa.binaryPath` in VS Code settings.
* If working inside the CodexA repo itself, the extension auto-detects
  `.venv/Scripts/codexa.exe` (Windows) or `.venv/bin/codexa` (Unix).

## Development

```bash
cd vscode-extension
npm install
npm run compile   # or npm run watch
```

Press **F5** in VS Code to open a new Extension Development Host.
