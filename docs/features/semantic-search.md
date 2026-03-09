# Semantic Search

CodexA's core capability is **semantic code search** — finding code by what it does,
not just pattern matching on text.

## How It Works

1. **Indexing** — Source files are parsed, chunked, and each chunk is encoded
   into a 384-dimensional vector using `all-MiniLM-L6-v2`
2. **Query** — Your search query is encoded using the same model
3. **Similarity** — FAISS finds the closest vectors via cosine similarity
4. **Ranking** — Results optionally fused with BM25 keyword scores via Reciprocal Rank Fusion

## Search Modes

### Semantic (default)

Vector similarity search — finds conceptually related code:

```bash
codex search "authentication middleware"
codex search "database connection pooling"
```

### Keyword (BM25)

Traditional ranked keyword search:

```bash
codex search "jwt_token" --mode keyword
```

### Hybrid (RRF)

Fuses semantic and keyword results for the best of both:

```bash
codex search "error handling" --mode hybrid
```

### Regex

Grep-compatible regular expression search:

```bash
codex search "def\s+authenticate" --mode regex -n
codex search "TODO|FIXME" --mode regex -l
```

## Grep Compatibility

CodexA supports familiar grep flags:

| Flag | Description |
|------|-------------|
| `-l` | Show only file paths with matches |
| `-L` | Show only file paths without matches |
| `-n` | Prefix lines with line numbers |
| `-C N` | Show N context lines around matches |
| `-s` | Case-sensitive (regex mode) |

## Output Formats

```bash
# Human-readable (default)
codex search "auth"

# JSON for AI agents
codex search "auth" --json

# JSONL for streaming/piping
codex search "auth" --jsonl | jq .file_path

# Full enclosing function/class context
codex search "auth" --full-section
```

## Configuration

Tune search behavior in `.codex/config.json`:

```json
{
  "search": {
    "top_k": 10,
    "similarity_threshold": 0.3,
    "rrf_k": 60
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `top_k` | 10 | Number of results to return |
| `similarity_threshold` | 0.3 | Minimum score to include |
| `rrf_k` | 60 | RRF fusion constant (higher = more weight to lower ranks) |

## Embedding Model

CodexA uses `all-MiniLM-L6-v2` by default — a compact model that:

- Produces 384-dimensional vectors
- Runs entirely offline (no API calls)
- Supports 12 programming languages
- First run downloads ~80MB model, then cached locally

Manage models with:

```bash
codex models list           # Available models
codex models info <name>    # Model details
codex models download <n>   # Pre-download for offline use
codex models switch <name>  # Switch active model (requires re-index)
```

## Performance

- **Indexing**: ~1,000 files/minute on typical hardware
- **Search**: <100ms per query after indexing
- **Memory**: FAISS index is memory-mapped for large codebases
- **Incremental**: Only changed files are re-indexed (`codex index --force` for full rebuild)
