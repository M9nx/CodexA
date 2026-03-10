# CodexA v0.4.3 — Release Notes

> **Released:** 2025 · **License:** MIT · **Docs:** [codex-a.dev](https://codex-a.dev)

**CodexA** is a developer intelligence engine for semantic code search, AI-assisted code understanding, and agent tooling.

---

## What's New in v0.4.3

This release focuses on **packaging reliability**, **indexing UX**, and fixes reported by the community ([#2](https://github.com/M9nx/CodexA/issues/2)).

### Packaging & Installation
- Tree-sitter grammar packages now **bundled in core dependencies** — language parsing works out of the box after `pip install codexa`
- Two install tiers documented: `pip install codexa` (lightweight CLI) and `pip install "codexa[ml]"` (semantic indexing + vector search)
- Reduced repeated HuggingFace model cache/network checks — prefers local model files when already cached

### Indexing & Search
- New `index.exclude_files` config option — glob-based file exclusions in `.codexa/config.json`
- `.codexaignore` support documented with examples for secrets and generated files
- Reduced embedding model re-download noise with smarter cache detection

### Reliability
- Actionable `MemoryError` handling for machines with < 2 GB RAM during embedding model loading
- Improved `codexa init` and `codexa index` CLI output with hints for ML extras and RAM requirements

---

## Previous Releases

### v0.4.2 — NumPy Compatibility
- Pinned `numpy < 2` to avoid ABI breakage with FAISS on some platforms

### v0.4.1 — Lightweight Install Split
- Moved heavy ML libraries (`sentence-transformers`, `torch`, `faiss-cpu`) to `[ml]` extra
- Core `pip install codexa` installs the CLI + tree-sitter parsing without ML overhead

### v0.4.0 — First Stable Public Release
- Package renamed `codexa-ai` → `codexa`
- 39 CLI commands, 13 AI agent tools, 22 plugin hooks
- Semantic search (FAISS + sentence-transformers), multi-mode search, quality analysis
- Docker image, Homebrew formula, MCP server, VS Code extension

---

## Installation

```bash
# Lightweight CLI (parsing, grep, quality, explain)
pip install codexa

# Full ML stack (semantic search, vector indexing, embeddings)
pip install "codexa[ml]"
```

Verify:

```bash
codexa --version
# codexa, version 0.4.3
```

## Quick Start

```bash
cd /path/to/your-project
codexa init --index       # Initialize and index in one step
codexa search "auth"      # Semantic code search
codexa explain MyClass    # Structural symbol explanation
codexa quality src/       # Code quality analysis
codexa doctor             # Environment health check
```

## Stats

| Metric | Value |
|--------|-------|
| **Version** | 0.4.3 |
| **CLI Commands** | 39 |
| **AI Agent Tools** | 13 |
| **Plugin Hooks** | 22 |
| **Parsed Languages** | 11 |
| **Tests** | 2596 |
| **Python** | >= 3.11 |

## Documentation

Full documentation: [codex-a.dev](https://codex-a.dev)

## License

MIT
