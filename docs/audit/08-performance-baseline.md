# 08 — Performance and Scalability Baseline

## Status: Baseline Not Yet Established

No reproducible benchmark has been run as part of this audit. The `codexa benchmark` command exists but has not been validated against a clean environment or documented as part of the development workflow.

This document defines the **procedure** for establishing baselines and records the known limitations.

---

## Known Performance Characteristics (from Code Inspection)

### Indexing

| Characteristic | Implementation | Notes |
|---------------|----------------|-------|
| Parallelism | `indexing/parallel.py` (ThreadPoolExecutor) | Python GIL likely limits true parallel CPU (estimate) |
| Rust parallel scan | `codexa-core/src/scan.rs` (rayon) | When Rust wheel installed; avoids GIL (estimate) |
| Embedding batch size | Configurable (`embedding.batch_size`) | Default varies by profile |
| Chunking strategy | Line-boundary or AST-aware (Rust) | AST chunker requires native wheel |
| Incremental indexing | Hash-based (blake3/Python) | Skips unchanged files |
| Memory use | Embedding model (all-MiniLM-L6-v2 ≈2 GB) | `--profile fast` < 1 GB |
| Ctrl+C partial-save | Implemented | Partial indexes are usable |

### Search

| Characteristic | Implementation | Notes |
|---------------|----------------|-------|
| Semantic search | FAISS IndexFlatIP or Rust flat | O(n) for flat, O(log n) for HNSW |
| BM25 | Python `rank_bm25` or Rust BM25 | Rust expected to be significantly faster (estimate) |
| Hybrid RRF | Python or Rust `reciprocal_rank_fusion_rs` | — |
| Top-K default | 10 | Configurable |
| Result re-ranking | Cross-encoder (optional) | Requires sentence-transformers |

### Memory

| Profile | Embedding Model | Approx. RAM (Estimate) |
|---------|----------------|-------------|
| fast | mxbai-embed-xsmall | < 1 GB |
| balanced | all-MiniLM-L6-v2 | ≈ 2 GB |
| precise | jina-code | ≈ 4 GB |

---

## Benchmark Procedure (To Be Established)

### Repository Sizes

| Size | Criteria | Suggested Repo |
|------|----------|----------------|
| Small | < 1,000 files | This repo (CodexA itself) |
| Medium | 1,000–20,000 files | CPython stdlib or Django |
| Large | > 20,000 files | Linux kernel headers or Chromium |

### Metrics to Record

1. Cold indexing time (first run, empty cache)
2. Incremental indexing time (single file change)
3. Semantic search latency (p50, p95)
4. Keyword search latency
5. Hybrid search latency
6. Peak memory during indexing
7. Index size on disk
8. VS Code extension activation time
9. First search response time after activation

### Hardware to Document

Must record: CPU, RAM, OS, Python version, Rust backend present/absent, embedding model profile.

---

## Scalability Concerns (from Code Inspection)

| Concern | Evidence | Risk |
|---------|----------|------|
| Python-only indexing is single-threaded for embeddings | `indexing/parallel.py` uses ThreadPoolExecutor but embedding is likely GIL-bound (estimate) | Large repos (> 10,000 files) may be slow without Rust wheel |
| `VectorStore` loads all vectors into memory | `storage/vector_store.py` — full load at `VectorStore.load()` | 50,000+ chunks × 384 dims × 4 bytes ≈ 72 MB RAM |
| Mmap path exists in Rust only | `RustVectorStore.load_mmap()` | Python fallback cannot mmap — full load required |
| BM25 index stored as JSON | `search/keyword_search.py` | Large repos produce large JSON files; slow to load |
| Web server is stdlib `http.server` | `web/server.py` | Single-threaded; not production-grade |
| grep fallback uses Python `re` | `search/grep.py` | Catastrophically slow on large repos without ripgrep |

---

## Action Required

The following benchmark must be established before Release 3:

```bash
# In a clean environment, on documented hardware:
codexa init --profile balanced
time codexa index .               # cold index
time codexa index .               # warm (incremental, no changes)
time codexa index --add src/x.py  # single-file incremental
time codexa search "authentication" -k 10  # semantic
time codexa search --mode keyword "auth"   # keyword
time codexa search --mode hybrid "auth"    # hybrid
```

Record output in `docs/audit/08-performance-baseline.md` with hardware specs.
