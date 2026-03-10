# CodexA — Project Roadmap

## Completed Phases

### Phase 1: CLI Framework ✅
- Click-based CLI with `codexa init`, `codexa index`, `codexa search` commands
- Pydantic v2 configuration models (`AppConfig`, `EmbeddingConfig`, `SearchConfig`, `IndexConfig`)
- Rich-powered logging with colored output and progress indicators
- Project scaffolding: `.codexa/` directory, `config.json`, index storage
- **52 tests** | Commit `de3c69c`

### Phase 2: Repository Indexing ✅
- File scanner with configurable ignore patterns and extension filters
- Code chunker with line-boundary splitting and configurable overlap
- Sentence-transformer embeddings using `all-MiniLM-L6-v2` (384-dim)
- FAISS `IndexFlatIP` vector store with metadata persistence
- Hash-based incremental indexing (only re-indexes changed files)
- **65 tests** | Commit `4466b3c`

### Phase 3: Semantic Search ✅
- Query → embedding → FAISS cosine similarity search pipeline
- Rich terminal formatter with syntax-highlighted code panels
- JSON output mode for AI/programmatic consumption
- Configurable top-k and score threshold filtering
- **14 tests** | Commit `7a69d38`

### Phase 4: Code Parsing ✅
- Tree-sitter AST parsing for **Python, JavaScript, Java, Go, Rust**
- Symbol extraction: functions, classes, methods, imports
- Parameter extraction and decorator detection
- Go receiver method detection, Rust impl block traversal
- Error-tolerant parsing (handles syntax errors gracefully)
- **54 tests** | Commit `520d8e4`

### Phase 5: Context Engine ✅
- `ContextBuilder`: multi-file symbol indexing and context window assembly
- `CallGraph`: lightweight reference-based call/dependency edges
- `DependencyMap`: file-level import tracking across the codebase
- `ContextWindow`: renders human-readable context summaries with imports, related symbols
- Cross-file symbol search and multi-file indexing support
- **45 tests** | Commit `9c66f8a`

### Phase 6: AI Features ✅
- `RepoSummary`: repository-wide statistics with per-language breakdowns
- `generate_ai_context()`: structured JSON context for LLM consumption
- `explain_symbol()` / `explain_file()`: structural code explanation helpers
- Focus modes: filter by symbol name or file path
- Full serialization support: `to_dict()`, `to_json()`, `render()`
- **42 tests** | Commit `7d84716`

**Total: 272 tests, all passing.**

### Phase 7: Platform Evolution ✅
Transformed CodexA from a CLI tool into a **developer semantic intelligence platform**.

#### AST-Aware Semantic Chunking
- `SemanticChunk` dataclass extending `CodeChunk` with symbol metadata
- `semantic_chunk_code()` / `semantic_chunk_file()`: split code along function/class/method boundaries using tree-sitter
- Automatic sub-splitting for oversized symbols, uncovered-block collection
- Falls back to line-based chunking for unsupported languages
- Semantic labels (e.g. `[python] function authenticate(user, password)`) for embedding quality

#### Enhanced Embedding Pipeline
- `preprocess_code_for_embedding()`: prepend semantic labels, collapse blanks, normalize formatting
- `generate_semantic_embeddings()`: recommended entry point (preprocess → encode)
- `generate_query_embedding()`: light preprocessing for search queries

#### Background Intelligence Subsystem
- `FileWatcher`: polling-based file change detection with hash comparison
- `AsyncIndexer`: queue-based background indexing with completion callbacks
- `IndexingDaemon`: combines watcher + indexer into a single start/stop API
- `codexa watch` CLI command with configurable poll interval

#### AI Tool Interaction Layer
- `ToolResult` structured response protocol for LLM agents
- `ToolRegistry` with 8 tools: `semantic_search`, `explain_symbol`, `explain_file`, `summarize_repo`, `find_references`, `get_dependencies`, `get_call_graph`, `get_context`
- `TOOL_DEFINITIONS` schema manifest for tool discovery
- Lazy ContextBuilder initialization, per-file and directory indexing

#### Expanded CLI Commands
- `codexa explain <symbol>`: structural explanation of symbols or entire files
- `codexa summary`: repository summary with language breakdown
- `codexa deps [target]`: dependency/import map (single file or whole project)
- `codexa watch`: background daemon for automatic re-indexing on file changes
- All commands support `--json` output mode

#### Plugin Architecture SDK
- `PluginBase` abstract class with `metadata()`, `activate()`, `deactivate()`, `on_hook()`
- `PluginHook` enum: `PRE_INDEX`, `POST_INDEX`, `ON_CHUNK`, `PRE_SEARCH`, `POST_SEARCH`, `PRE_ANALYSIS`, `POST_ANALYSIS`, `ON_FILE_CHANGE`, `CUSTOM`
- `PluginManager`: register, activate/deactivate, dispatch hooks in chain, plugin info
- `discover_from_directory()`: auto-discover plugins via `create_plugin()` factory

