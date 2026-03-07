# CodexA — Project Roadmap

## Completed Phases

### Phase 1: CLI Framework ✅
- Click-based CLI with `codex init`, `codex index`, `codex search` commands
- Pydantic v2 configuration models (`AppConfig`, `EmbeddingConfig`, `SearchConfig`, `IndexConfig`)
- Rich-powered logging with colored output and progress indicators
- Project scaffolding: `.codex/` directory, `config.json`, index storage
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
- `codex watch` CLI command with configurable poll interval

#### AI Tool Interaction Layer
- `ToolResult` structured response protocol for LLM agents
- `ToolRegistry` with 8 tools: `semantic_search`, `explain_symbol`, `explain_file`, `summarize_repo`, `find_references`, `get_dependencies`, `get_call_graph`, `get_context`
- `TOOL_DEFINITIONS` schema manifest for tool discovery
- Lazy ContextBuilder initialization, per-file and directory indexing

#### Expanded CLI Commands
- `codex explain <symbol>`: structural explanation of symbols or entire files
- `codex summary`: repository summary with language breakdown
- `codex deps [target]`: dependency/import map (single file or whole project)
- `codex watch`: background daemon for automatic re-indexing on file changes
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

---

## Upcoming Phases

### Phase 8: LLM Integration
- Connect to OpenAI, Ollama, or other LLM APIs
- Use `generate_ai_context()` as prompt context for code Q&A
- `codex ask <question>` — natural language questions about the codebase
- `codex review` — AI-powered code review suggestions
- `codex refactor <symbol>` — AI-assisted refactoring proposals

### Phase 9: Multi-Repo Support
- Index and search across multiple repositories
- Per-repo configuration with merged search results
- Cross-repo symbol resolution and dependency tracking
- Workspace-level summary aggregation

### Phase 10: Additional Languages
- TypeScript (`.ts`, `.tsx`)
- C++ (`.cpp`, `.hpp`, `.cc`, `.h`)
- C# (`.cs`)
- Ruby (`.rb`)
- PHP (`.php`)

### Phase 11: Web UI
- FastAPI/Flask REST API server
- Browser-based search interface
- Interactive call graph visualization (Mermaid / D3.js)
- Code exploration with syntax highlighting and symbol navigation

### Phase 12: CI/CD Integration
- GitHub Actions workflow for automated analysis on PR
- Pre-commit hooks for local analysis
- Generate changed-symbol reports on each commit
- AI-powered review context injected into PR comments

### Phase 13: Code Quality Metrics
- Cyclomatic complexity calculation per function
- Duplicate code detection across the codebase
- Dead code identification (unreferenced symbols)
- Maintainability index and trend tracking

---

## Architecture

```
codex CLI (Click)
  ├── init / index / search / explain / summary / context / graph
  │
  ├── Indexing Pipeline
  │     Scanner → Chunker → Embeddings (sentence-transformers) → FAISS VectorStore
  │     └── HashStore (incremental)
  │
  ├── Search Pipeline
  │     Query → Embedding → FAISS similarity → Rich / JSON formatter
  │
  ├── Parsing Engine (tree-sitter)
  │     Python · JavaScript · Java · Go · Rust
  │     └── Symbols: functions, classes, methods, imports, parameters, decorators
  │
  ├── Context Engine
  │     ContextBuilder → ContextWindow
  │     CallGraph (reference edges)
  │     DependencyMap (import tracking)
  │
  └── AI Features
        RepoSummary · generate_ai_context() · explain_symbol() · explain_file()
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| CLI | Click 8.x |
| Config | Pydantic v2 |
| Logging / Output | Rich |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector Search | FAISS (IndexFlatIP) |
| Code Parsing | tree-sitter 0.25+ |
| Testing | pytest + pytest-cov |
| Python | 3.12+ |
