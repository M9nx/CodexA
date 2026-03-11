# Roadmap

CodexA development roadmap. All phases through v0.5.0 are complete.

## v0.5.0 — All Phases Complete

CodexA v0.5.0 ships with all planned features implemented across 42 development phases.

### Phases 33–37 — Search Dominance

- **Phase 33**: JSONL streaming, scored output, snippet control, exclude/no-ignore flags
- **Phase 34**: Incremental indexing (`--add`, `--inspect`), model-consistency guard, Ctrl+C safety
- **Phase 35**: Tantivy full-text engine (Rust-native, cfg-gated)
- **Phase 36**: MCP Server v2 with cursor-based pagination, `--serve` shorthand, Claude Desktop auto-config
- **Phase 37**: `--hybrid`/`--sem` shorthands, `.codexaignore` auto-creation, PyInstaller single-binary

### Phase 32 — Rust Search Engine Core

- Native `codexa-core` Rust crate via PyO3 — HNSW, BM25, tree-sitter chunker (10 languages), parallel scanner, optional ONNX and Tantivy

### Phase 31 — RAG Pipeline

- 4-stage Retrieve → Deduplicate → Re-rank → Assemble pipeline
- Configurable strategies, cross-encoder re-ranking, token-aware budgets, source citations

### Phases 38–42 — Platform Expansion

- **Phase 38**: Incremental Embedding Models & Model Hub — `--switch-model`, model verification, multi-model index, benchmark memory metrics
- **Phase 39**: Pre-built Wheels & Platform Distribution — manylinux/macOS/Windows wheels, Scoop, Chocolatey, PyInstaller binaries
- **Phase 40**: Code Editor Compatibility — Zed, JetBrains, Neovim, Vim, Sublime Text, Emacs, Helix, Eclipse, Cursor/Windsurf
- **Phase 41**: Multi-Agent Orchestration — SessionManager, shared discovery, semantic diff, RAG code generation, bridge session endpoints
- **Phase 42**: Cross-Language Intelligence — FFI pattern detection, polyglot dependency graphs, language-aware search boosting, universal call graph

### Earlier Phases (1–30)

- CLI framework, repository indexing, semantic search, code parsing, context engine, AI features
- Platform evolution, AI coding assistant platform, external AI cooperation
- Multi-repo workspaces, multi-language parsing, platform enhancements
- Open source readiness, web interface, CI/CD pipeline, advanced AI workflows
- VS Code extension, priority features, power features, UI/UX polish
- Model profiles, persistent index, LLM caching, mypy strict, deep coverage
- AI agent tooling protocol, developer workflow intelligence, code quality metrics
- Self-improving development loop, competitive feature parity & distribution

---

## What's Next?

All planned phases are complete. CodexA is now in **community-driven development** mode.

If you have ideas for improvements, new features, or integrations, please [open an issue](https://github.com/M9nx/CodexA/issues) on GitHub and tell us what you'd like to see.
