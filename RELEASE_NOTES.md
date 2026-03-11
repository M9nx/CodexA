# CodexA v0.5.0 — Release Notes

> **Released:** March 2026 · **License:** MIT · **Docs:** [codex-a.dev](https://codex-a.dev)

**CodexA** is a developer intelligence engine for semantic code search, AI-assisted code understanding, and agent tooling.

---

## What's New in v0.5.0

The biggest release yet -- 12 phases of development in a single version. CodexA now ships with a Rust-powered search engine, a full RAG pipeline, editor plugins for 9 editors, multi-agent orchestration, and cross-language intelligence.

### Rust Search Engine Core
- `codexa-core` crate compiled via PyO3/maturin
- HNSW vector index with `instant-distance` for O(log n) nearest-neighbour search
- Memory-mapped persistence for near-instant startup
- AST-aware chunker splitting code at function/class/method boundaries (10 languages)
- Rust BM25 index, parallel scanner with blake3 hashing, RRF fusion
- ONNX embedder for ONNX Runtime inference
- All Rust components optional -- Python fallback when crate is not installed

### RAG Pipeline
- 4-stage retrieval: Retrieve, Deduplicate, Re-rank, Assemble with token budget
- Configurable strategies: `semantic`, `keyword`, `hybrid`, `multi`
- Cross-encoder re-ranking with `ms-marco-MiniLM-L-6-v2`
- Source citations with numbered `[N]` markers in LLM responses

### Search Dominance
- JSONL streaming, scored output, snippet control
- Incremental indexing with Ctrl+C partial-save safety
- Tantivy full-text engine via PyO3
- MCP Server v2 with cursor-based pagination
- `.codexaignore` auto-create on first index

### Model Hub and Distribution
- `--switch-model` for hot-swapping embedding models
- Model verification with `codexa models download --verify`
- Pre-built wheels for Linux (x86_64, aarch64), macOS (universal2), Windows (x64)
- Scoop and Chocolatey manifests, standalone PyInstaller binaries, Docker image

### Editor Plugins
First-class support for 9 editors:
VS Code, Zed, JetBrains (IntelliJ/PyCharm/WebStorm), Neovim, Vim, Sublime Text, Emacs, Helix, Eclipse. MCP configs for Cursor and Windsurf.

### Multi-Agent Orchestration
- Thread-safe concurrent agent sessions with TTL cleanup
- Shared discovery pool across multiple AI agents
- Semantic diff: AST-level detection of renames, moves, signature changes
- RAG-grounded code generation
- Bridge session endpoints: `/sessions`, `/sessions/create`, `/sessions/close`

### Cross-Language Intelligence
- FFI pattern detection: Python-Rust, Python-C, JS-WASM, Java-JNI
- Polyglot dependency graphs for multi-language import tracking
- Language-aware search boosting with configurable boost factor
- Universal call graph across languages

### Install
```bash
pip install codexa==0.5.0
```

### Stats
- 2657 tests passing
- 42 CLI commands
- 13 built-in AI agent tools
- 12 language parsers
- 9 editor plugins

---

## Previous Releases

### v0.4.4 — Model Flexibility & Smart Defaults
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
