# CodexA v0.4.4 — Release Notes

> **Released:** 2025 · **License:** MIT · **Docs:** [codex-a.dev](https://codex-a.dev)

**CodexA** is a developer intelligence engine for semantic code search, AI-assisted code understanding, and agent tooling.

---

## What's New in v0.4.4

This release introduces **model flexibility** — choose the right embedding model for your hardware, benchmark models against your codebase, and let CodexA auto-detect the best configuration.

### Model Profiles
- **Three profiles**: `fast` (mxbai-embed-xsmall, <1 GB RAM), `balanced` (MiniLM, ~2 GB), `precise` (jina-embeddings-v2-base-code, ~4 GB)
- **`codexa init --profile fast|balanced|precise`** — pick your tier at init time
- **Auto-detect**: when no profile is specified, CodexA detects available RAM and recommends the best model

### New Commands
- **`codexa models profiles`** — view available model profiles with RAM requirements and a ⭐ recommendation
- **`codexa models benchmark`** — benchmark all built-in models against your actual codebase. Reports load time, encode time, and chunks/second

### UX Improvements
- **Download progress**: friendly banner with model name and size shown when downloading a model for the first time
- **RAM-aware defaults**: `recommend_profile_for_ram()` picks the best model for your machine automatically

---

## Previous Releases

### v0.4.3 — Packaging & Indexing UX Fixes
- Tree-sitter grammar packages bundled in core dependencies
- `index.exclude_files` config, `.codexaignore` support
- MemoryError handling for low-RAM machines
- Reduced HuggingFace noise, improved CLI guidance
- Community fixes ([#2](https://github.com/M9nx/CodexA/issues/2))

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
# codexa, version 0.4.4
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
| **Version** | 0.4.4 |
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