#### Scalability & Performance
- `BatchProcessor`: configurable batch size with progress callbacks and stats
- `MemoryAwareEmbedder`: memory-safe embedding generation in batches
- `ParallelScanner`: thread-based concurrent file processing

- **119 new tests (391 total)** | Commit `8a45b9a`

**Total: 391 tests, all passing.**

### Phase 8: AI Coding Assistant Platform ✅
Transformed CodexA from a semantic code search engine into a **full AI coding assistant / agent platform**.

#### LLM Provider Abstraction Layer
- `LLMProvider` abstract base class with `complete()`, `chat()`, `is_available()`
- `LLMMessage` / `LLMResponse` structured data types with serialization
- `OpenAIProvider`: OpenAI Chat Completions API integration (GPT-3.5/4)
- `OllamaProvider`: Ollama local model server integration (stdlib HTTP, no extra deps)
- `MockProvider`: deterministic mock for testing with response queuing and call history

#### AI Reasoning Engine
- `ReasoningEngine`: orchestrates semantic search + parsed symbols + LLM conversations
- `ask()`: natural-language Q&A about the codebase with context snippets
- `review()`: AI-powered code review returning structured issues + summary
- `refactor()`: AI-assisted refactoring with explanation and safety validation
- `suggest()`: intelligent suggestions with "why" reasoning and priority levels
- Structured result types: `AskResult`, `ReviewResult`, `RefactorResult`, `SuggestResult`

#### Context & Memory Management
- `SessionMemory`: in-process memory with keyword search, recency, and max-entry eviction
- `WorkspaceMemory`: persistent memory stored in `.codexa/memory.json` with cross-session caching
- `MemoryEntry` / `ReasoningStep` data types with full serialization
- Multi-step reasoning chains: `start_chain()`, `add_step()`, `get_chain()`

#### Safety & Validation Layer
- `SafetyValidator`: scans LLM-generated code for dangerous patterns (eval, exec, os.system, shell injection, SQL injection, etc.)
- `SafetyReport` / `SafetyIssue` structured output with line numbers and severity
- Extensible pattern system with custom pattern injection
- Integrated into `codexa refactor` workflow

#### Expanded CLI Commands
- `codexa ask <question>`: natural-language Q&A about the codebase
- `codexa review <file>`: AI-powered code review with severity levels
- `codexa refactor <file>`: AI-assisted refactoring with safety checks
- `codexa suggest <target>`: intelligent suggestions with priority and rationale
- All commands support `--json` output mode

#### Plugin AI Hooks
- Added `PRE_AI` and `POST_AI` hooks to `PluginHook` enum (11 hooks total)
- Enables plugins to intercept and transform AI requests/responses

#### Configuration Extension
- `LLMConfig`: provider, model, api_key, base_url, temperature, max_tokens
- Integrated into `AppConfig` with full serialization roundtrip

- **62 new tests (453 total)**

**Total: 453 tests, all passing.**

### Phase 9: External AI Cooperation Layer ✅
Designed CodexA as a **lightweight AI developer assistant** that integrates and cooperates with existing IDE AI systems (GitHub Copilot ecosystem). The main goal is augmentation, not replacement — CodexA functions as an intelligent context provider, semantic analyzer, and safe suggestion engine.

#### Agent Cooperation Protocol
- `RequestKind` enum: 10 request types (semantic_search, explain_symbol, explain_file, get_context, get_dependencies, get_call_graph, summarize_repo, find_references, validate_code, list_capabilities)
- `AgentRequest` / `AgentResponse`: model-neutral JSON request/response dataclasses with serialization roundtrip
- `BridgeCapabilities`: self-describing manifest for external tool discovery

#### Context Injection API
- `ContextProvider`: structured context generation for external AI pipelines
- `context_for_query()`: semantic search results ready for LLM prompt injection
- `context_for_symbol()`: rich symbol context with explanations, call graph, dependencies
- `context_for_file()`: file-level symbols, explanations, and dependency map
- `context_for_repo()`: repository-wide summary for project onboarding
- `validate_code()`, `get_dependencies()`, `get_call_graph()`, `find_references()`

#### Lightweight HTTP Bridge Server
- `BridgeServer`: stdlib `http.server` based — zero external dependencies
- `GET /` → capabilities manifest, `POST /request` → route AgentRequest, `GET /health` → status
- CORS headers for IDE extension consumption
- Background thread support: `start_background()` / `stop()`
- Direct `dispatch()` method for in-process usage (no HTTP round-trip)

