# 01 — Environment Baseline (Corrected v2)

**Audit Date:** 2026-07-22  
**Auditor:** Senior Software Architect / Code Quality Auditor

---

## Git State

| Check | Result |
|-------|--------|
| Branch | `main` |
| Commit | `555506632fa76662318dacfa07d6f6c068393758` |
| Working-tree status | **Dirty** — configuration modified and reports added. No application source files modified. |

### Exact Changed Repository Files

```text
 M pyproject.toml
 M vscode-extension/package-lock.json
```

Additionally, untracked files (`??`) exist, primarily consisting of:
- `uv.lock` exists locally but is untracked and not committed or enforced by CI.
- `docs/audit/` and `docs/audit/evidence/` (generated reports and documentation)
- Various build artifacts and log files (`mypy_report.txt`, `pytest_report.txt`, `radon_report.txt`, `codexa-core/target/`)

**Nature of changes:**
- `pyproject.toml`: Configuration change (added `mypy` to dev dependencies).
- `vscode-extension/package-lock.json`: Configuration/lockfile change (from running `npm audit fix`).
- `uv.lock`: Generated lockfile.
- All other additions: Generated output or reports.
- **Application code:** Untouched.

---

## Environment Validation Table

| Check | Result | Evidence | Impact |
|-------|--------|----------|--------|
| Python version | Python 3.13.9 (via `py`) | `py --version` | Supported (≥3.11 required) |
| `python` alias | **Not found** on PATH | `python --version` fails | Forces use of `py`; CI uses `python -m pip` which may fail |
| `python3` alias | **Not found** on PATH | `python3 --version` fails | Same impact as above |
| uv package manager | uv 0.10.9 | `uv --version` | Available as Python install fallback |
| Rust / Cargo | 1.94.0 (stable) | `cargo --version` | Supported |
| rustup | 1.28.2 | `rustup --version` | Present |
| rustc | 1.94.0 (4a4ef493e) | Via rustup | Supported |
| Node.js | v24.5.0 | `node.exe --version` | Supported |
| npm | 11.10.0 | `npm.cmd --version` | Supported |
| PowerShell execution policy | Restricted for `.ps1` scripts | `npm.ps1 cannot be loaded` | **Blocks** `npm` shorthand; must use `npm.cmd` |
| `mypy` | **Installed** | `uv run mypy` runs | Type checking baseline successfully captured |
| mingw gcc linker | Present but `lpython313` not found | `cargo test` link error | **Blocks** native Rust tests on Windows |
| `codexa_core` Rust wheel | Not built/installed | `use_rust()` returns False | Extension runs Python-only fallback; Rust path not tested |
| VS Code extension compiled | `tsc -p ./` succeeds | `npm run compile` exit 0 | Extension can be built |
| ESLint config | **Missing** `.eslintrc*` | `eslint` "couldn't find config" | Linting non-functional |
| `cargo audit` | Not run (cargo-audit not installed) | — | Supply-chain check skipped |
| `pip-audit` | **Run** on requirements.txt | Exit 0 | **0 known vulnerabilities** in core production deps |

---

## Repository Structure

```
CodexA/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               # Python tests only; no mypy, no coverage gate
│   │   ├── build-wheels.yml     # Rust wheel builds + PyPI publish on tag
│   │   └── deploy-docs.yml      # VitePress docs deploy
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── copilot-instructions.md
├── codexa-core/                 # Rust native extension (PyO3)
│   ├── Cargo.toml               # version 0.1.0 (diverged from Python 0.5.0)
│   ├── src/
│   │   ├── lib.rs               # PyO3 module registration
│   │   ├── ann.rs               # Flat vector store (replaces FAISS)
│   │   ├── hnsw.rs              # HNSW ANN search
│   │   ├── bm25.rs              # BM25 keyword index
│   │   ├── chunk.rs             # Line-boundary code chunker
│   │   ├── ast_chunk.rs         # Tree-sitter AST-aware chunker
│   │   ├── scan.rs              # File scanner (blake3, parallel)
│   │   ├── hybrid.rs            # Reciprocal Rank Fusion
│   │   ├── embed.rs             # ONNX embedder (optional feature)
│   │   └── tantivy_search.rs    # Tantivy full-text (optional feature)
├── semantic_code_intelligence/  # Python core (23,104 LoC production)
│   ├── cli/                     # 40 command files + main.py + router.py
│   ├── analysis/                # Code quality, metrics, impact
│   ├── bridge/                  # HTTP bridge server
│   ├── config/                  # Settings, AppConfig
│   ├── context/                 # AI context windows, memory
│   ├── daemon/                  # File watcher
│   ├── docs/                    # Doc generation
│   ├── embeddings/              # Model registry, enhanced embeddings
│   ├── evolution/               # Self-improving dev loop
│   ├── indexing/                # Parallel indexer, scanner, semantic chunker
│   ├── llm/                     # LLM providers, RAG, reasoning, streaming
│   ├── lsp/                     # LSP server stub
│   ├── mcp/                     # MCP server (13 tools), Claude config
│   ├── parsing/                 # tree-sitter parser
│   ├── plugins/                 # Plugin system (22 hooks)
│   ├── scalability/             # Multi-repo, chunking strategies
│   ├── search/                  # grep, hybrid, keyword, semantic
│   ├── services/                # IndexingService, SearchService
│   ├── sessions/                # Multi-agent session management
│   ├── storage/                 # VectorStore, HashStore, SymbolRegistry
│   ├── tools/                   # AI agent tool protocol (13 tools)
│   ├── tui/                     # Textual TUI / fallback REPL
│   ├── utils/                   # Logging, helpers
│   ├── web/                     # Web UI + REST API
│   ├── workspace/               # Multi-repo workspace
│   ├── rust_backend.py          # Rust integration bridge
│   └── tests/                   # 46 test files
├── vscode-extension/
│   ├── src/extension.ts         # Single 1,121-line TypeScript file
│   ├── package.json             # v0.2.0 — ESLint 8 devDep, no eslintrc
│   └── tsconfig.json
├── docs/                        # VitePress documentation
├── pyproject.toml               # v0.5.0 — authoritative Python package config
├── requirements.txt             # Duplicate of pyproject.toml deps (not pinned)
├── Dockerfile
├── codexa.spec                  # PyInstaller spec
└── package.json                 # Root: VitePress docs only
```

---

## Build Systems

| Component | Build System | Command |
|-----------|-------------|---------|
| Python package | setuptools + pyproject.toml | `uv pip install -e .` |
| Rust extension | maturin (wheel only) / cargo (dev) | `maturin develop` or `cargo build` |
| VS Code extension | tsc (TypeScript) | `npm run compile` |
| Documentation | VitePress (Node.js) | `npm run docs:dev` |
| Standalone binary | PyInstaller | `pyinstaller codexa.spec` |

---

## Environmental Limitations Affecting Audit

1. **Rust extension cannot link on Windows MinGW**: `cargo test` and `cargo build` (debug) fail because MinGW-GCC cannot locate `lpython313`. This is a **Windows-specific build environment defect**, not a code defect.
2. **`cargo-audit` not installed**: Supply-chain audit of Rust crates was performed via `Cargo.lock` inspection only.
