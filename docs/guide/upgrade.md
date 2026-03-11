# Upgrade Guide

## Upgrading to v0.5.0

v0.5.0 is a major release spanning **12 phases** (31-42) that brings a native Rust search engine, RAG pipeline, advanced search features, multi-editor support, cross-language intelligence, and multi-agent orchestration.

### Install

```bash
pip install --upgrade codexa

# Or with ML extras
pip install --upgrade "codexa[ml]"
```

### What's New

#### Rust Search Engine Core (Phase 32)

- Native `codexa-core` Rust crate via PyO3 for transparent acceleration
- HNSW approximate nearest-neighbour search with memory-mapped persistence
- AST-aware chunker splitting code at function/class boundaries (10 languages)
- BM25 keyword index, parallel file scanner, optional ONNX embedding inference
- Graceful fallback: all Rust components are optional

#### RAG Pipeline (Phase 31)

- 4-stage Retrieval-Augmented Generation: Retrieve, Deduplicate, Re-rank, Assemble
- Cross-encoder re-ranking, token-aware budgets, source citations
- Configurable strategies: `semantic`, `keyword`, `hybrid`, `multi`

#### Search & Grep Output (Phase 33)

New flags on `codexa search` and `codexa grep`:

```bash
# JSONL streaming (ideal for AI agents and pipelines)
codexa search "auth flow" --jsonl
codexa grep "TODO" --jsonl

# Show relevance scores
codexa search "error handling" --scores

# Control snippet length or omit snippets entirely
codexa search "database" --snippet-length 100
codexa search "database" --no-snippet

# Exclude files by glob, include gitignored files
codexa search "config" --exclude "*.test.*" --no-ignore
codexa grep "FIXME" --exclude "vendor/*" -L
```

#### Incremental Indexing (Phase 34)

```bash
# Index a single file without full scan
codexa index --add src/new_module.py

# Inspect a file's index metadata (content hash, chunks, vectors)
codexa index --inspect src/auth.py
```

- **Model-consistency guard**: Detects if the embedding model changed since last index and warns before corrupting vectors
- **Ctrl+C safety**: Partial index is saved on interrupt; next run resumes

#### Tantivy Full-Text Engine (Phase 35)

Optional Rust-native [Tantivy](https://github.com/quickwit-oss/tantivy) full-text search engine. Requires building `codexa-core` with the `tantivy-backend` feature:

```bash
cd codexa-core
maturin develop --release --features tantivy-backend
```

Check availability:

```python
from semantic_code_intelligence.rust_backend import use_tantivy
print(use_tantivy())  # True if compiled with tantivy-backend
```

#### MCP Server v2 (Phase 36)

- **Cursor-based pagination** on `semantic_search`, `keyword_search`, `hybrid_search` MCP tools
- **`codexa --serve`** shorthand to start the MCP server in one flag
- **Claude Desktop auto-config**:

```bash
codexa mcp --claude-config
```

#### Search Shorthands & Distribution (Phase 37)

```bash
# Mode shorthands
codexa search "query" --hybrid    # equivalent to --mode hybrid
codexa search "query" --sem       # equivalent to --mode semantic

# .codexaignore is auto-created on first index with sensible defaults
```

PyInstaller spec included at `codexa.spec` for single-binary distribution.

#### Model Hub & Hot-Swap (Phase 38)

```bash
# Switch embedding model with automatic re-index
codexa index --switch-model jina-code

# Download with integrity verification
codexa models download bge-small --verify

# Benchmark models with memory metrics
codexa models benchmark
```

- Per-model vector subdirectories for multi-model index support

#### Pre-built Wheels & Distribution (Phase 39)

- CI-built wheels for Linux (x86_64, aarch64), macOS (universal2), Windows (x64)
- Scoop and Chocolatey package manifests
- Standalone PyInstaller binaries via GitHub Releases
- Updated Docker image with Rust extensions

#### Code Editor Plugins (Phase 40)

First-class integration for 9 editors, all sharing the same MCP/bridge protocol:

- **Zed** -- extension with context servers and language servers
- **JetBrains** -- IntelliJ/PyCharm/WebStorm plugin with bridge HTTP client
- **Neovim** -- Lua plugin with telescope.nvim picker and floating preview
- **Vim** -- Vimscript plugin with quickfix integration
- **Sublime Text** -- command palette, quick panel, output panel
- **Emacs** -- helm/ivy completion, grep-mode results
- **Helix** -- languages.toml configuration guide
- **Eclipse** -- plugin descriptor and setup guide
- **Cursor/Windsurf** -- documented MCP setup configs

#### Multi-Agent Orchestration (Phase 41)

- Thread-safe `SessionManager` for concurrent AI agent sessions with TTL cleanup
- Shared discovery pool for coordinated context across agents
- Semantic diff: AST-level rename, move, signature, body, and cosmetic change detection
- RAG-grounded code generator
- Bridge session endpoints: `/sessions`, `/sessions/create`, `/sessions/close`

#### Cross-Language Intelligence (Phase 42)

- FFI pattern detection (Python-Rust, Python-C, JS-WASM, Java-JNI)
- Polyglot dependency graphs across language boundaries
- Language-aware search boosting with configurable boost factor
- Universal multi-language call graph

### Breaking Changes

None. All new flags and features are additive. Existing CLI invocations work unchanged.

### Migration Checklist

1. `pip install --upgrade codexa`
2. Re-index to pick up the latest features: `codexa index --force`
3. (Optional) Build with Tantivy: `maturin develop --release --features tantivy-backend`
4. (Optional) Set up Claude Desktop: `codexa mcp --claude-config`
5. (Optional) Try model switching: `codexa index --switch-model jina-code`

---

## Previous Versions

### v0.4.5

- RAG Pipeline (Phase 31): 4-stage Retrieve, Deduplicate, Re-rank, Assemble
- Cross-encoder re-ranking, token-aware budgets, source citations

### v0.4.4

- Model Profiles: `fast`, `balanced`, `precise` with auto-detection
- `codexa init --profile`, `codexa models profiles`, `codexa models benchmark`

### v0.4.3

- Bundled tree-sitter grammars, `exclude_files` config
- Install tiers: `pip install codexa` (lightweight) vs `pip install "codexa[ml]"`

### v0.4.0

- First stable public release
- 39 CLI commands, 13 AI agent tools, 22 plugin hooks
