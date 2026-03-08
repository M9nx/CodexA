# Changelog

All notable changes to CodexA are documented in this file.

## [0.18.0] — Phase 18: Developer Workflow Intelligence

### Added
- **Hotspot detection engine** — multi-factor risk scoring (complexity, duplication, fan-in/out, git churn)
- **Impact analysis engine** — BFS blast radius prediction via call graph and dependency map
- **Symbol trace tool** — upstream callers, downstream callees, cross-file execution paths
- **`codex hotspots`** — identify high-risk code areas with `--top-n`, `--include-git/--no-git`
- **`codex impact <target>`** — analyse blast radius of a symbol or file change
- **`codex trace <symbol>`** — trace execution relationships upstream and downstream
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
- **`codex metrics`** — compute metrics, save snapshots, view history, track trends
- **`codex gate`** — enforce quality gates with `--strict` exit-code support
- **QualityConfig** — new configuration section in `.codex/config.json`
- **QUALITY_METRICS.md** — auto-generated documentation for metrics features
- Updated CI reference docs with new commands
- 27 CLI commands (up from 25)

### Fixed
- Unicode encoding crash on Windows cp1252 consoles (ASCII fallback for log icons)

## [0.1.0] — 2026-03-07

### Phase 1: CLI Framework
- Added Click-based CLI with `codex init`, `codex index`, `codex search` commands
- Added Pydantic v2 configuration models (`AppConfig`, `EmbeddingConfig`, `SearchConfig`, `IndexConfig`)
- Added Rich-powered logging with colored output
- Added project scaffolding: `.codex/` directory with `config.json` and index storage
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
- **Expanded CLI**: `codex explain`, `codex summary`, `codex deps`, `codex watch` commands (all with `--json` support)
- **Plugin Architecture SDK**: `PluginBase`, `PluginHook` (9 hook points), `PluginManager` with discovery, activation, and chained hook dispatch
- **Scalability**: `BatchProcessor`, `MemoryAwareEmbedder`, `ParallelScanner` for memory-safe batch processing and concurrent I/O
- 119 new tests (391 cumulative)

### Phase 8: AI Coding Assistant Platform
- **LLM Provider Abstraction**: `LLMProvider` ABC with `OpenAIProvider`, `OllamaProvider`, `MockProvider`; `LLMMessage`/`LLMResponse` structured types
- **AI Reasoning Engine**: `ReasoningEngine` orchestrating semantic search + LLM; `ask()`, `review()`, `refactor()`, `suggest()` workflows with structured result types
- **Context & Memory**: `SessionMemory` (in-process), `WorkspaceMemory` (persistent `.codex/memory.json`), multi-step reasoning chains
- **Safety Validator**: `SafetyValidator` scans LLM output for dangerous patterns (eval, exec, shell injection, SQL injection); extensible pattern system
- **New CLI Commands**: `codex ask`, `codex review`, `codex refactor`, `codex suggest` (all with `--json` support)
- **Plugin AI Hooks**: `PRE_AI` and `POST_AI` added to `PluginHook` (11 hooks total)
- **LLMConfig**: provider, model, api_key, base_url, temperature, max_tokens — integrated into `AppConfig`
- 62 new tests (453 cumulative)

### Phase 9: External AI Cooperation Layer
- **Agent Cooperation Protocol**: `AgentRequest`/`AgentResponse` JSON protocol, `RequestKind` enum (10 types), `BridgeCapabilities` manifest for external tool discovery
- **Context Injection API**: `ContextProvider` with 8 methods — `context_for_query()`, `context_for_symbol()`, `context_for_file()`, `context_for_repo()`, `validate_code()`, `get_dependencies()`, `get_call_graph()`, `find_references()`
- **HTTP Bridge Server**: `BridgeServer` using stdlib `http.server` (zero deps) with REST endpoints, CORS, background thread support, direct `dispatch()` method
- **VSCode Extension Interface**: `VSCodeBridge` adapting output to VS Code shapes (hover, diagnostics, completions, code-actions); `generate_extension_manifest()` helper
- **New CLI Commands**: `codex serve` (start bridge server), `codex context` (generate structured context for piping); 13 commands total
- Tests for all new modules

