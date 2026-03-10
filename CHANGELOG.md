# Changelog

All notable changes to CodexA are documented in this file.

## [0.4.4] — Model Flexibility & Smart Defaults

### New Features
- **Model Profiles**: Three built-in profiles — `fast` (mxbai-embed-xsmall, <1 GB RAM), `balanced` (MiniLM, ~2 GB), `precise` (jina-embeddings-v2-base-code, ~4 GB)
- **`codexa init --profile`**: Choose your embedding model tier at initialization. When omitted, auto-detects available RAM and recommends the best profile
- **`codexa models profiles`**: View all available model profiles with RAM requirements and recommendations
- **`codexa models benchmark`**: Benchmark embedding models against your actual codebase — measures load time, encoding speed, and throughput
- **Download progress indicator**: Friendly banner with model size shown when downloading a new embedding model for the first time
- **RAM-aware model selection**: `recommend_profile_for_ram()` automatically picks the best model for your hardware

### Changed
- Model registry extended with `ModelProfile` dataclass, `size_mb` and `ram_required_gb` fields on `ModelInfo`
- Version bumped to 0.4.4

## [0.4.3] — Packaging and Indexing UX Fixes

### Packaging & Installation
- Added bundled tree-sitter grammar packages to the core dependency set so language parsing works after a normal install without pulling extra packages from `requirements.txt`
- Clarified install modes in the README: `pip install codexa` for lightweight commands, `pip install "codexa[ml]"` for semantic indexing and vector search

### Indexing & Search
- Added `index.exclude_files` config support for glob-based file exclusions in `.codexa/config.json`
- Continued support for `.codexaignore`, now documented with examples for secrets and generated files
- Reduced repeated HuggingFace cache/network checks by preferring local model files when already cached

### Reliability
- Added actionable low-memory failures for embedding model loading on machines with less than about 2 GB of available RAM
- Improved `codexa init` and `codexa index` guidance with ML extra and RAM hints

### Changed
- Version bumped to 0.4.3

## [0.4.0] — First Stable Public Release

### Release Highlights
CodexA v0.4.0 is the first stable public release — focused on stabilization, packaging, and usability.

### Packaging & Distribution
- **Package renamed**: `codexa-ai` → `codexa` for cleaner `pip install codexa`
- **`version.py`**: Single source of truth for version at `semantic_code_intelligence/version.py`
- **PyPI ready**: `pip install codexa` installs CLI and all dependencies
- **Docker**: Production-ready image with `docker build -t codexa .`
- **Homebrew**: `brew install --formula Formula/codexa.rb`
- **Reproducible builds**: `python -m build` generates sdist + wheel

### CLI Stability
- All **39 commands** verified with `--help`
- Consistent `--json` output across all commands
- Global error handler with graceful messages
- `codexa --version` → `codexa, version 0.4.0`

