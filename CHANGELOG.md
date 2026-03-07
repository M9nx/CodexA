# Changelog

All notable changes to CodexA are documented in this file.

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