#### VSCode Extension Interface
- `VSCodeBridge`: formatting layer adapting ContextProvider output to VS Code shapes
- `hover()`: markdown hover tooltips for symbols
- `diagnostics()`: SafetyValidator issues → VS Code Diagnostic format
- `completions()`: semantic search → CompletionItem list
- `code_actions()`: safety issues → quick-fix code actions
- `generate_extension_manifest()`: package.json fragment for companion extension

#### New CLI Commands
- `codexa serve`: start the bridge server with configurable host/port
- `codexa context <mode> [target]`: generate structured context (query/symbol/file/repo) for piping to external tools
- All commands support `--json` output mode

- **Tests for all new modules** | 13 CLI commands total

**Total: 453+ tests, all passing.**

### Phase 10: Multi-Repository Workspace Intelligence ✅
Introduced first-class multi-repository workspace support — manage, index, and search across multiple repos from a single workspace root.

#### Workspace Model
- `RepoEntry` dataclass: name, path, last_indexed timestamp, file_count, vector_count
- `WorkspaceManifest`: versioned JSON manifest at `.codexa/workspace.json`
- `Workspace` class: load/save persistence, add/remove/get repo management
- Per-repo vector indexes stored under `.codexa/repos/<name>/`
- Merged cross-repo search with score-sorted results

#### Workspace CLI
- `codexa workspace init`: initialize a workspace
- `codexa workspace add <name> <path>`: register a repository
- `codexa workspace remove <name>`: unregister a repository
- `codexa workspace list`: show all repos (Rich table or `--json`)
- `codexa workspace index`: index one (`--repo`) or all repos with `--force` option
- `codexa workspace search <query>`: cross-repo semantic search with `--repo` filtering
- All commands support `--path` for workspace root and `--json` output

- **52 new tests (516 → 568)** | 14 CLI commands total | Commit `01019db`

### Phase 11: Multi-Language Parsing Expansion ✅
Expanded tree-sitter parsing from 5 to **11 languages**, covering the most popular ecosystems.

#### New Language Grammars
- **TypeScript** (`.ts`): functions, arrow functions, classes, interfaces, enums, imports
- **TSX** (`.tsx`): full TypeScript + JSX support
- **C++** (`.cpp`, `.cc`, `.hpp`, `.h`): functions, classes, structs, enums, `#include` directives
- **C#** (`.cs`): methods, constructors, classes, interfaces, structs, enums, `using` directives
- **Ruby** (`.rb`): methods, singleton methods, classes, modules, `require`/`require_relative` imports
- **PHP** (`.php`): functions, methods, classes, interfaces, traits, enums, `use` declarations

#### Parser Improvements
- `_LANGUAGE_FACTORY` dict for grammars with non-standard factory functions (TypeScript, TSX, PHP)
- Enhanced `_find_name()`: handles C++ declarator nesting, Ruby `constant` nodes, PHP `name` nodes
- Ruby import filtering: only `require` and `require_relative` calls treated as imports (not `include`, `puts`, etc.)
- Semantic chunker automatically supports all new languages via `parse_file()` delegation

- **65 new tests (568 → 633)** | Commit `01019db`

### Phase 12: Platform Enhancements ✅
Cross-cutting improvements to plugins, reasoning, security, and IDE integration.

#### Plugin SDK Evolution
- `ON_STREAM` hook: intercept streaming LLM token chunks in real-time
- `CUSTOM_VALIDATION` hook: user-defined code validation rules via plugins
- 13 total hooks (up from 11)

#### Reasoning Engine Improvements
- **Context pruning**: `_prune_context()` trims snippets to stay within configurable `max_context_chars`
- **Priority scoring**: `_score_snippet()` combines semantic similarity with keyword-overlap bonus
- **Explainability metadata**: all result types (`AskResult`, `ReviewResult`, `RefactorResult`, `SuggestResult`) include an `explainability` dict tracking snippet counts, context size, and method used

#### Security Validator Enhancements
- Path traversal detection (`../../`)
- Hardcoded secrets (password, api_key, token, secret literals)
- XSS risks (`innerHTML`, `document.write`)
- Insecure cryptography (MD5, SHA-1)
- Insecure HTTP (non-localhost `http://` URLs)
- SSL verification bypass (`verify=False`)
- 17 total patterns (up from 8)

#### VSCode Streaming Context
- `StreamChunk` dataclass: kind (`token`, `context`, `done`, `error`), content, metadata
- `to_sse()`: Server-Sent Event formatting for HTTP streaming
- `build_streaming_context()`: builds a sequence of SSE-ready chunks from semantic search results

- **49 new tests (633 → 682)** | Commit `01019db`

**Total: 682 tests, all passing.**

### Phase 13: Open Source Readiness & Developer Experience ✅
Transformed CodexA into a community-ready open source project with auto-documentation, developer workflow tooling, and plugin scaffolding.

