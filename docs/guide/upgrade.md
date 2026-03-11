# Upgrade Guide

## Upgrading to v0.5.0

v0.5.0 is the **Search Dominance** release — 5 phases (33–37) closing the output, indexing, and UX gap with pure-Rust search tools like [ck](https://github.com/BeaconBay/ck), while keeping CodexA's unique intelligence features.

### Install

```bash
pip install --upgrade codexa

# Or with ML extras
pip install --upgrade "codexa[ml]"
```

### What's New

#### Search & Grep Output (Phase 33)

New flags on `codexa search` and `codexa grep`:

```bash
# JSONL streaming — one JSON object per line (ideal for AI agents and pipelines)
codexa search "auth flow" --jsonl
codexa grep "TODO" --jsonl

# Show relevance scores
codexa search "error handling" --scores

# Control snippet length or omit snippets entirely
codexa search "database" --snippet-length 100
codexa search "database" --no-snippet

# Exclude files by glob, include gitignored files
codexa search "config" --exclude "*.test.*" --no-ignore
codexa grep "FIXME" --exclude "vendor/*" -L
```

#### Incremental Indexing (Phase 34)

```bash
# Index a single file without full scan
codexa index --add src/new_module.py

# Inspect a file's index metadata (content hash, chunks, vectors)
codexa index --inspect src/auth.py
```

- **Model-consistency guard**: Detects if the embedding model changed since last index and warns before corrupting vectors
- **Ctrl+C safety**: Partial index is saved on interrupt; next run resumes

#### Tantivy Full-Text Engine (Phase 35)

Optional Rust-native [Tantivy](https://github.com/quickwit-oss/tantivy) full-text search engine. Requires building `codexa-core` with the `tantivy-backend` feature:

```bash
cd codexa-core
maturin develop --release --features tantivy-backend
```

Check availability:

```python
from semantic_code_intelligence.rust_backend import use_tantivy
print(use_tantivy())  # True if compiled with tantivy-backend
```

#### MCP Server v2 (Phase 36)

- **Cursor-based pagination** on `semantic_search`, `keyword_search`, `hybrid_search` MCP tools — pass `page_size` and `cursor` parameters
- **`codexa --serve`** shorthand to start the MCP server in one flag
- **Claude Desktop auto-config**:

```bash
# Print the MCP configuration JSON for Claude Desktop
codexa mcp --claude-config
```

#### Search Shorthands & Distribution (Phase 37)

```bash
# Mode shorthands (match ck's UX)
codexa search "query" --hybrid    # equivalent to --mode hybrid
codexa search "query" --sem       # equivalent to --mode semantic

# .codexaignore is auto-created on first index with sensible defaults
```

PyInstaller spec included at `codexa.spec` for single-binary distribution.

### Breaking Changes

None. All new flags are additive. Existing CLI invocations work unchanged.

### Migration Checklist

1. `pip install --upgrade codexa`
2. Re-index to pick up model-consistency guard: `codexa index --force`
3. (Optional) Build with Tantivy: `maturin develop --release --features tantivy-backend`
4. (Optional) Set up Claude Desktop: `codexa mcp --claude-config`

---

## Previous Versions

### v0.4.5

- RAG Pipeline (Phase 31): 4-stage Retrieve → Deduplicate → Re-rank → Assemble
- Cross-encoder re-ranking, token-aware budgets, source citations

### v0.4.4

- Model Profiles: `fast`, `balanced`, `precise` with auto-detection
- `codexa init --profile`, `codexa models profiles`, `codexa models benchmark`

### v0.4.3

- Bundled tree-sitter grammars, `exclude_files` config
- Install tiers: `pip install codexa` (lightweight) vs `pip install "codexa[ml]"`

### v0.4.0

- First stable public release
- 39 CLI commands, 13 AI agent tools, 22 plugin hooks