### Phase 10: Multi-Repository Workspace Intelligence
- **Workspace Model**: `RepoEntry`, `WorkspaceManifest`, `Workspace` class with load/save persistence
- Per-repo vector indexes under `.codex/repos/<name>/`, merged cross-repo search
- **6 CLI subcommands**: `codex workspace init|add|remove|list|index|search`
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
- **New CLI Commands**: `codex docs` (auto-generate Markdown docs), `codex doctor` (environment health check), `codex plugin new|list|info` (plugin scaffold & management)
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
- **New CLI Commands**: `codex web` (start web server), `codex viz` (generate Mermaid diagrams with `--json`, `--output`)
- **Auto-Documentation**: `generate_web_reference()` → `WEB.md`
- 74 new tests (762 → 836), 19 CLI commands total

## [0.16.0] — 2026-03-07

### Phase 16: Advanced AI Workflows
- **Conversation Memory** (`llm/conversation.py`): `ConversationSession` with uuid-based IDs, role-typed messages, turn counting, `get_messages_for_llm(max_turns)` for context window management, JSON serialization round-trip; `SessionStore` for file-backed persistence under `.codex/sessions/` with path traversal prevention, list/delete/get-or-create operations
- **Investigation Chains** (`llm/investigation.py`): `InvestigationChain` with LLM planner loop — structured JSON prompting for thought/action/action_input, three built-in actions (search, analyze, deps), automatic conclusion forcing at step limit, `SessionMemory` chain tracking, fallback parsing for non-JSON LLM responses
- **Cross-Repo Refactoring** (`llm/cross_refactor.py`): `analyze_cross_repo()` with per-repo symbol indexing, cross-repo duplicate detection via trigram Jaccard similarity (reuses `ci/quality.py` internals), optional LLM-powered refactoring advice generation, workspace-aware multi-repo analysis
- **Streaming LLM** (`llm/streaming.py`): `stream_chat()` unified API with provider-specific streamers (Ollama native HTTP streaming, OpenAI SDK streaming, MockProvider word-by-word simulation), `StreamEvent` with SSE serialization, `PluginHook.ON_STREAM` dispatch for real-time plugin hooks, graceful fallback for unknown providers
- **New CLI Commands**: `codex chat` (multi-turn with `--session`, `--list-sessions`, `--max-turns`, `--json`, `--pipe`), `codex investigate` (autonomous investigation with `--max-steps`, `--json`, `--pipe`), `codex cross-refactor` (cross-repo analysis with `--threshold`, `--json`, `--pipe`)
- **Auto-Documentation**: `generate_ai_workflows_reference()` → `AI_WORKFLOWS.md`
- 64 new tests (915 → 979), 25 CLI commands total

## [0.15.0] — 2026-03-07

### Phase 15: CI/CD & Contribution Safety Pipeline
- **Quality Analyzers** (`ci/quality.py`): Cyclomatic complexity scoring (14 decision patterns), dead code detection (call graph + body heuristic), duplicate logic detection (trigram Jaccard similarity), aggregate `QualityReport` with `analyze_project()`
- **PR Intelligence** (`ci/pr.py`): `build_change_summary()` per-file symbol diff, `analyze_impact()` blast-radius via call graph traversal, `suggest_reviewers()` domain-based heuristic, `compute_risk()` 0-100 composite score with factors, `generate_pr_report()` full advisory report
- **CI Templates** (`ci/templates.py`): `generate_analysis_workflow()` (full GitHub Actions), `generate_safety_workflow()` (lightweight safety-only), `generate_precommit_config()` (`.pre-commit-config.yaml`)
- **Pre-commit Hooks** (`ci/hooks.py`): `run_precommit_check()` with SafetyValidator + CUSTOM_VALIDATION plugin dispatch
- **New CLI Commands**: `codex quality` (complexity/dead-code/duplicates/safety with `--json`, `--pipe`, `--safety-only`), `codex pr-summary` (change summary/impact/reviewers/risk with `--json`, `--pipe`, `--files`), `codex ci-gen` (template generation: analysis/safety/precommit with `--output`, `--python-version`)
- **Auto-Documentation**: `generate_ci_reference()` → `CI.md`
- 79 new tests (836 → 915), 22 CLI commands total
