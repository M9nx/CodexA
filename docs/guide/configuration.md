# Configuration

CodexA stores its configuration in `.codexa/config.json`, created by `codexa init`.

## Configuration File

```json
{
  "embedding": {
    "model_name": "all-MiniLM-L6-v2",
    "chunk_size": 512,
    "chunk_overlap": 64
  },
  "search": {
    "top_k": 10,
    "similarity_threshold": 0.3,
    "rrf_k": 60
  },
  "index": {
    "extensions": [".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp"],
    "exclude_patterns": ["**/node_modules/**", "**/.git/**", "**/dist/**"],
    "exclude_files": [],
    "incremental": true
  },
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "sk-...",
    "temperature": 0.2,
    "max_tokens": 2048,
    "rag_budget_tokens": 3000,
    "rag_strategy": "hybrid",
    "rag_use_cross_encoder": false
  },
  "quality": {
    "complexity_threshold": 10,
    "min_maintainability": 40.0,
    "max_issues": 20,
    "snapshot_on_index": false,
    "history_limit": 50
  }
}
```

## Sections

### `embedding`

Controls the sentence-transformer model used for vector encoding.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `model_name` | string | `all-MiniLM-L6-v2` | Sentence-transformer model name |
| `chunk_size` | int | 512 | Maximum tokens per code chunk |
| `chunk_overlap` | int | 64 | Overlap between consecutive chunks |

::: tip Model Profiles
Instead of setting `model_name` manually, use model profiles for one-command setup:

```bash
codexa init --profile fast       # mxbai-embed-xsmall — fast, low RAM (<1 GB)
codexa init --profile balanced   # MiniLM — good balance (~2 GB RAM)
codexa init --profile precise    # jina-code — best quality (~4 GB RAM)
codexa init                      # Auto-detects RAM and picks the best profile
```

View profiles: `codexa models profiles`
Benchmark models: `codexa models benchmark`
:::

### `search`

Controls search behavior across all modes.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `top_k` | int | 10 | Default number of results |
| `similarity_threshold` | float | 0.3 | Minimum cosine similarity score |
| `rrf_k` | int | 60 | Reciprocal Rank Fusion constant |

### `index`

Controls which files are indexed.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `extensions` | list | See above | File extensions to index |
| `exclude_patterns` | list | See above | Glob patterns to exclude directories |
| `exclude_files` | list | `[]` | Glob patterns to exclude specific files (e.g., `["*.min.js", "*.generated.*"]`) |
| `incremental` | bool | true | Only re-index changed files |

You can also create a `.codexaignore` file in your project root (same syntax as `.gitignore`) to exclude files from indexing:

```text
# .codexaignore
*.min.js
*.bundle.js
vendor/
secrets/
*.generated.*
```

### `llm`

Configure the LLM provider for AI-powered commands.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | — | `openai`, `ollama`, or `mock` |
| `model` | string | — | Model name (e.g., `gpt-4`, `llama3`) |
| `api_key` | string | — | API key (OpenAI only) |
| `temperature` | float | 0.2 | Sampling temperature |
| `max_tokens` | int | 2048 | Maximum response tokens |
| `rag_budget_tokens` | int | 3000 | Token budget for RAG context assembly |
| `rag_strategy` | string | `hybrid` | Retrieval strategy: `semantic`, `keyword`, `hybrid`, or `multi` |
| `rag_use_cross_encoder` | bool | false | Use cross-encoder model for re-ranking (slower, more precise) |

::: tip RAG Pipeline
The RAG pipeline controls how code context is retrieved and assembled before sending to the LLM. The `hybrid` strategy (default) combines semantic and keyword search with Reciprocal Rank Fusion for best results. Enable `rag_use_cross_encoder` for precision-critical queries — it uses `ms-marco-MiniLM-L-6-v2` for re-ranking but adds latency.
:::

### `quality`

Controls the quality analysis pipeline and gates.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `complexity_threshold` | int | 10 | Min cyclomatic complexity to flag |
| `min_maintainability` | float | 40.0 | Min maintainability index for gate |
| `max_issues` | int | 20 | Max issues before gate failure |
| `snapshot_on_index` | bool | false | Auto-snapshot after indexing |
| `history_limit` | int | 50 | Max stored snapshots |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (overrides config) |
| `CODEX_LLM_PROVIDER` | Force LLM provider |
| `CODEX_LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`) |

## Project Structure

After `codexa init`:

```
.codexa/
├── config.json     # Configuration file
├── index/          # FAISS vector index
├── cache/          # Query and embedding caches
├── sessions/       # Multi-turn chat sessions
├── memory.json     # Quality snapshots
└── plugins/        # Custom plugin files
```
