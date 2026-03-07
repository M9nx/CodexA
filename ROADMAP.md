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

---

## Upcoming Phases

### Phase 7: Enhanced CLI
- Add `codex explain <symbol>` command (uses `explain_symbol`)
- Add `codex summary` command (uses `summarize_repository`)
- Add `codex context <symbol>` command (uses `ContextBuilder`)
- Add `codex graph` command (visualize call graph in terminal)
- Wire all Phase 4–6 features into the existing CLI

### Phase 8: Smart Indexing
- Replace line-boundary chunker with tree-sitter–aware chunking
- Split on function/class boundaries instead of raw line counts
- Produce higher-quality embeddings aligned to semantic units
- Hybrid mode: fall back to line-based chunking for unsupported languages

### Phase 9: Watch Mode
- File-system watcher (watchdog) for live re-indexing
- Detect file changes and re-index only modified files via hash store
- Background daemon mode with `codex watch`
- Configurable debounce and ignore patterns

### Phase 10: LLM Integration
- Connect to OpenAI, Ollama, or other LLM APIs
- Use `generate_ai_context()` as prompt context for code Q&A
- `codex ask <question>` — natural language questions about the codebase
- `codex review` — AI-powered code review suggestions
- `codex refactor <symbol>` — AI-assisted refactoring proposals

### Phase 11: Multi-Repo Support
- Index and search across multiple repositories
- Per-repo configuration with merged search results
- Cross-repo symbol resolution and dependency tracking
- Workspace-level summary aggregation

### Phase 12: Additional Languages
- TypeScript (`.ts`, `.tsx`)
- C++ (`.cpp`, `.hpp`, `.cc`, `.h`)
- C# (`.cs`)
- Ruby (`.rb`)
- PHP (`.php`)

### Phase 13: Web UI
- FastAPI/Flask REST API server
- Browser-based search interface
- Interactive call graph visualization (Mermaid / D3.js)
- Code exploration with syntax highlighting and symbol navigation

### Phase 14: Plugin System
- Plugin architecture for custom analyzers
- Custom formatter plugins (Markdown, HTML, SARIF)
- Third-party integration hooks (Slack, Discord, CI/CD)
- Plugin discovery and configuration via `codex.plugins` config

### Phase 15: CI/CD Integration
- GitHub Actions workflow for automated analysis on PR
- Pre-commit hooks for local analysis
- Generate changed-symbol reports on each commit
- AI-powered review context injected into PR comments

### Phase 16: Code Quality Metrics
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
