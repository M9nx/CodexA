# Roadmap

Planned improvements for CodexA, organized by priority.

## Recently Completed (v0.5.0)

### Search Dominance — Phases 33-37

> After competitive analysis against [ck](https://github.com/BeaconBay/ck)
> (Rust-based semantic search, v0.7.4), we redesigned the roadmap around a
> **Search Dominance** strategy — matching ck's grep UX while keeping CodexA's
> unique intelligence features.

- **Phase 33 — JSONL Streaming & Output Parity**: `--jsonl`, `--scores`, `--snippet-length`, `--no-snippet`, `--exclude`, `--no-ignore` on search and grep commands
- **Phase 34 — Chunk-Level Incremental Indexing**: `--add <file>`, `--inspect <file>`, model-consistency guard, Ctrl+C partial-save safety
- **Phase 35 — Tantivy Full-Text Engine**: `TantivyIndex` PyO3 class in Rust, cfg-gated `tantivy-backend` feature, Python bridge with feature detection
- **Phase 36 — MCP Server v2**: Cursor-based pagination on semantic/keyword/hybrid search, `codexa --serve` shorthand, `--claude-config` auto-configuration
- **Phase 37 — grep Parity & Distribution**: `--hybrid`/`--sem` shorthands, `.codexaignore` auto-creation, PyInstaller single-binary spec

### Rust Search Engine Core — Phase 32

- Native `codexa-core` Rust crate via PyO3 — HNSW, BM25, tree-sitter chunker (10 languages), parallel scanner, optional ONNX and Tantivy

### RAG Pipeline — Phase 31

- 4-stage Retrieve → Deduplicate → Re-rank → Assemble pipeline
- Configurable strategies, cross-encoder re-ranking, token-aware budgets, source citations

### Previous (v0.4.x)

- Model Profiles (fast/balanced/precise), auto-detection from RAM
- Bundled tree-sitter grammars, exclude_files config
- ML extras split: `pip install codexa` (lightweight) vs `pip install "codexa[ml]"`
- 39 CLI commands, 13 AI agent tools, 22 plugin hooks
- Docker image, Homebrew formula, VS Code extension

---

## Upcoming Phases

### Phase 38 — Incremental Embedding Models & Model Hub

| Feature | Description |
|---------|-------------|
| Lazy re-embedding | Store raw chunks; re-embed only on query if model changed |
| `--switch-model` | Smart model switching with cache invalidation |
| HuggingFace tokenizers | Rust `tokenizers` crate for exact token counting |
| Multi-model index | Separate vector indices per model, switch at query time |
| Model benchmarking | Compare models on your actual codebase |

### Phase 39 — Pre-built Wheels & Platform Distribution

| Feature | Description |
|---------|-------------|
| manylinux / macOS / Windows wheels | Pre-compiled Rust extensions, no build tools needed |
| Scoop / Chocolatey | Windows package manager support |
| GitHub Releases | Standalone binaries for every platform |
| Docker image | Production multi-stage image with pre-loaded models |

### Phase 40 — Code Editor Compatibility

| Feature | Description |
|---------|-------------|
| Zed extension | Native Zed MCP client integration |
| JetBrains plugin | IntelliJ, PyCharm, PhpStorm, WebStorm, GoLand, Rider |
| Neovim integration | telescope.nvim picker + LSP |
| Vim plugin | Vimscript/Lua with quickfix integration |
| Sublime Text package | Command palette, goto-symbol, inline annotations |
| Emacs package | helm/ivy completion, org-mode, flycheck |
| Helix integration | LSP + MCP config guide |
| Cursor / Windsurf | Verified MCP setup guides |
| Eclipse plugin | Java/PHP developer support |

### Phase 41 — Multi-Agent Orchestration & IDE v2

| Feature | Description |
|---------|-------------|
| Concurrent sessions | Isolated agent sessions |
| JetBrains plugin | IntelliJ/PyCharm integration |
| Neovim integration | telescope.nvim plugin |
| Semantic Diff | AST-level diff detection |
| Code Generation | RAG-grounded scaffolds, tests, docs |

### Phase 42 — Cross-Language Intelligence

| Feature | Description |
|---------|-------------|
| Cross-language symbol resolution | FFI, WASM, interop boundaries |
| Polyglot dependency graphs | Imports across language boundaries |
| Universal call graph | Multi-language workspace-wide call graph |

## Contributing

Interested in working on any of these? Check the [GitHub issues](https://github.com/M9nx/CodexA/issues) for related discussions.