#### OSS Foundation
- **LICENSE** (MIT), **CONTRIBUTING.md**, **SECURITY.md**
- GitHub CI workflow (`.github/workflows/ci.yml`) — pytest on Python 3.11/3.12/3.13, ubuntu + windows matrix
- Issue templates (bug report, feature request) and PR template
- Enhanced `pyproject.toml`: classifiers, keywords, project URLs, readme

#### Auto-Documentation Generator (`semantic_code_intelligence/docs/`)
- `generate_cli_reference()`: walks Click command tree → Markdown with arguments, options tables, help text
- `generate_plugin_reference()`: documents all 13 hooks, base class API, metadata schema, lifecycle
- `generate_bridge_reference()`: endpoints, request kinds, AgentRequest/AgentResponse schemas
- `generate_tool_reference()`: tool registry with descriptions and usage examples
- `generate_all_docs()`: batch-generates all references into a `docs/` directory

#### New CLI Commands
- `codexa docs`: auto-generate Markdown documentation (`--section cli|plugins|bridge|tools|all`, `--json`)
- `codexa doctor`: environment health check — Python version, dependencies, project status (`--json`)
- `codexa plugin new <name>`: scaffold a new plugin from template (`--hooks`, `--author`, `--description`)
- `codexa plugin list`: discover and list installed plugins (`--json`)
- `codexa plugin info <name>`: show plugin details

#### CLI Ergonomics
- `--pipe` global flag for pipeline-friendly output (no Rich formatting)
- Version bumped to `0.13.0`
- 17 top-level CLI commands total

#### Sample Plugins
- `search_annotator.py`: POST_SEARCH hook example — annotates results with metadata
- `code_quality.py`: CUSTOM_VALIDATION hook example — flags TODOs, print statements

- **80 new tests (682 → 762)** | 17 CLI commands total

**Total: 762 tests, all passing.**

### Phase 14: Web Interface & Developer Accessibility Layer ✅
Added an optional lightweight web interface with REST API, browser UI, and Mermaid visualization — zero external dependencies.

#### REST API (`semantic_code_intelligence/web/api.py`)
- `APIHandler` wrapping `ContextProvider` with developer-friendly JSON endpoints
- GET: `/health`, `/api/search`, `/api/symbols`, `/api/deps`, `/api/callgraph`, `/api/summary`
- POST: `/api/ask` (natural-language questions), `/api/analyze` (validate/explain code)
- CORS headers on all responses, query-string helpers

#### Visualization (`semantic_code_intelligence/web/visualize.py`)
- `render_call_graph()`: caller → callee Mermaid flowchart from call edges
- `render_dependency_graph()`: file dependency flowchart with dedup
- `render_workspace_graph()`: hub-and-spoke workspace diagram
- `render_symbol_map()`: class diagram from symbols (classes, methods, standalone functions)
- Helpers: `_sanitize_id()`, `_sanitize_class_id()`, `_short_label()`

#### Web UI (`semantic_code_intelligence/web/ui.py`)
- Server-rendered HTML with inline CSS (dark GitHub-style theme) and vanilla JavaScript
- 4 pages: Search, Symbols, Workspace, Visualize
- No build step, no npm, no framework dependencies

#### Combined Server (`semantic_code_intelligence/web/server.py`)
- `WebServer` merging API + UI on a single port (default 8080)
- `start()`, `start_background()`, `stop()` lifecycle
- Uses Python stdlib `http.server` — zero external deps

#### New CLI Commands
- `codexa web [--host HOST] [--port PORT] [--path PATH]` — start web server
- `codexa viz KIND [--target T] [--output FILE] [--json] [--path PATH]` — generate Mermaid diagrams

#### Documentation
- `generate_web_reference()` added to auto-doc generator → `WEB.md`
- Version bumped to `0.14.0`
- 19 top-level CLI commands total

- **74 new tests (762 → 836)** | 19 CLI commands total

**Total: 836 tests, all passing.**

### Phase 15: CI/CD & Contribution Safety Pipeline ✅

| Feature | Status |
|---|---|
| Cyclomatic complexity analysis (14 decision patterns) | ✅ |
| Dead code detection (call graph + body heuristic) | ✅ |
| Duplicate logic detection (trigram Jaccard similarity) | ✅ |
| Aggregate quality report (`analyze_project()`) | ✅ |
| PR change summary (per-file symbol diff) | ✅ |
| PR impact analysis (blast-radius via call graph) | ✅ |
| Reviewer suggestion (domain-based heuristic) | ✅ |
| Risk scoring (0-100 composite with factors) | ✅ |
| GitHub Actions workflow templates (analysis, safety) | ✅ |
| Pre-commit config generation | ✅ |
| Pre-commit hook support (safety + plugin dispatch) | ✅ |
| `codexa quality` CLI command | ✅ |
| `codexa pr-summary` CLI command | ✅ |
| `codexa ci-gen` CLI command | ✅ |
| Auto-documentation: `CI.md` | ✅ |
| 79 new tests, backward compatible | ✅ |

