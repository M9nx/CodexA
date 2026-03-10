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
    "incremental": true
  },
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "sk-...",
    "temperature": 0.2,
    "max_tokens": 2048
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
| `exclude_patterns` | list | See above | Glob patterns to exclude |
| `incremental` | bool | true | Only re-index changed files |

### `llm`

Configure the LLM provider for AI-powered commands.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | — | `openai`, `ollama`, or `mock` |
| `model` | string | — | Model name (e.g., `gpt-4`, `llama3`) |
| `api_key` | string | — | API key (OpenAI only) |
| `temperature` | float | 0.2 | Sampling temperature |
| `max_tokens` | int | 2048 | Maximum response tokens |

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
