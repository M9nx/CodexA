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
codexa search "authentication middleware"
codexa search "database connection pooling"
```

### Keyword (BM25)

Traditional ranked keyword search:

```bash
codexa search "jwt_token" --mode keyword
```

### Hybrid (RRF)

Fuses semantic and keyword results for the best of both:

```bash
codexa search "error handling" --mode hybrid
```

### Regex

Grep-compatible regular expression search:

```bash
codexa search "def\s+authenticate" --mode regex -n
codexa search "TODO|FIXME" --mode regex -l
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
codexa search "auth"

# JSON for AI agents
codexa search "auth" --json

# JSONL for streaming/piping
codexa search "auth" --jsonl | jq .file_path

# Full enclosing function/class context
codexa search "auth" --full-section
```

## Configuration

Tune search behavior in `.codexa/config.json`:

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
codexa models list           # Available models
codexa models info <name>    # Model details
codexa models download <n>   # Pre-download for offline use
codexa models switch <name>  # Switch active model (requires re-index)
```

## Performance

- **Indexing**: ~1,000 files/minute on typical hardware
- **Search**: <100ms per query after indexing
- **Memory**: FAISS index is memory-mapped for large codebases
- **Incremental**: Only re-embeds changed chunks (content-hash caching)
- **BM25 persistence**: BM25 index cached to disk, loads in <10ms

## Raw Filesystem Grep

For instant results without an index, use the `codexa grep` command:

```bash
codexa grep "TODO|FIXME"                # Search all files
codexa grep "def authenticate" -g "*.py"  # Filter by file type
codexa grep "password" --case-sensitive   # Case-sensitive
codexa grep "import re" --json            # JSON output
codexa grep "class.*Service" -l           # Files-only (like grep -l)
```

Uses **ripgrep** for speed when available, falls back to pure Python.
Unlike `codexa search --mode regex`, this searches the actual filesystem —
no index required.

## Benchmarking

Measure real performance on your codebase:

```bash
codexa benchmark
```

Reports indexing speed, search latency (all 4 modes with p50/p99/QPS), BM25
persistence speedup, and memory usage.
- **Incremental**: Only changed files are re-indexed (`codexa index --force` for full rebuild)
