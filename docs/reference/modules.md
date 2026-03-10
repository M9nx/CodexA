# Module Reference

Complete reference for all 26 packages in `semantic_code_intelligence/`.

## analysis

Code explanation and repository summarization.

| Symbol | Type | Description |
|--------|------|-------------|
| `LanguageStats` | class | Per-language statistics (files, lines, symbols) |
| `RepoSummary` | class | Structured repository summary |
| `CodeExplanation` | class | Explanation result for a symbol or file |
| `summarize_repo()` | function | Generate full repository summary |
| `explain_symbol()` | function | Produce structural explanation of a symbol |
| `explain_file()` | function | Explain all symbols in a file |
| `detect_languages()` | function | Detect languages in the codebase |

## bridge

HTTP bridge server for IDE extensions and AI agents.

| Symbol | Type | Description |
|--------|------|-------------|
| `BridgeServer` | class | HTTP server implementing the bridge protocol |
| `AgentRequest` | class | Incoming bridge request with kind and payload |
| `AgentResponse` | class | Response with correlation ID and result |
| `ContextProvider` | class | Provides context to bridge consumers |
| `VSCodeBridge` | class | VS Code-specific bridge adapter |
| `RequestRouter` | class | Routes requests by kind |
| `ResponseFormatter` | class | Formats results for agent consumption |
| `start_bridge()` | function | Start the bridge server |
| `handle_request()` | function | Process a single bridge request |

## ci

Quality analysis, metrics, hotspots, impact analysis, and CI gates.

| Symbol | Type | Description |
|--------|------|-------------|
| `QualityAnalyzer` | class | Runs full quality analysis pipeline |
| `QualitySnapshot` | class | Point-in-time quality metrics |
| `QualityTrend` | class | Trend analysis over snapshots |
| `QualityGate` | class | Configurable pass/fail gates |
| `Hotspot` | class | High-risk code location |
| `HotspotAnalyzer` | class | Detects hotspots via complexity, churn, fan-in |
| `ImpactReport` | class | Blast radius analysis result |
| `ImpactAnalyzer` | class | Predicts change impact via call graph BFS |
| `MetricsCollector` | class | Collects code metrics |
| `BanditIssue` | class | Security issue found by Bandit |
| `run_quality_analysis()` | function | Run full quality pipeline |
| `run_bandit_scan()` | function | Run Bandit security scan |
| `calculate_maintainability_index()` | function | Compute maintainability score |
| `detect_hotspots()` | function | Find high-risk code areas |
| `analyze_impact()` | function | Compute blast radius of changes |

## cli

39 Click commands organized by capability. All commands support `--json` for machine-readable output.

See [CLI Reference](cli) for the complete command documentation.

## config

Pydantic configuration models loaded from `.codexa/config.json`.

| Symbol | Type | Description |
|--------|------|-------------|
| `AppConfig` | class | Root configuration aggregating all sub-configs |
| `EmbeddingConfig` | class | Model name, chunk size, overlap settings |
| `SearchConfig` | class | top_k, similarity threshold, hybrid weights |
| `IndexConfig` | class | Incremental indexing, file extensions |
| `LLMConfig` | class | Provider, model, API key, temperature |
| `QualityConfig` | class | Quality gate thresholds |
| `load_config()` | function | Load config from `.codexa/config.json` |

## context

Context building for AI consumption — symbol resolution, call graphs, dependency maps.

| Symbol | Type | Description |
|--------|------|-------------|
| `ContextBuilder` | class | Builds rich context windows for AI tools |
| `ContextWindow` | class | Bounded token-aware context container |
| `CallGraph` | class | Function call graph (callers/callees) |
| `DependencyMap` | class | File-level dependency graph |
| `SessionMemory` | class | Multi-turn conversation memory with persistence |
| `SymbolResolver` | class | Resolves symbol names to definitions |
| `TokenCounter` | class | Estimates token count for context budgets |
| `ReferenceCollector` | class | Collects all references to a symbol |

## daemon

Background file watching and incremental indexing.

| Symbol | Type | Description |
|--------|------|-------------|
| `IndexingDaemon` | class | Long-running daemon for watch mode |
| `FileWatcher` | class | Filesystem event watcher |
| `AsyncIndexer` | class | Async incremental indexer |
| `DaemonConfig` | class | Daemon configuration |

## embeddings

Sentence-transformer model management and vector encoding.

| Symbol | Type | Description |
|--------|------|-------------|
| `ModelInfo` | class | Metadata about an embedding model |
| `load_model()` | function | Load a sentence-transformer model |
| `encode_text()` | function | Encode text to vector |
| `encode_batch()` | function | Batch encode multiple texts |
| `list_models()` | function | List available models |
| `download_model()` | function | Download a model by name |
| `switch_model()` | function | Switch active embedding model |
| `get_model_info()` | function | Get model metadata |

## evolution

Self-improving development loop with budget awareness.

| Symbol | Type | Description |
|--------|------|-------------|
| `EvolutionEngine` | class | Orchestrates the self-improvement loop |
| `BudgetGuard` | class | Enforces token/time/cost budgets |
| `TaskSelector` | class | Selects next improvement task |
| `PatchGenerator` | class | Generates code patches via LLM |
| `TestRunner` | class | Runs tests to validate patches |
| `EvolutionResult` | class | Result of an evolution cycle |
| `EvolutionTask` | class | A single improvement task |
| `EvolutionBudget` | class | Budget configuration |
| `evolve()` | function | Run one evolution cycle |

## indexing

File scanning, code chunking, and semantic chunk creation.

