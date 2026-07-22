# Roadmap

> Roadmap items describe current engineering direction, not guaranteed dates.
> Scope may change based on validation results, security findings, compatibility
> requirements, and measured performance data.

## Current stable release

::: info Current stable release
CodexA v0.5.0 remains the current stable release.
:::

## Completed Through v0.5.0

CodexA completed its initial feature-development phases through v0.5.0.
These phases established indexing, semantic and hybrid search, AI-agent
interfaces, the optional Rust backend, quality tooling, plugins, MCP support,
and the VS Code extension.

### Phases 33–37 — Search Dominance (Completed)
- JSONL streaming, scored output, snippet control, exclude/no-ignore flags
- Incremental indexing (`--add`, `--inspect`), model-consistency guard, Ctrl+C safety
- Tantivy full-text engine (Rust-native, cfg-gated, *Experimental*)
- MCP Server v2 with cursor-based pagination, `--serve` shorthand, Claude Desktop auto-config
- `--hybrid`/`--sem` shorthands, `.codexaignore` auto-creation, PyInstaller single-binary

### Phase 32 — Rust Search Engine Core (Completed)
- Native `codexa-core` Rust crate via PyO3 — HNSW, BM25, tree-sitter chunker (10 languages), parallel scanner, optional ONNX and Tantivy (*Environment-dependent*)

### Phase 31 — RAG Pipeline (Completed)
- 4-stage Retrieve → Deduplicate → Re-rank → Assemble pipeline
- Configurable strategies, cross-encoder re-ranking, token-aware budgets, source citations

### Phases 38–42 — Platform Expansion (Source Available / Planned)
- **Incremental Embedding Models & Model Hub**: `--switch-model`, model verification, multi-model index, benchmark memory metrics
- **Pre-built Wheels & Platform Distribution**: manylinux/macOS/Windows wheels, Scoop, Chocolatey, PyInstaller binaries
- **Code Editor Compatibility**: VS Code (Available). Zed, JetBrains, Neovim, Vim, Sublime Text, Emacs, Helix, Eclipse, Cursor/Windsurf (Planned)
- **Multi-Agent Orchestration**: SessionManager, shared discovery, semantic diff, RAG code generation, bridge session endpoints (Source Available)
- **Cross-Language Intelligence**: FFI pattern detection, polyglot dependency graphs, language-aware search boosting, universal call graph (Planned)

---

## Planned Releases

### v0.5.1 — Stabilization and Trustworthy Gates
- VS Code Workspace Trust protection
- Webview Content Security Policy
- Functional lint, format, security, and coverage gates
- Rust CI validation on supported toolchains
- Improved audit evidence and documentation accuracy
- Tests for critical configuration-writing paths
- No new product features

### v0.6.0 — Critical Reliability and Contracts
- Higher coverage for HTTP, MCP, grep, streaming, and backend-selection paths
- Versioned JSON output contract
- Versioned index/storage schema
- Reproducible dependency resolution
- Better error handling
- Backend visibility in CLI and VS Code
- Safer optional-build dependencies
- Coordinated TypeScript/ESLint upgrade
- Critical-package mypy enforcement

### v0.7.0 — Performance and Native Integration
- Reproducible performance baseline
- Cold and incremental indexing benchmarks
- Search latency and memory measurements
- Python/Rust behavior-parity tests
- Non-blocking indexing in VS Code
- VS Code integration test suite
- Rust-native qualification on supported platforms
- Performance changes only when justified by benchmark evidence

### v0.8.0 — Release Maturity
- Public compatibility and deprecation policy
- Shared component version source
- Automated release pipeline
- Reproducible build artifacts
- Artifact signatures or verifiable provenance
- Migration documentation
- Supported-platform matrix
- Stable versus Experimental feature labels
- Plugin API stability policy

> Telemetry is not committed to this roadmap. It requires a separate product and privacy decision.