**Total: 915 tests, all passing.**

---

### Phase 16: Advanced AI Workflows ✅

| Feature | Status |
|---|---|
| Multi-turn conversation memory with session persistence | ✅ |
| ConversationSession (uuid-based, serializable, turn-limited) | ✅ |
| SessionStore (file-backed `.codexa/sessions/`, path-safe) | ✅ |
| Autonomous multi-step code investigation chains | ✅ |
| InvestigationChain (LLM planner loop, search/analyze/deps) | ✅ |
| Cross-repo refactoring suggestions (trigram Jaccard) | ✅ |
| LLM-powered refactoring advice generation | ✅ |
| Streaming LLM responses (Ollama, OpenAI, Mock, fallback) | ✅ |
| Real-time plugin hooks (ON_STREAM dispatch) | ✅ |
| StreamEvent with SSE serialization | ✅ |
| `codexa chat` CLI command (session resume, list, max-turns) | ✅ |
| `codexa investigate` CLI command (step-by-step display) | ✅ |
| `codexa cross-refactor` CLI command (threshold, suggestions) | ✅ |
| Auto-documentation: `AI_WORKFLOWS.md` | ✅ |
| 64 new tests, backward compatible | ✅ |

**Total: 979 tests, all passing.**

---

### Phase 25: VS Code Extension v0.2.0 — Full IDE Integration ✅
Major rewrite of the VS Code extension from basic 4-command wrapper to a rich multi-panel IDE integration.

| Feature | Status |
|---|---|
| **Bug fix**: `--pipe` global flag added to all CLI invocations (was missing, causing empty/corrupt output) | ✅ |
| 4 sidebar webview panels (Search, Symbols & Graphs, Quality, Tools) | ✅ |
| Multi-mode search panel (semantic/keyword/hybrid/regex) with top-K selector | ✅ |
| Symbol explorer: explain symbol, call graph, file dependencies — all inline | ✅ |
| Quality dashboard: one-click quality analysis, metrics grid, risk hotspots | ✅ |
| Tools panel: Doctor, Re-Index, Models, Tool List, run any of the 8 agent tools with custom args | ✅ |
| 8 commands (was 4): +quality, +explainSymbol, +doctor, +index | ✅ |
| 3 keybindings: Ctrl+Shift+F5 (search), Ctrl+Shift+E (explain), Ctrl+Shift+Q (quality) | ✅ |
| Editor context menu: right-click → Explain Symbol / Show Call Graph | ✅ |
| CodeLens provider: inline "Explain" links on Python def/class definitions | ✅ |
| Status bar item: clickable CodexA icon with live status updates | ✅ |
| Click-to-open: all result cards navigate to file:line in the editor | ✅ |
| Output channel: all CLI invocations logged to "CodexA" output panel | ✅ |
| Extension version bumped to 0.2.0 | ✅ |
| Test updated (4 → 8 commands assertion) | ✅ |

**2556 tests, all passing** | Commit `e11a488`

---

### Phase 26: Priority Feature Implementation (P1–P5) ✅

| Feature | Status |
|---|---|
| BM25 keyword search with configurable k1/b parameters | ✅ |
| Regex search with case-sensitivity control | ✅ |
| Hybrid search with Reciprocal Rank Fusion (RRF) | ✅ |
| Full-section expansion via symbol registry | ✅ |
| Auto-index on first search | ✅ |
| Chunk-level content hashing (SHA-256) for incremental indexing | ✅ |
| Model registry with 5 curated embedding models | ✅ |
| ONNX runtime backend for embeddings | ✅ |
| Parallel indexing with ThreadPoolExecutor | ✅ |
| Interactive TUI with /mode, /view, /quit commands | ✅ |
| MCP server (JSON-RPC over stdio, 8 tools) | ✅ |
| `.codexaignore` support | ✅ |
| AST-based call graphs via tree-sitter | ✅ |
| Cross-repo search modes (semantic/keyword/regex/hybrid) | ✅ |
| Streaming responses for chat and investigate | ✅ |
| 34 CLI commands | ✅ |

**2413 tests, all passing**

---

### Phase 27: Power Features (P1–P6) ✅

| Feature | Status |
|---|---|
| Rich Textual split-pane TUI with mode cycling and keyboard bindings | ✅ |
| Graceful fallback REPL when Textual not installed | ✅ |
| Grep flag parity (--context-lines, --files-only, --files-without-match, --line-numbers, --jsonl) | ✅ |
| VS Code extension scaffold with 4 commands and sidebar search panel | ✅ |
| Single-binary distribution via PyInstaller | ✅ |
| IVF index support for large repos (>50k vectors) | ✅ |
| `codexa models` CLI (list, info, download, switch) | ✅ |
| 35 CLI commands | ✅ |