| Symbol | Type | Description |
|--------|------|-------------|
| `CodeChunk` | class | A chunk of source code with metadata |
| `ScannedFile` | class | A scanned source file |
| `SemanticChunk` | class | Chunk with embedding vector attached |
| `scan_directory()` | function | Scan a directory for source files |
| `chunk_file()` | function | Split a file into semantic chunks |
| `run_indexing()` | function | Full indexing pipeline |
| `incremental_index()` | function | Index only changed files |

## llm

LLM provider abstraction with caching, streaming, and investigation chains.

| Symbol | Type | Description |
|--------|------|-------------|
| `LLMProvider` | class | Abstract base for LLM providers |
| `OpenAIProvider` | class | OpenAI API provider |
| `OllamaProvider` | class | Ollama local inference provider |
| `MockProvider` | class | Mock provider for testing |
| `CachedProvider` | class | Caching wrapper around any provider |
| `LLMCache` | class | Disk-based LLM response cache |
| `InvestigationChain` | class | ReAct-style autonomous investigation |
| `StreamHandler` | class | Handles streaming LLM responses |
| `create_provider()` | function | Factory for LLM providers |

## lsp

Language Server Protocol implementation.

| Symbol | Type | Description |
|--------|------|-------------|
| `LSPServer` | class | LSP server for editor integration |
| `start_lsp()` | function | Start the LSP server |

## mcp

Model Context Protocol server using the official MCP SDK.

| Symbol | Type | Description |
|--------|------|-------------|
| `run_mcp_server()` | function | Start the MCP stdio server |
| `_create_server()` | function | Create and configure MCP server instance |
| `_dispatch_tool()` | function | Route tool calls to the executor |

## parsing

Tree-sitter AST parsing for 12 programming languages.

| Symbol | Type | Description |
|--------|------|-------------|
| `Symbol` | class | Extracted symbol (function, class, method) with location |
| `parse_file()` | function | Parse a file into an AST |
| `extract_symbols()` | function | Extract symbols from AST |
| `get_language()` | function | Get tree-sitter language for file extension |

**Supported languages:** Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, C, C++, C#, PHP, Swift

## plugins

Extensible plugin system with 22 hook points.

| Symbol | Type | Description |
|--------|------|-------------|
| `PluginManager` | class | Discovery, loading, lifecycle management |
| `PluginBase` | class | Abstract base class for plugins |
| `PluginHook` | enum | 22 hook point definitions |
| `PluginMetadata` | class | Plugin name, version, author, hooks |
| `PluginRegistry` | class | Registry of loaded plugins |
| `load_plugins()` | function | Discover and load plugins from directory |

## scalability

Performance optimizations for large codebases.

| Symbol | Type | Description |
|--------|------|-------------|
| `BatchProcessor` | class | Process items in configurable batches |
| `MemoryAwareEmbedder` | class | Embedder that respects memory limits |
| `ParallelScanner` | class | Multi-threaded file scanning |
| `StreamingIndexer` | class | Streaming indexer for large repos |

## search

FAISS vector search, BM25 keyword search, and hybrid RRF fusion.

| Symbol | Type | Description |
|--------|------|-------------|
| `HybridResult` | class | Combined search result with score |
| `BM25Index` | class | BM25 keyword index |
| `FaissSearcher` | class | FAISS vector similarity search |
| `hybrid_search()` | function | Combined vector + keyword search with RRF |
| `vector_search()` | function | Pure vector similarity search |
| `keyword_search()` | function | Pure BM25 keyword search |

## services

Service-layer abstractions for indexing and search results.

| Symbol | Type | Description |
|--------|------|-------------|
| `IndexingResult` | class | Result of an indexing operation |
| `SearchResult` | class | Normalized search result |

## storage

Persistent storage for vectors, symbols, and metadata.

| Symbol | Type | Description |
|--------|------|-------------|
| `VectorStore` | class | FAISS-backed vector storage |
| `SymbolRegistry` | class | Symbol definition and reference store |
| `IndexStats` | class | Index size, file count, chunk count |
| `QueryHistory` | class | Search query history |
| `ChunkStore` | class | Stores code chunks with metadata |
| `CacheManager` | class | Manages disk caches |

## tools

AI Agent Tool Protocol — structured tool invocation for LLM agents.

| Symbol | Type | Description |
|--------|------|-------------|
| `ToolExecutor` | class | Executes tool invocations |
| `ToolInvocation` | class | Typed tool call request |
| `ToolExecutionResult` | class | Typed tool call response |
| `ToolError` | class | Tool execution error |
| `ToolRegistry` | class | Registry of available tools |
| `ToolSchema` | class | JSON Schema for a tool |

## tui

Textual-based interactive terminal UI.

| Symbol | Type | Description |
|--------|------|-------------|
| `CodexaTUI` | class | Main TUI application |
| `start_tui()` | function | Launch the interactive terminal |

## utils

Logging and utility functions.

| Symbol | Type | Description |
|--------|------|-------------|
| `setup_logging()` | function | Configure rich logging |
| `get_logger()` | function | Get a named logger |

## web

Web UI and REST API server.

| Symbol | Type | Description |
|--------|------|-------------|
| `WebServer` | class | HTTP server combining API and UI |
| `APIHandler` | class | REST API request handler |
| `UIHandler` | class | Static file and UI handler |
| `start_web()` | function | Start the web server |

## workspace

Multi-repo workspace management.

| Symbol | Type | Description |
|--------|------|-------------|
| `Workspace` | class | Multi-repo workspace container |
| `WorkspaceManifest` | class | Workspace configuration manifest |
| `create_workspace()` | function | Create a new workspace |
