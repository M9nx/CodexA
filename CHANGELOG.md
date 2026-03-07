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

### Phase 7: Platform Evolution
- **AST-Aware Semantic Chunking**: `SemanticChunk`, `semantic_chunk_code()`, `semantic_chunk_file()` — splits on function/class/method boundaries via tree-sitter, falls back to line-based chunking
- **Enhanced Embedding Pipeline**: `preprocess_code_for_embedding()`, `generate_semantic_embeddings()`, `generate_query_embedding()` — semantic label prepending and format normalization
- **Background Intelligence**: `FileWatcher` (polling-based change detection), `AsyncIndexer` (queue-based background indexing), `IndexingDaemon` (combined watcher + indexer)
- **AI Tool Interaction Layer**: `ToolRegistry` with 8 tools (`semantic_search`, `explain_symbol`, `explain_file`, `summarize_repo`, `find_references`, `get_dependencies`, `get_call_graph`, `get_context`), `ToolResult` protocol, `TOOL_DEFINITIONS` schema
- **Expanded CLI**: `codex explain`, `codex summary`, `codex deps`, `codex watch` commands (all with `--json` support)
- **Plugin Architecture SDK**: `PluginBase`, `PluginHook` (9 hook points), `PluginManager` with discovery, activation, and chained hook dispatch
- **Scalability**: `BatchProcessor`, `MemoryAwareEmbedder`, `ParallelScanner` for memory-safe batch processing and concurrent I/O
- 119 new tests (391 cumulative)