**2556 tests, all passing**

---

### Phase 28: UI/UX Polish Across All Interfaces ✅

| Feature | Status |
|---|---|
| **VS Code Extension**: Find References in SymbolsViewProvider | ✅ |
| **VS Code Extension**: ToolsViewProvider rewrite — dynamic parameter inputs from SCHEMAS | ✅ |
| **VS Code Extension**: Client-side validation, `--json` flag fix, rich result rendering | ✅ |
| **VS Code Extension**: 6 quick action buttons, spinners, animations | ✅ |
| **VS Code Extension**: Enhanced SHARED_CSS for consistent styling | ✅ |
| **Web UI**: 3 new pages (Tools, Quality, Ask) | ✅ |
| **Web UI**: 4 new API endpoints (/api/quality, /api/metrics, /api/hotspots, /api/tools/run) | ✅ |
| **CLI**: Global error handler in main.py | ✅ |
| **CLI**: Rich tables in tool_cmd.py, try/except in metrics/impact/hotspots/ask commands | ✅ |
| **CLI**: print_separator() and print_header() utilities | ✅ |
| **TUI**: Improved Textual CSS, Ctrl+K/J for top-k adjustment | ✅ |
| **TUI**: Rich tables and syntax highlighting in fallback REPL | ✅ |
| **TUI**: /help, /topk, /explain commands | ✅ |
| 36 CLI commands | ✅ |

**2595 tests, all passing**

---

## Upcoming Phases

### Phase 31: Remote / Cloud Mode
Package CodexA as a Docker container with a REST API so teams can share one index server. Add auth, rate limiting, team dashboards.

### Phase 32: CI/CD Deep Integration
GitHub Actions / GitLab CI plugin that runs `codexa quality` on PRs, blocks merges on regressions, and posts inline review comments.

### Phase 33: RAG Pipeline
Connect the vector store to LLMs for retrieval-augmented code generation — "write a function like X but for Y" with real codebase context.

---

### Phase 30: Competitive Feature Parity & Distribution ✅

| Feature | Status |
|---|---|
| **Watch-mode indexing**: `codexa index --watch` with NativeFileWatcher + incremental re-embedding | ✅ |
| **Full grep compatibility**: `-A`/`-B`/`-C` context lines, `-w` word, `-v` invert, `-c` count, `--hidden` | ✅ |
| **`codexa languages` command**: Rich table listing all 11 supported languages with grammar status | ✅ |
| **Profiling**: `codexa benchmark --profile` with cProfile hotspot analysis | ✅ |
| **MCP new tools**: `get_file_context` (full-section retrieval), `list_languages` | ✅ |
| **MCP-over-SSE**: `codexa serve --mcp` exposes MCP tools over HTTP+SSE | ✅ |
| **Dockerfile**: production-ready multi-stage image with ripgrep and pre-loaded model | ✅ |
| **Homebrew formula**: `Formula/codexa.rb` for macOS installation | ✅ |
| **PyPI ready**: version 0.30.0, `python -m build` compatible | ✅ |
| 40 CLI commands | ✅ |

---
### Evolution Cycle 1 ✔️
First run of the self-improving development loop (`codexa evolve`).

- Rich `markup=True` → `markup=False` on RichHandler to fix CI crash on Python 3.11/Windows ✔️
- `__test__ = False` on TestResult/TestRunner to suppress PytestCollectionWarning ✔️
- Click `__version__` deprecation replaced with `importlib.metadata.version()` ✔️
- Warnings reduced from 15 → 3 (remaining 3 are SWIG/frozen-importlib internals) ✔️
- 18 public-method docstrings added across evolution + tools/protocol packages ✔️
- Engine `run()` refactored: extracted `_run_iteration()` with per-iteration error isolation ✔️
- Evolution history recorded to `.codexa/evolution_history.json` ✔️

**2320 tests, all passing, 3 warnings** | Commits `4d7b109`, `31d41a3`

---
### Evolution Cycle 2 ✔️
Documentation sweep — 42 docstrings added across 5 core modules.

- ci/metrics.py: 11 docstrings (FileMetrics, ProjectMetrics, QualitySnapshot, etc.) ✔️
- workspace/__init__.py: 10 docstrings (RepoEntry, WorkspaceManifest, Workspace) ✔️
- bridge/protocol.py: 8 docstrings (AgentRequest, AgentResponse, BridgeCapabilities) ✔️
- context/memory.py: 7 docstrings (MemoryEntry, ReasoningStep, SessionMemory, WorkspaceMemory) ✔️
- context/engine.py: 6 docstrings (ContextWindow, CallEdge, CallGraph, DependencyMap) ✔️
- README.md & ROADMAP.md updated with correct badges and stats ✔️

