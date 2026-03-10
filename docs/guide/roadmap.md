# Roadmap

Planned improvements for CodexA, organized by priority.

## Recently Completed (v0.30.0)

- **Watch-mode indexing**: `codexa index --watch` — live re-indexing with NativeFileWatcher + incremental indexing
- **`codexa languages` command**: Rich table of all 11 supported tree-sitter languages with extensions, grammar status, and `--check` verification
- **Full grep compatibility**: `-A/-B/-C` context lines, `-w` word match, `-v` invert, `-c` count, `--hidden` — in both ripgrep and Python backends
- **Benchmark profiling**: `codexa benchmark --profile` with cProfile integration — top 20 hotspots by cumulative time
- **MCP-over-SSE**: `codexa serve --mcp` — MCP tools over HTTP with Server-Sent Events via Starlette/uvicorn
- **13 MCP tools**: Added `get_file_context` (surrounding code retrieval) and `list_languages` (grammar listing)
- **Packaging**: Production Dockerfile, Homebrew formula, PyPI-ready with `python -m build`
- **39 CLI commands** (up from 38)

### Previously Completed (v0.29.0)

- O(1) vector removal, true incremental indexing, BM25 persistence
- Native file watcher (Rust-backed `watchfiles`), raw filesystem grep, performance benchmarking
- Enhanced init (`--index`, `--vscode`), 11 AI tools (quality, duplicates, grep)

---

## Upcoming Improvements

### Phase 31 — RAG Pipeline for LLM Commands

Replace the current "dump context → prompt" approach with a proper Retrieval-Augmented Generation pipeline:

- Semantic retrieval with re-ranking (cross-encoder)
- Token-aware context assembly with budget allocation
- Source citation in responses (file + line references)
- Configurable retrieval strategies (dense, sparse, hybrid)
- Chunk-level relevance scoring before LLM submission

### Phase 32 — Cross-Language Intelligence

Unified code intelligence across language boundaries:

- Cross-language symbol resolution (e.g., Python calling Rust via FFI)
- Polyglot dependency graphs linking imports across languages
- Language-aware search boosting (prefer results in the query's context language)
- Universal call graph spanning multiple languages in a workspace

### Phase 33 — Team & Cloud Mode

Optional team collaboration features (privacy-first, opt-in):

- Shared search indices with team-scoped access control
- Remote index hosting for large monorepos (gRPC or HTTP)
- Index sharding and distributed search across machines
- Audit logging for compliance-sensitive environments

### Phase 34 — CI/CD Deep Integration

First-class CI pipeline integration beyond quality gates:

- PR diff-aware indexing — only re-index changed files in CI
- Automated PR review comments via GitHub Actions / GitLab CI
- Quality trend dashboards exported as CI artifacts
- Breaking-change detection based on call graph + reference analysis
- Configurable CI profiles (fast/thorough/security-only)

### Phase 35 — Advanced Embedding & Search

Next-generation search infrastructure:

- Fine-tuned code embedding models (CodeBERT, StarEncoder)
- GPU-accelerated FAISS with IVF-PQ indices for million-file repos
- Field-scoped search filters (`--lang`, `--symbol-type`, `--file`)
- Configurable RRF weights for hybrid search tuning
- Re-ranking with cross-encoders for precision-critical queries

### Phase 36 — Async Web & Real-Time Streaming

Migrate the web server to a modern async framework:

- WebSocket streaming for live search results
- Non-blocking request handling with connection pooling
- Server-sent events for long-running operations (indexing progress)
- Real-time collaboration widgets in the web UI

### Phase 37 — Plugin Marketplace & Sandboxing

Mature the plugin ecosystem:

- Plugin sandboxing with resource limits and restricted filesystem access
- Community plugin registry with versioning and discovery
- Plugin dependency resolution and conflict detection
- Visual plugin configuration in the web UI

### Phase 38 — Precise Token Management

Replace rough token estimation with model-specific counting:

- `tiktoken` for OpenAI models, model-specific tokenizers for Ollama
- Accurate context window budgeting with overflow protection
- Token usage reporting and cost estimation per query
- Smart context truncation preserving semantic boundaries

### Phase 39 — LSP 2.0 & Editor Deep Integration

Enhanced editor integration beyond current LSP:

- Inline code explanations as CodeLens / inlay hints
- Semantic go-to-definition across indexed repos
- Live quality annotations in the editor gutter
- Multi-root workspace support with cross-repo navigation

## Low Priority (Future)

### Fine-Tuned Embedding Models

- Domain-specific vocabulary handling
- Language-aware fine-tuning
- Benchmark against general-purpose models

### Distributed Indexing

- Sharded FAISS indices across machines
- Distributed embedding computation
- Merged search results with federation

## Contributing

Interested in working on any of these? Check the [GitHub issues](https://github.com/M9nx/CodexA/issues) for related discussions.
