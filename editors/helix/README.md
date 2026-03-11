# Helix Editor — CodexA Integration Guide

Helix supports LSP and can be configured to use CodexA's MCP bridge.

## Setup

### 1. Start the CodexA server

```bash
codexa serve
```

### 2. Configure Helix languages.toml

Add to `~/.config/helix/languages.toml`:

```toml
# CodexA MCP integration for all languages
[[language]]
name = "python"
language-servers = ["pylsp", "codexa"]

[[language]]
name = "javascript"
language-servers = ["typescript-language-server", "codexa"]

[[language]]
name = "typescript"
language-servers = ["typescript-language-server", "codexa"]

[[language]]
name = "rust"
language-servers = ["rust-analyzer", "codexa"]

[[language]]
name = "go"
language-servers = ["gopls", "codexa"]

[language-server.codexa]
command = "codexa"
args = ["mcp"]
```

### 3. Verify

Open a project in Helix and verify the language server connects:

```
:lsp-workspace-command
```

## MCP Tools Available

All 13 CodexA MCP tools are available:
- `semantic_search` — Natural language code search
- `keyword_search` — BM25 keyword search
- `hybrid_search` — Fused semantic + keyword
- `regex_search` — Grep-compatible regex
- `explain_symbol` — Symbol details
- `index_status` — Index health
- `reindex` — Trigger re-index
- `health_check` — Server health
- `get_quality_score` — Code quality analysis
- `find_duplicates` — Duplicate detection
- `grep_files` — Raw file grep
- `get_file_context` — File context retrieval
- `list_languages` — Supported languages