**2320 tests, all passing** | Commit `8576ac5`

---
### Evolution Cycle 3 ✔️
Three targeted improvements: debugging UX, observability, and documentation.

- `__repr__` added to 5 non-dataclass classes (CallGraph, DependencyMap, SessionMemory, WorkspaceMemory, QueryHistory) ✔️
- 5 silent `except Exception: pass` replaced with `logger.debug()` in CI modules (hooks, hotspots, pr) ✔️
- 17 docstrings added across daemon/watcher.py, llm/conversation.py, analysis/ai_features.py ✔️
- Missing docstrings reduced from 109 → 92 across 9 files ✔️

**2320 tests, all passing** | Commit `a1f3c98`

---
### Phase 24: Self-Improving Development Loop ✅
- Evolution engine orchestrating analyse → task → patch → test → commit/revert loop ✅
- Budget guard enforcing token, iteration, and wall-clock time limits ✅
- Pytest-based test runner with structured result parsing ✅
- Git commit manager (diff, stage, commit, revert, stash) ✅
- Priority-based task selector (fix tests → type hints → error handling → dedup → optimise) ✅
- Minimal context builder with token-budget-aware prompt assembly ✅
- Patch generator with LLM diff generation, safety validation, git apply ✅
- `codexa evolve` CLI command with --iterations, --budget, --timeout flags ✅
- Evolution history persisted to .codexa/evolution_history.json ✅
- Phase 24 test suite with full coverage ✅

### Phase 23: Persistent Intelligence Index ✅
- Index manifest with schema versioning, embedding model tracking, timestamps ✅
- Symbol registry with multi-criteria find, substring search, file-level removal ✅
- Index statistics with per-language coverage, staleness, health metrics ✅
- Query history with FIFO eviction, popular queries/files, search analytics ✅
- Indexing service integration (manifest, registry, stats auto-populated) ✅
- Search service integration (query history auto-recorded) ✅
- Phase 23 test suite with full coverage ✅

### Phase 22: LLM Caching + Rate Limiting ✅
- Disk-backed LLM response cache with TTL and max-entry eviction ✅
- Sliding-window rate limiter (RPM + TPM) with blocking/non-blocking modes ✅
- CachedProvider transparent wrapper for any LLMProvider ✅
- LLMConfig extended with cache_enabled, cache_ttl_hours, cache_max_entries, rate_limit_rpm, rate_limit_tpm ✅
- CLI commands auto-wrap providers with caching + rate limiting ✅
- Phase 22 test suite with full coverage ✅

### Phase 21: Mypy Strict Typing & Coverage Gate ✅
- Mypy strict configuration in pyproject.toml ✅
- All 49 strict errors fixed across 26 source files ✅
- Pytest coverage gate (fail_under = 70%) ✅
- 79%+ coverage measured, gate passing ✅
- TYPE_CHECKING guards for clean lazy imports ✅
- Phase 21 test suite with regression guards ✅

### Phase 20: Deep Coverage & Copilot Integration ✅
- GitHub Copilot system prompt and integration guide ✅
- `.github/copilot-instructions.md` with full tool instructions ✅
- 824 new tests across 3 test files (Phase 20a/20b/20c) ✅
- Full coverage of all 22 subpackages ✅
- Context engine, memory, visualization, AI features, services ✅
- 2028 total tests, all passing ✅

### Phase 19: AI Agent Tooling Protocol ✅
- Tool Invocation Protocol (ToolInvocation, ToolExecutionResult, ToolError dataclasses) ✅
- Tool Execution Engine (ToolExecutor with validation, routing, timing) ✅
- Extended capability manifest (tools field in BridgeCapabilities) ✅
- Agent-friendly streaming (SSE /tools/stream endpoint) ✅
- CLI tool mode: `codexa tool run|list|schema` ✅
- AI safety guardrails (deterministic, no code execution, schema validation) ✅
- Plugin integration (REGISTER_TOOL, PRE_TOOL_INVOKE, POST_TOOL_INVOKE hooks) ✅
- AI_TOOL_PROTOCOL.md auto-generated documentation ✅
- 70+ new tests ✅

### Phase 17: Code Quality Metrics & Trends ✅
- Maintainability index and trend tracking ✅
- Historical metric snapshots and trend visualization ✅
- Configurable quality thresholds and policies ✅
- Quality gate enforcement in CI pipelines ✅

