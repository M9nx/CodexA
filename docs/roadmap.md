# Roadmap

Planned improvements for CodexA, organized by priority.

## High Priority

### RAG Pipeline for LLM Commands

Replace the current "dump context → prompt" approach with a proper Retrieval-Augmented Generation pipeline:

- Semantic retrieval with re-ranking
- Token-aware context assembly
- Source citation in responses
- Configurable retrieval strategies

### Async Web & WebSocket Streaming

Migrate the web server from synchronous `http.server` to an async framework:

- Real-time search result streaming via WebSocket
- Non-blocking request handling
- Server-sent events for long-running operations
- Connection pooling for multi-client scenarios

### Precise Token Counting

Replace rough `len(text) // 4` estimation with model-specific tokenizers:

- `tiktoken` for OpenAI models
- Model-specific tokenizers for Ollama models
- Accurate context window budgeting
- Token usage reporting

---

## Medium Priority

### Field-Scoped Search

Allow narrowing searches by metadata fields:

```bash
codex search "auth" --lang python --symbol-type class --file "src/**"
```

- Language, symbol type, file path filters
- Pre-filter before vector search for efficiency
- Composable filter expressions

### Configurable RRF Weights

Make the Reciprocal Rank Fusion weights tunable:

```json
{
  "search": {
    "rrf_k": 60,
    "vector_weight": 0.7,
    "keyword_weight": 0.3
  }
}
```

### Plugin Sandboxing

Isolate plugins to prevent interference:

- Resource limits (memory, CPU time)
- Restricted filesystem access
- Capability-based permissions
- Graceful error containment

### LLM Call Retry Logic

Add resilience for LLM provider calls:

- Exponential backoff with jitter
- Provider failover (OpenAI → Ollama)
- Request timeout configuration
- Rate limit awareness

---

## Low Priority

### Docker Image

Official Docker image for CI and deployment:

```dockerfile
FROM python:3.12-slim
RUN pip install codex-ai
ENTRYPOINT ["codex"]
```

### CLI Aliases

User-definable command shortcuts:

```json
{
  "aliases": {
    "s": "search",
    "q": "quality",
    "h": "hotspots"
  }
}
```

### YAML Configuration

Support YAML as an alternative to JSON configuration:

```yaml
embedding:
  model_name: all-MiniLM-L6-v2
  chunk_size: 512
search:
  top_k: 10
```

### Incremental Quality Cache

Cache quality analysis results per-file, invalidating only on file changes. Speeds up repeated `codex quality` runs on large codebases.

### TUI Export

Export TUI views and dashboards to HTML, PNG, or PDF for reports and documentation.

### Additional Language Grammars

Expand tree-sitter support beyond the current 12 languages:

- Kotlin, Scala, Dart, Lua, Elixir, Haskell, OCaml, Zig

---

## Completed (Recent)

- [x] **Radon integration** — AST-based cyclomatic complexity and maintainability index (v0.28.0)
- [x] **Bandit integration** — Security linting in quality pipeline (v0.28.0)
- [x] **Official MCP SDK** — Replaced custom JSON-RPC with official `mcp` package (v0.28.0)
- [x] **2595+ tests** — Comprehensive test coverage across all packages
- [x] **Plugin system** — 22 hook points with full lifecycle management
- [x] **Evolution engine** — Self-improving development loop with budget control
