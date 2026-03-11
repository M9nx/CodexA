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

## Completed Phases (38–42)

### Phase 38 — Incremental Embedding Models & Model Hub ✅

| Feature | Status |
|---------|--------|
| `--switch-model` | ✅ Auto-force re-index on model switch |
| Model download with verify | ✅ Integrity checking via `--verify` |
| Multi-model index | ✅ Per-model vector subdirectories |
| Model benchmarking | ✅ Memory metrics in benchmark output |

### Phase 39 — Pre-built Wheels & Platform Distribution ✅

| Feature | Status |
|---------|--------|
| manylinux / macOS / Windows wheels | ✅ CI via maturin-action |
| Scoop / Chocolatey | ✅ Package manifests shipped |
| GitHub Releases | ✅ Standalone PyInstaller binaries |
| Docker image | ✅ Updated v0.5.0 with Rust extensions |

### Phase 40 — Code Editor Compatibility ✅

| Feature | Status |
|---------|--------|
| Zed extension | ✅ |
| JetBrains plugin | ✅ |
| Neovim integration | ✅ |
| Vim plugin | ✅ |
| Sublime Text package | ✅ |
| Emacs package | ✅ |
| Helix integration | ✅ |
| Cursor / Windsurf | ✅ |
| Eclipse plugin | ✅ |

### Phase 41 — Multi-Agent Orchestration & IDE v2 ✅

| Feature | Status |
|---------|--------|
| Concurrent sessions | ✅ Thread-safe SessionManager with TTL |
| Coordinated context | ✅ Shared discovery pool |
| Semantic Diff | ✅ AST-level rename/move/signature/body/cosmetic detection |
| Code Generation | ✅ RAG-grounded code generator |
| Bridge session endpoints | ✅ HTTP routes for session management |

### Phase 42 — Cross-Language Intelligence ✅

| Feature | Status |
|---------|--------|
| Cross-language symbol resolution | ✅ FFI pattern detection |
| Polyglot dependency graphs | ✅ Multi-language import tracking |
| Language-aware search boosting | ✅ Configurable boost factor |
| Universal call graph | ✅ Multi-language workspace-wide graph |

## Contributing

Interested in working on any of these? Check the [GitHub issues](https://github.com/M9nx/CodexA/issues) for related discussions.
