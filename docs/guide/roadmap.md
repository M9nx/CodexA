# Roadmap

Planned improvements for CodexA, organized by priority.

## Recently Completed (v0.29.0)

- **O(1) vector removal**: File-level index for instant vector lookup and batch FAISS reconstruction
- **True incremental indexing**: Content-hash caching — unchanged chunks skip embedding entirely
- **BM25 persistence**: BM25 index cached to disk with 3-tier loading (memory/disk/build)
- **Native file watcher**: Rust-backed `watchfiles` with OS-native APIs (inotify/FSEvents/ReadDirectoryChanges)
- **Raw filesystem grep**: `codex grep` command with ripgrep backend, no index required
- **Performance benchmarking**: `codex benchmark` command measuring indexing, search, and memory
- **Enhanced init**: `codex init --index --vscode` for one-command setup
- **11 AI tools**: Added `get_quality_score`, `find_duplicates`, `grep_files` to tools and MCP

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

## Low Priority

### Fine-Tuned Embedding Models

Train custom embedding models on codebases:

- Domain-specific vocabulary handling
- Language-aware fine-tuning
- Benchmark against general-purpose models

### Distributed Indexing

Support indexing across multiple machines:

- Sharded FAISS indices
- Distributed embedding computation
- Merged search results

## Contributing

Interested in working on any of these? Check the [GitHub issues](https://github.com/M9nx/CodexA/issues) for related discussions.
