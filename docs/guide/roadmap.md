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

> Phases redesigned after self-analysis with CodexA tools and competitive
> comparison with [ck](https://github.com/BeaconBay/ck) (Rust-based semantic
> search, v0.7.4). Priorities: close visible UX/performance gaps first, then
> double down on CodexA's unique AI-powered strengths.

### Phase 32 — Search UX & Output Modes

Close the biggest visible gaps in search ergonomics:

- `--scores` flag to display similarity scores with color highlighting
- `--full-section` flag to return complete function/class bodies, not just chunk snippets
- `--threshold` flag to filter results below a minimum similarity score
- JSONL streaming output mode (`--jsonl`) for piping into downstream tools
- `codexa search --inspect <file>` to visualize chunks, token counts, and embeddings for a file
- `.codexaignore` auto-generation from detected binary/vendored/generated files
- Smart binary detection to skip non-text files during indexing

### Phase 33 — Precise Token Management

Replace rough token estimation with model-specific counting (ck already ships exact tokenization):

- `tiktoken` for OpenAI models, HuggingFace `tokenizers` for local/Ollama models
- Accurate context window budgeting with overflow protection in RAG pipeline
- Token usage reporting and cost estimation per query
- Smart context truncation preserving semantic boundaries (function/class edges)
- `codexa search --tokens` to show token count per result

### Phase 34 — Performance & Smart Indexing

Content-aware incremental indexing to close the speed gap:

- Content-hash (blake3) per chunk — skip re-embedding unchanged code
- Parallel embedding with configurable worker count
- Batch FAISS insertion instead of one-by-one vector adds
- Memory-mapped FAISS indices for low-RAM machines
- `codexa index --diff` to index only git-changed files
- Indexing progress bar with ETA and throughput stats

### Phase 35 — Advanced Embedding & Model Selection

Multiple embedding models and smarter search infrastructure:

- Support BGE, mxbai-embed, nomic-embed, jina-code-v2 alongside current MiniLM
- Model switching at query time without full re-index (dual-index mode)
- GPU-accelerated FAISS with IVF-PQ indices for million-file repos
- Field-scoped search filters (`--lang`, `--symbol-type`, `--file`)
- Configurable RRF weights for hybrid search tuning
- `codexa models compare` to benchmark models on the user's actual codebase

### Phase 36 — CI/CD Deep Integration

First-class CI pipeline integration — a unique CodexA strength:

- PR diff-aware indexing — only re-index changed files in CI
- Automated PR review comments via GitHub Actions / GitLab CI
- Quality trend dashboards exported as CI artifacts (HTML + JSON)
- Breaking-change detection based on call graph + reference analysis
- Configurable CI profiles (`fast` / `thorough` / `security-only`)

### Phase 37 — VS Code Extension & Editor Integration

Marketplace-ready VS Code extension with deep editor features:

- Inline code explanations as CodeLens / inlay hints
- Semantic go-to-definition across indexed repos
- Live quality annotations in the editor gutter
- Multi-root workspace support with cross-repo navigation
- Extension marketplace publishing and auto-update

### Phase 38 — Async Web & Real-Time Streaming

Migrate the web server to a modern async framework:

- WebSocket streaming for live search results
- Non-blocking request handling with connection pooling
- Server-sent events for long-running operations (indexing progress)
- Real-time dashboard with quality trends and search analytics

### Phase 39 — Cross-Language Intelligence

Unified code intelligence across language boundaries:

- Cross-language symbol resolution (e.g., Python calling Rust via FFI)
- Polyglot dependency graphs linking imports across languages
- Language-aware search boosting (prefer results in the query's context language)
- Universal call graph spanning multiple languages in a workspace

## Low Priority (Future)

### Plugin Marketplace & Sandboxing

- Plugin sandboxing with resource limits and restricted filesystem access
- Community plugin registry with versioning and discovery
- Plugin dependency resolution and conflict detection
- Visual plugin configuration in the web UI

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