### Key Capabilities (cumulative)
- **Semantic search**: FAISS vector index + sentence-transformers (`all-MiniLM-L6-v2`)
- **Multi-mode search**: semantic, keyword (BM25), regex, hybrid (RRF), and grep
- **Tree-sitter parsing**: 11 languages (Python, JS, TS, TSX, Java, Go, Rust, C++, C#, Ruby, PHP)
- **13 AI agent tools**: via CLI, HTTP bridge, MCP server, or MCP-over-SSE
- **Quality analysis**: complexity, security (Bandit), hotspots, impact, quality gates
- **Plugin system**: 22 hooks across the full pipeline
- **39 CLI commands** with `--json`, `--pipe`, `--verbose` flags
- **2595 tests**, all passing

### Changed
- Version: 0.30.0 → 0.4.0 (semantic versioning for public release)
- Package name: `codexa-ai` → `codexa`
- Homepage: github.com/M9nx/CodexA → codex-a.dev

---

## [0.30.0] — Competitive Feature Parity & Distribution

### New Commands
- **`codexa index --watch`**: Live watch-mode indexing — performs initial index then watches for file changes and re-indexes incrementally using NativeFileWatcher + `run_incremental_indexing()`
- **`codexa languages`**: Rich table listing all 11 supported tree-sitter languages with extensions, grammar status, and `--check` flag to verify grammar loading

### Enhanced Commands
- **`codexa grep`**: Full standard grep compatibility — `-A`/`-B`/`-C` (context lines), `-w` (word match), `-v` (invert match), `-c` (count only), `--hidden` (include hidden files); context lines rendered in both ripgrep and Python backends
- **`codexa benchmark --profile`**: cProfile integration — dumps top 20 hotspots by cumulative time during full indexing for performance troubleshooting
- **`codexa serve --mcp`**: MCP-over-SSE transport — exposes all MCP tools over HTTP with Server-Sent Events for AI agent integration via Starlette/uvicorn

### MCP Server
- **13 MCP tools** (up from 11): added `get_file_context` (full-section surrounding code retrieval) and `list_languages` (tree-sitter grammar listing)
- `get_file_context` supports both line-number and symbol-name based context lookup with ±30 line window

### Packaging & Distribution
- **Dockerfile**: Production-ready image with ripgrep, git, and pre-loaded default embedding model
- **Homebrew formula**: `Formula/codexa.rb` for macOS installation via `brew install`
- **PyPI ready**: Version 0.30.0 with `python -m build` compatibility

### Changed
- CLI registers **39 commands** (up from 38)
- Version bumped to 0.30.0
- ROADMAP updated with Phase 30 and renumbered future phases

## [0.29.0] — Performance & Developer Experience Overhaul

### Performance
- **Vector removal O(1)**: Added `_file_index` (dict→set) for instant file→vector lookup instead of linear scan; batch FAISS reconstruction
- **Incremental indexing fix**: Extract vectors before removal, cache by content hash, reuse for unchanged chunks — eliminates redundant embedding computation
- **BM25 persistence**: BM25 index serialized to disk (JSON); 3-tier cache: memory→disk→build; staleness detection
- **Native file watcher**: Rust-backed `watchfiles` using OS-native APIs (inotify/FSEvents/ReadDirectoryChanges) with polling fallback

### New Commands
- **`codexa grep "<pattern>"`**: Raw filesystem search without requiring an index; ripgrep backend for speed, pure-Python fallback
- **`codexa benchmark`**: Full performance benchmarking — indexing speed, search latency (semantic/keyword/regex/hybrid with avg/p50/p99/QPS), BM25 persistence speedup, memory usage

### Enhanced Commands
- **`codexa init --index`**: Auto-build search index after initialization
- **`codexa init --vscode`**: Generate `.vscode/settings.json` with MCP server config
- Next steps guidance shown after bare `codexa init`

### New AI Tools (11 total)
- **`get_quality_score`**: Code quality analysis — complexity, dead code, duplicates, safety
- **`find_duplicates`**: Trigram Jaccard similarity-based duplicate detection
- **`grep_files`**: Raw filesystem regex search via ripgrep or Python
- All 3 tools available via both `ToolRegistry` and MCP server

### MCP Server
- **11 MCP tools** (up from 8): added `get_quality_score`, `find_duplicates`, `grep_files`

### Changed
- CLI registers **38 commands** (up from 36)
- Version bumped to 0.29.0
- `watchfiles>=1.0.0` added to dependencies

## [0.28.0] — Phase 28: UI/UX Polish Across All Interfaces

### VS Code Extension
- **SymbolsViewProvider**: Added Find References feature with HTML input fields and card-based result rendering
- **ToolsViewProvider**: Complete rewrite with dynamic parameter inputs generated from tool SCHEMAS, client-side validation, corrected `--json` flag placement, rich result rendering, 6 quick action buttons, loading spinners and animations
- **SHARED_CSS**: Enhanced shared stylesheet for consistent panel styling

### Web UI
- **3 new pages**: Tools, Quality, Ask — accessible from the navigation bar
- **4 new API endpoints**: `/api/quality`, `/api/metrics`, `/api/hotspots`, `/api/tools/run`
- Updated navigation links across all pages

### CLI
- **Global error handler** in `main.py` for graceful exception handling
- **Rich tables** in `tool_cmd.py` for tool listing and results
- **Error handling** added to `metrics_cmd`, `impact_cmd`, `hotspots_cmd`, `ask_cmd` with try/except blocks
- **`print_separator()`** and **`print_header()`** utility functions for consistent output formatting

### TUI
- **Improved Textual CSS** for better layout and styling
- **Ctrl+K / Ctrl+J** keybindings for top-k adjustment
- **Rich tables and syntax highlighting** in fallback REPL mode
- **New commands**: `/help`, `/topk`, `/explain` in the REPL

### Changed
- CLI registers **36 commands** (up from 35)
- 2595 tests, all passing

### Bugfixes (Post-Release)
- **JSON output contamination**: Fixed `explain --json`, `summary --json`, `deps --json` mixing diagnostic text into JSON output
- **Web API /api/hotspots 500**: Fixed missing arguments to `analyze_hotspots()` — now properly builds symbols, call_graph, dep_map before analysis
- **MCP server version**: Bumped from 0.26.0 to 0.28.0

## [0.27.0] — Phase 27: Power Features (P1–P6)

### Added — P1: Rich Textual TUI
- **Full Textual split-pane TUI** (`tui/__init__.py`) — split-pane layout with result list + syntax-highlighted preview, mode cycling (semantic/keyword/regex/hybrid), keyboard bindings (Ctrl+Q quit, Ctrl+M mode, Escape clear)
- **Graceful fallback REPL** when `textual` is not installed

### Added — P2: Grep Flag Parity + JSONL
- **`--context-lines / -C N`** — show N context lines before/after each match (grep-style)
- **`--files-only / -l`** — print only file paths with matches (like `grep -l`)
- **`--files-without-match / -L`** — print file paths without any matches (like `grep -L`)
- **`--line-numbers / -n`** — prefix output lines with line numbers (like `grep -n`)
- **`--jsonl`** — output one JSON object per line for piping into `jq`/`fzf`
- **`format_results_jsonl()`** in `search/formatter.py`
- **`_expand_context()`** — reads extra context lines from disk for `-C` flag

### Added — P3: VS Code Extension
- **`vscode-extension/`** scaffold with `package.json`, `tsconfig.json`, `src/extension.ts`
- 4 commands: Search Codebase, Ask a Question, Show Call Graph, List Models
- Sidebar webview search panel with real-time results
- Keybinding: `Ctrl+Shift+F5` for search

### Added — P4: Single-Binary Distribution
- **`build.py`** — PyInstaller build script for standalone `codexa` binary
- Supports `--onefile` (default) and `--onedir` modes
- `pyproject.toml` optional dependency group `[build]` with `pyinstaller>=6.0.0`

### Added — P5: Performance Hardening
- **IVF index support** in `storage/vector_store.py` — `IndexIVFFlat` approximate search for large repos (>50k vectors)
- **Auto-upgrade**: flat index transparently migrates to IVF when vector count crosses `IVF_THRESHOLD` (50,000)
- **`use_ivf=True` constructor option** for explicit IVF mode
- **Graceful fallback** to flat when too few vectors to train IVF (<100)

### Added — P6: `codexa models` CLI
- **`codexa models list [--json]`** — table or JSON of all 5 built-in embedding models
- **`codexa models info <name>`** — detailed model info panel
- **`codexa models download <name> [--backend auto|onnx|torch]`** — pre-download for offline use
- **`codexa models switch <name> [-p PATH]`** — switch active model + prompt re-index
- `pyproject.toml` optional dependency group `[tui]` with `textual>=0.40.0`

### Changed
- CLI now registers **35 commands** (up from 34)
- `search_cmd.py` extended with 5 new grep-compatible flags
- `vector_store.py` supports both flat and IVF FAISS indices

## [0.26.0] — Phase 26: Priority Feature Implementation (P1–P5)

### Added — P1: Close the Search Gap
- **BM25 keyword search** (`search/keyword_search.py`) — in-memory inverted index with configurable k1/b parameters, camelCase/underscore-aware tokenizer
- **Regex search** (`search/keyword_search.py`) — grep-compatible pattern matching with case-sensitivity control
- **Hybrid search with RRF** (`search/hybrid_search.py`) — Reciprocal Rank Fusion fuses semantic and BM25 rankings (k=60)
- **Full-section expansion** (`search/section_expander.py`) — expand search results to the enclosing function/class using the symbol registry
- **Auto-index on first search** (`services/search_service.py`) — transparent indexing when no vector store exists, controlled via `--no-auto-index`
- **4 search modes in CLI** (`cli/commands/search_cmd.py`) — `--mode semantic|keyword|regex|hybrid`, `--full-section`, `--case-sensitive` flags

### Added — P2: Close the Indexing Gap
- **Chunk-level content hashing** (`storage/chunk_hash_store.py`) — SHA-256 per chunk stored in `chunk_hashes.json`, enables skipping unchanged chunks during incremental indexing
- **Model registry** (`embeddings/model_registry.py`) — 5 curated embedding models as frozen `ModelInfo` dataclasses with dimension/description metadata
- **ONNX runtime backend** (`embeddings/generator.py`) — auto-detection of `optimum`/`onnxruntime`, falls back to PyTorch when unavailable

### Added — P3: Performance
- **Parallel indexing** (`indexing/parallel.py`) — `ThreadPoolExecutor`-based parallel file chunking and hashing with configurable worker count
- **Shared model caching** — in-process `_model_cache` dict in `generator.py` eliminates redundant model loads

### Added — P4: UX & Integration
- **Interactive TUI** (`tui/__init__.py`, `cli/commands/tui_cmd.py`) — terminal REPL with `/mode`, `/view`, `/quit` commands and mode switching
- **MCP server** (`mcp/__init__.py`, `cli/commands/mcp_cmd.py`) — JSON-RPC over stdio implementing Model Context Protocol v2024-11-05 with 8 tools
- **`.codexaignore` support** (`indexing/scanner.py`) — gitignore-style file exclusion patterns loaded from project root

### Added — P5: Widen the Lead
- **AST-based call graphs** (`context/engine.py`) — tree-sitter powered call extraction walking `call`/`call_expression`/`method_invocation`/`invocation_expression` nodes, with regex fallback for unsupported languages
- **Cross-repo search modes** (`workspace/__init__.py`) — `Workspace.search()` now supports semantic, keyword, regex, and hybrid modes across all linked repositories
- **Streaming responses** (`cli/commands/chat_cmd.py`, `cli/commands/investigate_cmd.py`, `llm/investigation.py`) — `--stream` flag for token-by-token output in chat and investigate commands

### Changed
- CLI now registers **34 commands** (up from 32)
- `search_service.py` rewritten to dispatch across 4 search backends with auto-index and full-section support
- `indexing_service.py` rewritten for chunk-level incremental indexing with content hashing
- `generator.py` rewritten for ONNX backend and model registry integration
- `CallGraph.build()` replaced regex-based implementation with AST-based tree-sitter analysis

### Tests
- **48 new tests** in `test_priority_features.py` covering all P1–P5 features
- Total test count: **2413** (up from 2365)

## [0.25.0] — Phase 25: Incremental Indexing & Quality Refactors

### Added
- **Stale vector removal** (`storage/vector_store.py`) — `VectorStore.remove_by_file()` rebuilds the FAISS index excluding entries for a given file, enabling true incremental re-indexing without stale duplicates
- **Deleted file cleanup** (`services/indexing_service.py`) — incremental indexing now detects files removed from disk and purges their vectors, symbols, and hash entries automatically
- **HF_TOKEN environment support** (`embeddings/generator.py`) — `_configure_hf_token()` checks `HF_TOKEN`, `HUGGING_FACE_HUB_TOKEN`, and `HUGGINGFACE_TOKEN` before loading models, eliminating unauthenticated-request warnings
- **Call graph regex matching** (`context/engine.py`) — `CallGraph.build()` uses word-boundary regex `\b{name}\s*[\(\.]` instead of substring matching for accurate call detection
- **Web UI Mermaid rendering** (`web/ui.py`) — visualization page now loads Mermaid JS from CDN and renders call graphs / dependency graphs as interactive SVGs
- **Web viz data format fix** (`web/server.py`, `bridge/context_provider.py`) — call graph API now returns `edges` key combining callers and callees, matching what the visualization renderer expects

### Fixed
- **23 silent exception catches** across 14 files converted to `logger.debug()` messages for better debuggability: `explain_cmd`, `quality_cmd`, `pr_summary_cmd`, `chat_cmd`, `cross_refactor_cmd`, `hotspots_cmd`, `impact_cmd`, `trace_cmd`, `hooks.py`, `investigation.py`, `cross_refactor.py`, `metrics.py`, `docs/__init__`, `streaming.py`
- **Dependency path resolution** (`bridge/context_provider.py`) — relative file paths now resolved against project root before lookup

### Changed
- **Refactored `quality_cmd.py`** — extracted `_output_safety()`, `_output_report_pipe()`, `_output_report_rich()` helpers to reduce cyclomatic complexity from 38 to ~12
- **Refactored `metrics_cmd.py`** — extracted `_output_history()`, `_output_trend()`, `_output_current_metrics()` helpers to reduce cyclomatic complexity from 31 to ~10
- **Refactored `indexing_service.py`** — extracted `_extract_symbols()` and `_compute_index_stats()` from `run_indexing()` to reduce complexity from 31 to ~18

## [0.24.0] — Phase 24: Self-Improving Development Loop

### Added
- **Evolution engine** (`evolution/engine.py`) — orchestrates the self-improving development loop: analyse → select task → build context → generate patch → test → commit/revert → repeat
- **Budget guard** (`evolution/budget_guard.py`) — enforces hard limits on tokens (default 20 000), iterations (default 5), and wall-clock time (default 600 s) so the loop cannot run away
- **Test runner** (`evolution/test_runner.py`) — runs pytest as a subprocess with timeout, parses summary into structured `TestResult` dataclass
- **Commit manager** (`evolution/commit_manager.py`) — safe git operations (diff, stage, commit, revert, stash) for the evolution cycle
- **Task selector** (`evolution/task_selector.py`) — priority-based selection: fix failing tests → add type hints → improve error handling → reduce duplication → small optimisation
- **Context builder** (`evolution/context_builder.py`) — assembles minimal LLM prompt (system rules + task + file contents + git diff) within a token budget
- **Patch generator** (`evolution/patch_generator.py`) — calls LLM for a unified diff, validates safety limits (≤ 3 files, ≤ 200 lines), applies via `git apply`
- **`codexa evolve` CLI command** (`cli/commands/evolve_cmd.py`) — `--iterations`, `--budget`, `--timeout`, `--path` flags; Rich progress output with per-iteration details
- **Evolution history** — every run appended to `.codexa/evolution_history.json` with full iteration records
- **Phase 24 test suite** (`test_phase24.py`) — tests covering all 7 evolution modules, CLI command, module imports, version check

## [0.23.0] — Phase 23: Persistent Intelligence Index

### Added
- **Index manifest** (`storage/index_manifest.py`) — versioned metadata tracking schema version, embedding model, dimensions, timestamps, file/chunk/symbol counts, and project root for index integrity checks
- **Symbol registry** (`storage/symbol_registry.py`) — persistent queryable directory of all code symbols (functions, classes, methods, imports) with multi-criteria find, substring search, per-file removal, and language/kind summaries
- **Index statistics** (`storage/index_stats.py`) — comprehensive health metrics including per-language coverage (files, chunks, symbols, lines), staleness tracking, average chunk size, and indexing duration
- **Query history** (`storage/query_history.py`) — cross-session search analytics with FIFO eviction (max 500), popular queries/files tracking, and per-query result metadata (score, languages, top files)
- **Indexing integration** — `run_indexing()` now populates manifest, symbol registry, and stats after every index run; `IndexingResult` includes `symbols_extracted` count
- **Search integration** — `search_codebase()` records every query in persistent history with result count, top score, languages, and top files
- **Phase 23 test suite** (`test_phase23.py`) — tests covering all 4 storage modules, indexing integration, search integration, module imports, version check

## [0.22.0] — Phase 22: LLM Caching + Rate Limiting

### Added
- **LLM response cache** (`llm/cache.py`) — disk-backed JSON cache with SHA-256 keys, TTL expiration, and max-entry eviction (LRU oldest-first)
- **Rate limiter** (`llm/rate_limiter.py`) — sliding-window enforcement for requests-per-minute (RPM) and tokens-per-minute (TPM) with blocking and non-blocking modes
- **CachedProvider** (`llm/cached_provider.py`) — transparent wrapper that adds caching and rate limiting to any LLMProvider
- **LLMConfig fields** — `cache_enabled`, `cache_ttl_hours`, `cache_max_entries`, `rate_limit_rpm`, `rate_limit_tpm` in config settings
- **CLI integration** — `_wrap_provider()` in ask/chat/investigate commands auto-wraps providers with CachedProvider based on config
- **CacheStats / RateLimiterStats** — statistics tracking with hit rate, eviction count, rejected requests
- **Phase 22 test suite** (`test_phase22.py`) — 74 tests covering cache, rate limiter, CachedProvider, config, CLI integration, end-to-end flows

## [0.21.0] — Phase 21: Mypy Strict Typing & Coverage Gate

### Added
- **Mypy strict configuration** — `[tool.mypy]` in pyproject.toml with `strict = true`, `warn_return_any`, `warn_unused_ignores`
- **Pytest coverage gate** — `[tool.coverage.run]`/`[tool.coverage.report]` with `fail_under = 70`, `show_missing`, `skip_covered`
- **Phase 21 test suite** (`test_phase21.py`) — regression guards for all 49 mypy fixes, config validation, type annotation checks
- **TYPE_CHECKING guards** — proper `if TYPE_CHECKING:` pattern for lazy LLM provider imports in CLI commands

### Fixed
- **49 mypy strict errors** across 26 source files resolved:
  - `ci/pr.py` — added missing `SafetyReport` import (name-defined)
  - `ci/impact.py` — renamed loop vars to avoid `AffectedSymbol`/`Symbol` type conflict
  - `cli/commands/quality_cmd.py` — renamed duplicate loop var (`d` → `dup`) to fix type narrowing
  - `llm/investigation.py` — `.module` → `.import_text` on `FileDependency` (attr-defined)
  - `llm/cross_refactor.py` — fixed `tuple[str, ...]` → `tuple[str, str]` for pair keys
  - `cli/commands/viz_cmd.py` — `ws.repos.values()` → `ws.repos` (list, not dict)
  - `search/formatter.py` — added `str | Syntax` annotation for fallback
  - `embeddings/generator.py` — added `None` guard for `get_sentence_embedding_dimension()`
  - `docs/__init__.py` — `click.BaseCommand` → `click.Group | click.Command`
  - `cli/commands/doctor_cmd.py` — `dict` → `dict[str, Any]` (4 functions)
  - `services/search_service.py` — `dict` → `dict[str, Any]`
  - `tools/__init__.py` — `dict` → `dict[str, Any]`, explicit `ToolResult` cast
  - `bridge/context_provider.py` — `dict` → `dict[str, Any]` (2 callees lists)
  - `llm/ollama_provider.py` — explicit typed variables for `json.loads` and `resp.status`
  - `storage/vector_store.py` — `int()` cast on `faiss.Index.ntotal`
  - `ci/templates.py` — `Callable[..., str]` annotation for template generators
  - `web/api.py` — typed variable for `json.loads` result
  - `plugins/__init__.py` — removed stale `type: ignore[union-attr]`
  - `llm/openai_provider.py` — removed stale `type: ignore[import-untyped]`
  - `cli/commands/{chat,ask,investigate}_cmd.py` — typed `_get_provider` with `TYPE_CHECKING` guard

### Metrics
- **0 mypy strict errors** on 104 source files
- **79%+ test coverage** (above 70% gate)
- **2028+ tests** maintained

## [0.20.0] — Phase 20: Deep Coverage & Copilot Integration

### Added
- **GitHub Copilot integration** — `.github/copilot-instructions.md` with full CodexA tool instructions for system prompt
- **README Copilot setup guide** — 7-step guide for VS Code Copilot configuration, example conversations, and settings
- **Phase 20 test suite** (`test_phase20.py`) — 385 deep-coverage tests across all 22 subpackages
- **Phase 20b test suite** (`test_phase20b.py`) — 289 extended tests for config, bridge, LLM, context, analysis, indexing, storage, workspace, daemon, CI, docs, scalability, plugins, tools, and version
- **Phase 20c test suite** (`test_phase20c.py`) — 150 tests for visualization functions, search formatter, context engine (CallGraph, DependencyMap, ContextWindow, ContextBuilder), memory (SessionMemory, WorkspaceMemory), AI features (LanguageStats, RepoSummary, CodeExplanation, summarize/explain), reasoning/investigation results, services
- 2028 total tests (up from 1204) — **824 new tests**
- 31 CLI commands, 22 plugin hooks

## [0.19.0] — Phase 19: AI Agent Tooling Protocol

### Added
- **Tool Invocation Protocol** — `ToolInvocation`, `ToolExecutionResult`, `ToolError` dataclasses with JSON round-trip
- **`ToolErrorCode` enum** — typed error codes (`unknown_tool`, `invalid_arguments`, `missing_required_arg`, `execution_error`, `timeout`, `permission_denied`)
- **Tool Execution Engine** — `ToolExecutor` with argument validation, built-in + plugin tool routing, timing, and batch execution
- **Plugin tool registration** — `register_plugin_tool()` / `unregister_plugin_tool()` with collision protection
- **Extended capability manifest** — `BridgeCapabilities.tools` field with full tool schemas
- **Bridge HTTP endpoints** — `POST /tools/invoke`, `GET /tools/list`, `GET /tools/stream` (SSE)
- **Bridge protocol extensions** — `INVOKE_TOOL` and `LIST_TOOLS` request kinds (12 total)
- **`codexa tool list`** — list all available tools with descriptions
- **`codexa tool run <name>`** — invoke a tool with `--arg key=value` pairs
- **`codexa tool schema <name>`** — display tool parameter schema
- **3 new plugin hooks** — `REGISTER_TOOL`, `PRE_TOOL_INVOKE`, `POST_TOOL_INVOKE` (22 total)
- **AI safety guardrails** — deterministic tools only, schema validation, no arbitrary code execution
- **AI_TOOL_PROTOCOL.md** — auto-generated documentation for the tool protocol
- 31 CLI commands (up from 30)
- 70+ new tests

## [0.18.0] — Phase 18: Developer Workflow Intelligence

### Added
- **Hotspot detection engine** — multi-factor risk scoring (complexity, duplication, fan-in/out, git churn)
- **Impact analysis engine** — BFS blast radius prediction via call graph and dependency map
- **Symbol trace tool** — upstream callers, downstream callees, cross-file execution paths
- **`codexa hotspots`** — identify high-risk code areas with `--top-n`, `--include-git/--no-git`
- **`codexa impact <target>`** — analyse blast radius of a symbol or file change
- **`codexa trace <symbol>`** — trace execution relationships upstream and downstream
- **6 new plugin hooks** — `PRE/POST_HOTSPOT_ANALYSIS`, `PRE/POST_IMPACT_ANALYSIS`, `PRE/POST_TRACE` (19 total)
- **Pipeline-oriented output** — all 3 new commands support `--json` and `--pipe` modes
- **WORKFLOW_INTELLIGENCE.md** — auto-generated documentation for workflow intelligence features
- 30 CLI commands (up from 27)

## [0.17.0] — Phase 17: Code Quality Metrics & Trends

### Added
- **Maintainability index** — per-file and project-wide MI (0-100) based on SEI formula
- **FileMetrics / ProjectMetrics** — LOC, comment ratio, complexity aggregation
- **Quality snapshots** — save timestamped metric captures via WorkspaceMemory
- **Trend analysis** — linear regression over historical snapshots (improving/stable/degrading)
- **Quality policies & gates** — configurable thresholds with CI-friendly enforcement
- **`codexa metrics`** — compute metrics, save snapshots, view history, track trends
- **`codexa gate`** — enforce quality gates with `--strict` exit-code support
- **QualityConfig** — new configuration section in `.codexa/config.json`
- **QUALITY_METRICS.md** — auto-generated documentation for metrics features
- Updated CI reference docs with new commands
- 27 CLI commands (up from 25)

### Fixed
- Unicode encoding crash on Windows cp1252 consoles (ASCII fallback for log icons)

## [0.1.0] — 2026-03-07

### Phase 1: CLI Framework
- Added Click-based CLI with `codexa init`, `codexa index`, `codexa search` commands
- Added Pydantic v2 configuration models (`AppConfig`, `EmbeddingConfig`, `SearchConfig`, `IndexConfig`)
- Added Rich-powered logging with colored output
- Added project scaffolding: `.codexa/` directory with `config.json` and index storage
- 52 tests

### Phase 2: Repository Indexing
- Added file scanner with configurable ignore patterns and extension filters
- Added code chunker with line-boundary splitting and overlap
- Added sentence-transformer embeddings (`all-MiniLM-L6-v2`, 384 dimensions)
- Added FAISS `IndexFlatIP` vector store with metadata persistence
- Added hash-based incremental indexing (skips unchanged files)
- 65 tests (117 cumulative)

### Phase 3: Semantic Search
- Added search service: query → embedding → FAISS cosine similarity
- Added Rich terminal formatter with syntax-highlighted code panels
- Added JSON output mode for AI/programmatic consumption
- Added configurable top-k and score threshold filtering
- 14 tests (131 cumulative)

### Phase 4: Code Parsing
- Added tree-sitter AST parsing for Python, JavaScript, Java, Go, Rust
- Added symbol extraction: functions, classes, methods, imports
- Added parameter extraction and decorator detection
- Added Go receiver method detection and Rust impl block traversal
- Error-tolerant parsing for files with syntax errors
- 54 tests (185 cumulative)

### Phase 5: Context Engine
- Added `ContextBuilder` for multi-file symbol indexing and context windows
- Added `CallGraph` for lightweight reference-based call edges
- Added `DependencyMap` for file-level import tracking
- Added `ContextWindow` with human-readable rendering
- Added cross-file symbol search
- 45 tests (230 cumulative)

### Phase 6: AI Features
- Added `RepoSummary` with per-language statistics
- Added `generate_ai_context()` for structured LLM-friendly JSON output
- Added `explain_symbol()` and `explain_file()` code explanation helpers
- Added focus modes: filter by symbol name or file path
- Full serialization: `to_dict()`, `to_json()`, `render()`
- 42 tests (272 cumulative)

### Phase 7: Platform Evolution
- **AST-Aware Semantic Chunking**: `SemanticChunk`, `semantic_chunk_code()`, `semantic_chunk_file()` — splits on function/class/method boundaries via tree-sitter, falls back to line-based chunking
- **Enhanced Embedding Pipeline**: `preprocess_code_for_embedding()`, `generate_semantic_embeddings()`, `generate_query_embedding()` — semantic label prepending and format normalization
- **Background Intelligence**: `FileWatcher` (polling-based change detection), `AsyncIndexer` (queue-based background indexing), `IndexingDaemon` (combined watcher + indexer)
- **AI Tool Interaction Layer**: `ToolRegistry` with 8 tools (`semantic_search`, `explain_symbol`, `explain_file`, `summarize_repo`, `find_references`, `get_dependencies`, `get_call_graph`, `get_context`), `ToolResult` protocol, `TOOL_DEFINITIONS` schema
- **Expanded CLI**: `codexa explain`, `codexa summary`, `codexa deps`, `codexa watch` commands (all with `--json` support)
- **Plugin Architecture SDK**: `PluginBase`, `PluginHook` (9 hook points), `PluginManager` with discovery, activation, and chained hook dispatch
- **Scalability**: `BatchProcessor`, `MemoryAwareEmbedder`, `ParallelScanner` for memory-safe batch processing and concurrent I/O
- 119 new tests (391 cumulative)

### Phase 8: AI Coding Assistant Platform
- **LLM Provider Abstraction**: `LLMProvider` ABC with `OpenAIProvider`, `OllamaProvider`, `MockProvider`; `LLMMessage`/`LLMResponse` structured types
- **AI Reasoning Engine**: `ReasoningEngine` orchestrating semantic search + LLM; `ask()`, `review()`, `refactor()`, `suggest()` workflows with structured result types
- **Context & Memory**: `SessionMemory` (in-process), `WorkspaceMemory` (persistent `.codexa/memory.json`), multi-step reasoning chains
- **Safety Validator**: `SafetyValidator` scans LLM output for dangerous patterns (eval, exec, shell injection, SQL injection); extensible pattern system
- **New CLI Commands**: `codexa ask`, `codexa review`, `codexa refactor`, `codexa suggest` (all with `--json` support)
- **Plugin AI Hooks**: `PRE_AI` and `POST_AI` added to `PluginHook` (11 hooks total)
- **LLMConfig**: provider, model, api_key, base_url, temperature, max_tokens — integrated into `AppConfig`
- 62 new tests (453 cumulative)

### Phase 9: External AI Cooperation Layer
- **Agent Cooperation Protocol**: `AgentRequest`/`AgentResponse` JSON protocol, `RequestKind` enum (10 types), `BridgeCapabilities` manifest for external tool discovery
- **Context Injection API**: `ContextProvider` with 8 methods — `context_for_query()`, `context_for_symbol()`, `context_for_file()`, `context_for_repo()`, `validate_code()`, `get_dependencies()`, `get_call_graph()`, `find_references()`
- **HTTP Bridge Server**: `BridgeServer` using stdlib `http.server` (zero deps) with REST endpoints, CORS, background thread support, direct `dispatch()` method
- **VSCode Extension Interface**: `VSCodeBridge` adapting output to VS Code shapes (hover, diagnostics, completions, code-actions); `generate_extension_manifest()` helper
- **New CLI Commands**: `codexa serve` (start bridge server), `codexa context` (generate structured context for piping); 13 commands total
- Tests for all new modules

### Phase 10: Multi-Repository Workspace Intelligence
- **Workspace Model**: `RepoEntry`, `WorkspaceManifest`, `Workspace` class with load/save persistence
- Per-repo vector indexes under `.codexa/repos/<name>/`, merged cross-repo search
- **6 CLI subcommands**: `codexa workspace init|add|remove|list|index|search`
- 52 new tests (516 → 568), 14 CLI commands

### Phase 11: Multi-Language Parsing Expansion
- **6 new tree-sitter grammars**: TypeScript, TSX, C++, C#, Ruby, PHP
- `_LANGUAGE_FACTORY` for non-standard APIs, enhanced `_find_name()` for C++/Ruby/PHP
- Ruby import filtering, semantic chunker integration for all new languages
- 65 new tests (568 → 633), 11 languages total

### Phase 12: Platform Enhancements
- **Plugin hooks**: `ON_STREAM`, `CUSTOM_VALIDATION` (13 hooks total)
- **Reasoning improvements**: context pruning, priority scoring, explainability metadata
- **Security patterns**: path traversal, hardcoded secrets, XSS, insecure crypto, insecure HTTP, SSL bypass (17 total)
- **VSCode streaming**: `StreamChunk`, SSE formatting, `build_streaming_context()`
- 49 new tests (633 → 682)

## [0.13.0] — 2026-03-07

### Phase 13: Open Source Readiness & Developer Experience
- **OSS Foundation**: MIT LICENSE, CONTRIBUTING.md, SECURITY.md
- **GitHub CI**: `.github/workflows/ci.yml` — pytest matrix (Python 3.11-3.13, Ubuntu + Windows)
- **GitHub Templates**: bug report, feature request, PR template
- **Auto-Documentation Generator**: `generate_cli_reference()`, `generate_plugin_reference()`, `generate_bridge_reference()`, `generate_tool_reference()`, `generate_all_docs()`
- **New CLI Commands**: `codexa docs` (auto-generate Markdown docs), `codexa doctor` (environment health check), `codexa plugin new|list|info` (plugin scaffold & management)
- **CLI Ergonomics**: `--pipe` global flag for pipeline-friendly output, version bump to 0.13.0
- **Sample Plugins**: `search_annotator.py` (POST_SEARCH), `code_quality.py` (CUSTOM_VALIDATION)
- **Enhanced pyproject.toml**: classifiers, keywords, project URLs, readme metadata
- 80 new tests (682 → 762), 17 CLI commands total

## [0.14.0] — 2026-03-07

### Phase 14: Web Interface & Developer Accessibility Layer
- **REST API** (`web/api.py`): `APIHandler` with GET endpoints (`/health`, `/api/search`, `/api/symbols`, `/api/deps`, `/api/callgraph`, `/api/summary`) and POST endpoints (`/api/ask`, `/api/analyze`); CORS headers, query-string helpers
- **Visualization** (`web/visualize.py`): Mermaid diagram generators — `render_call_graph()`, `render_dependency_graph()`, `render_workspace_graph()`, `render_symbol_map()`
- **Web UI** (`web/ui.py`): Server-rendered HTML with dark theme, vanilla JS; pages: Search, Symbols, Workspace, Visualize
- **Combined Server** (`web/server.py`): `WebServer` merging API + UI on single port (default 8080); stdlib `http.server`, zero deps
- **New CLI Commands**: `codexa web` (start web server), `codexa viz` (generate Mermaid diagrams with `--json`, `--output`)
- **Auto-Documentation**: `generate_web_reference()` → `WEB.md`
- 74 new tests (762 → 836), 19 CLI commands total

## [0.16.0] — 2026-03-07

### Phase 16: Advanced AI Workflows
- **Conversation Memory** (`llm/conversation.py`): `ConversationSession` with uuid-based IDs, role-typed messages, turn counting, `get_messages_for_llm(max_turns)` for context window management, JSON serialization round-trip; `SessionStore` for file-backed persistence under `.codexa/sessions/` with path traversal prevention, list/delete/get-or-create operations
- **Investigation Chains** (`llm/investigation.py`): `InvestigationChain` with LLM planner loop — structured JSON prompting for thought/action/action_input, three built-in actions (search, analyze, deps), automatic conclusion forcing at step limit, `SessionMemory` chain tracking, fallback parsing for non-JSON LLM responses
- **Cross-Repo Refactoring** (`llm/cross_refactor.py`): `analyze_cross_repo()` with per-repo symbol indexing, cross-repo duplicate detection via trigram Jaccard similarity (reuses `ci/quality.py` internals), optional LLM-powered refactoring advice generation, workspace-aware multi-repo analysis
- **Streaming LLM** (`llm/streaming.py`): `stream_chat()` unified API with provider-specific streamers (Ollama native HTTP streaming, OpenAI SDK streaming, MockProvider word-by-word simulation), `StreamEvent` with SSE serialization, `PluginHook.ON_STREAM` dispatch for real-time plugin hooks, graceful fallback for unknown providers
- **New CLI Commands**: `codexa chat` (multi-turn with `--session`, `--list-sessions`, `--max-turns`, `--json`, `--pipe`), `codexa investigate` (autonomous investigation with `--max-steps`, `--json`, `--pipe`), `codexa cross-refactor` (cross-repo analysis with `--threshold`, `--json`, `--pipe`)
- **Auto-Documentation**: `generate_ai_workflows_reference()` → `AI_WORKFLOWS.md`
- 64 new tests (915 → 979), 25 CLI commands total

## [0.15.0] — 2026-03-07

### Phase 15: CI/CD & Contribution Safety Pipeline
- **Quality Analyzers** (`ci/quality.py`): Cyclomatic complexity scoring (14 decision patterns), dead code detection (call graph + body heuristic), duplicate logic detection (trigram Jaccard similarity), aggregate `QualityReport` with `analyze_project()`
- **PR Intelligence** (`ci/pr.py`): `build_change_summary()` per-file symbol diff, `analyze_impact()` blast-radius via call graph traversal, `suggest_reviewers()` domain-based heuristic, `compute_risk()` 0-100 composite score with factors, `generate_pr_report()` full advisory report
- **CI Templates** (`ci/templates.py`): `generate_analysis_workflow()` (full GitHub Actions), `generate_safety_workflow()` (lightweight safety-only), `generate_precommit_config()` (`.pre-commit-config.yaml`)
- **Pre-commit Hooks** (`ci/hooks.py`): `run_precommit_check()` with SafetyValidator + CUSTOM_VALIDATION plugin dispatch
- **New CLI Commands**: `codexa quality` (complexity/dead-code/duplicates/safety with `--json`, `--pipe`, `--safety-only`), `codexa pr-summary` (change summary/impact/reviewers/risk with `--json`, `--pipe`, `--files`), `codexa ci-gen` (template generation: analysis/safety/precommit with `--output`, `--python-version`)
- **Auto-Documentation**: `generate_ci_reference()` → `CI.md`
- 79 new tests (836 → 915), 22 CLI commands total
