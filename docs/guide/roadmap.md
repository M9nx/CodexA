# Roadmap

Planned improvements for CodexA, organized by priority.

## Recently Completed (v0.4.5)

- **RAG Pipeline (Phase 31)**: Full Retrieval-Augmented Generation pipeline for LLM commands
  - 4-stage pipeline: Retrieve → Deduplicate → Re-rank → Assemble
  - Configurable strategies: `semantic`, `keyword`, `hybrid`, `multi`
  - Optional cross-encoder re-ranking (`ms-marco-MiniLM-L-6-v2`)
  - Token-aware context assembly with budget allocation (default 3000 tokens)
  - Source citations with `[N]` markers and file:line references
  - Three new config fields: `rag_budget_tokens`, `rag_strategy`, `rag_use_cross_encoder`

### v0.4.4

- **Model Profiles**: Three built-in profiles — `fast`, `balanced`, `precise` — each tuned for different hardware
- **`codexa init --profile`**: Choose your embedding model tier at init, or let CodexA auto-detect from available RAM
- **`codexa models profiles`**: View available profiles with RAM requirements and ⭐ recommendation
- **`codexa models benchmark`**: Benchmark all built-in models against your actual codebase
- **Download progress banner**: Friendly indicator with model size when downloading for the first time
- **RAM-aware defaults**: Auto-picks the best model for your machine

### v0.4.3

- **Bundled tree-sitter grammars**: All grammar packages included in core dependencies — parsing works out of the box
- **`exclude_files` config**: Glob-based file exclusions via `index.exclude_files` in `.codexa/config.json`
- **Reduced HuggingFace noise**: Prefers locally cached models, skips redundant network checks
- **MemoryError handling**: Actionable error messages when embedding model loading fails on low-RAM machines
- **Improved CLI guidance**: `codexa init` and `codexa index` show ML extra and RAM hints
- **Install tiers**: `pip install codexa` (lightweight) vs `pip install "codexa[ml]"` (full ML stack)

### v0.4.2

- Pinned `numpy < 2` to avoid ABI breakage with FAISS on some platforms

### v0.4.1

- ML libraries (`sentence-transformers`, `torch`, `faiss-cpu`) moved to `[ml]` extra
- Lightweight `pip install codexa` installs CLI + tree-sitter without ML overhead

### v0.4.0 — First Stable Public Release

- Package renamed `codexa-ai` → `codexa`
- 39 CLI commands, 13 AI agent tools, 22 plugin hooks
- Semantic search, multi-mode search, quality analysis, MCP server
- Docker image, Homebrew formula, VS Code extension

### Previously Completed (v0.30.0 / v0.29.0)

- Watch-mode indexing, `codexa languages` command, full grep compatibility
- MCP-over-SSE, 13 MCP tools, production Dockerfile, Homebrew formula
- O(1) vector removal, incremental indexing, BM25 persistence, native file watcher

---

## Upcoming Improvements

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