### Phase 18: Developer Workflow Intelligence ✅
- Hotspot detection engine (complexity, duplication, fan-in/out, churn) ✅
- Impact analysis engine (blast radius via call graph + deps BFS) ✅
- Symbol trace tool (upstream callers, downstream callees, cross-file) ✅
- 3 new CLI commands: `hotspots`, `impact`, `trace` ✅
- Pipeline-oriented output (--json, --pipe) for all commands ✅
- 6 new plugin hooks (19 total) ✅
- WORKFLOW_INTELLIGENCE.md auto-generated documentation ✅
- 60+ new tests ✅

### Phase 19: AI Agent Tooling Protocol ✅
- Tool Invocation Protocol (ToolInvocation, ToolExecutionResult, ToolError dataclasses) ✅
- Tool Execution Engine (ToolExecutor with validation, routing, timing) ✅
- Extended capability manifest (tools field in BridgeCapabilities) ✅
- Agent-friendly streaming (SSE /tools/stream endpoint) ✅
- CLI tool mode: `codexa tool run|list|schema` ✅
- AI safety guardrails (deterministic, no code execution, schema validation) ✅
- Plugin integration (REGISTER_TOOL, PRE_TOOL_INVOKE, POST_TOOL_INVOKE hooks) ✅
- AI_TOOL_PROTOCOL.md auto-generated documentation ✅
- 70+ new tests ✅

---

## Architecture

```
codexa CLI (Click) — 36 commands
  ├── init / index / search / explain / summary / watch / deps
  ├── ask / review / refactor / suggest
  ├── serve / context
  ├── workspace (init · add · remove · list · index · search)
  ├── docs / doctor
  ├── plugin (new · list · info)
  ├── web / viz
  ├── quality / pr-summary / ci-gen
  ├── chat / investigate / cross-refactor
  ├── metrics / gate
  ├── hotspots / impact / trace
  ├── tool (list · run · schema)
  ├── evolve
  │
  ├── Indexing Pipeline
  │     Scanner → Chunker → Embeddings (sentence-transformers) → FAISS VectorStore
  │     └── HashStore (incremental)
  │
  ├── Search Pipeline
  │     Query → Embedding → FAISS similarity → Rich / JSON formatter
  │
  ├── Parsing Engine (tree-sitter) — 11 languages
  │     Python · JavaScript · TypeScript · TSX · Java · Go · Rust
  │     C++ · C# · Ruby · PHP
  │     └── Symbols: functions, classes, methods, imports, parameters, decorators
  │
  ├── Context Engine
  │     ContextBuilder → ContextWindow
  │     CallGraph (reference edges)
  │     DependencyMap (import tracking)
  │     SessionMemory / WorkspaceMemory (cross-session caching)
  │
  ├── Multi-Repo Workspace
  │     Workspace → RepoEntry · WorkspaceManifest
  │     Per-repo indexing (.codexa/repos/<name>/)
  │     Merged cross-repo search
  │
  ├── AI Features
  │     RepoSummary · generate_ai_context() · explain_symbol() · explain_file()
  │
  ├── LLM Integration
  │     LLMProvider (OpenAI · Ollama · Mock)
  │     ReasoningEngine (ask · review · refactor · suggest)
  │     ConversationSession · SessionStore (multi-turn persistence)
  │     InvestigationChain (autonomous multi-step reasoning)
  │     stream_chat (Ollama/OpenAI/Mock with plugin hooks)
  │     analyze_cross_repo (cross-repo refactoring)
  │     Context pruning · priority scoring · explainability
  │     SafetyValidator (17 patterns)
  │
  ├── Bridge / IDE Integration
  │     BridgeServer (HTTP) · ContextProvider · VSCodeBridge
  │     ToolExecutor (structured tool protocol) · ToolInvocation / ToolExecutionResult
  │     StreamChunk (SSE streaming) · Extension manifest
  │
  ├── Auto-Documentation Engine
  │     CLI ref · Plugin ref · Bridge ref · Tool ref · Web ref · AI Tool Protocol ref → Markdown
  │
  ├── Web Interface (optional)
  │     WebServer (stdlib http.server) · APIHandler · UIHandler
  │     REST API (search, symbols, deps, callgraph, summary, ask, analyze)
  │     Mermaid Visualization (call graph, deps, workspace, symbol map)
  │
  │
  ├── VS Code Extension (TypeScript)
  │     4 sidebar panels (Search, Symbols & Graphs, Quality, Tools)
  │     8 commands · 3 keybindings · CodeLens · context menus
  │     Status bar · output channel · click-to-open navigation
  │
  └── Plugin SDK
        PluginBase · PluginHook (22 hooks) · PluginManager
        Plugin scaffold · Sample plugins · Discovery
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| CLI | Click 8.x |
| Config | Pydantic v2 |
| Logging / Output | Rich |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector Search | FAISS (IndexFlatIP) |
| Code Parsing | tree-sitter 0.25+ (11 language grammars) |
| Testing | pytest + pytest-cov (2556 tests) |
| Python | 3.12+ |
