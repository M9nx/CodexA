# 07 — Architecture Audit

## Component Responsibility Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    VS Code Extension (Node.js)                  │
│  extension.ts: 1,121 lines — all logic in one file             │
│  4 webview panels · 8 commands · binary resolution             │
│  No tests · No CSP · No workspace trust check                  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ execFile(codexa, argv)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       CLI Layer (click)                         │
│  40 command files in cli/commands/ · main.py · router.py       │
│  --json · --pipe · --verbose global flags                       │
│  Output format tightly coupled to extension parsing             │
└────────────────┬────────────────────────────────────────────────┘
                 │ Python function calls
                 ▼
┌────────────────────────────────────────────────────────────────┐
│               Service Layer (Python)                           │
│  IndexingService · SearchService                               │
│  Config · Storage · Cache                                      │
├────────────────┬───────────────────────────────────────────────┤
│  AI Layer      │  Analysis Layer                               │
│  llm/ · rag/   │  analysis/ · quality/ · metrics/             │
│  evolution/    │  impact/ · hotspots/                          │
├────────────────┴───────────────────────────────────────────────┤
│               Parsing Layer (Python + Rust)                    │
│  tree-sitter parser (Python) · RustChunker · AstChunker       │
├────────────────────────────────────────────────────────────────┤
│               Search Layer (Python + Rust)                     │
│  VectorStore (FAISS/Rust flat/Rust HNSW) · BM25 (Py/Rust)    │
│  grep.py · hybrid_search.py · keyword_search.py               │
└────────────────┬───────────────────────────────────────────────┘
                 │ Optional native module
                 ▼
┌────────────────────────────────────────────────────────────────┐
│               Rust Extension (codexa_core)                     │
│  RustVectorStore · HnswVectorStore · RustBM25Index            │
│  RustChunker · AstChunker · RustScanner · RRF                 │
│  [optional: OnnxEmbedder · TantivyIndex]                      │
└────────────────────────────────────────────────────────────────┘
                 │ File I/O
                 ▼
┌────────────────────────────────────────────────────────────────┐
│               Storage (.codexa/)                               │
│  vectors.bin · metadata.json · bm25.json · hashes.json        │
│  config.json · sessions/ · query_history.json                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Architectural Violations and Concerns

### 1. Extension is Tightly Coupled to CLI Output Format — P1

The VS Code extension parses `codexa` JSON output by field name (e.g., `data.results || data.snippets`). The extension and CLI share **no versioned contract**. A field rename or restructuring in the Python CLI would silently break the extension. The `extractJson` fallback (`try JSON.parse; find first { or [; retry`) makes this even more brittle.

**Recommendation:** Define a versioned JSON output contract. Include `"version": 1` in `--json` responses. Add a compatibility check in the extension.

### 2. Duplicate Search Logic — P2

Both Python and Rust implement:
- Vector similarity search (FAISS vs `RustVectorStore`/`HnswVectorStore`)
- BM25 keyword indexing
- Code chunking
- File scanning

The Python implementations and Rust implementations are intended to be interchangeable via `rust_backend.py`. However, there is **no integration test** that verifies both return identical results for the same input. Behavior divergence between Python and Rust paths is plausible and undetected.

### 3. Silent Fallback Behavior — P1

`rust_backend.py` silently falls back to Python if `codexa_core` is not installed:
```python
except ImportError:
    logger.debug("Rust backend not available — using Python fallback.")
```

A `logger.debug` message is invisible by default. Users and agents will not know they are running with degraded performance (Python FAISS vs Rust HNSW). The `codexa doctor` command reports this, but it is not surfaced during indexing or search.

**Recommendation:** Surface backend selection in `codexa index` output and in the VS Code status bar.

### 4. Unversioned Storage Schema — P1

The storage format (`vectors.bin`, `metadata.json`, etc.) has no schema version. If the format changes, an old index is silently loaded with incorrect data or a confusing error. The `IndexManifest` partially addresses this (tracks embedding model name), but not the storage format.

**Recommendation:** Add `schema_version: int` to `IndexManifest`. Refuse to load mismatched versions with a clear upgrade message.

### 5. CI Does Not Test the Full Stack — P1

The `ci.yml` only runs Python unit tests. It does not:
- Build the Rust extension
- Test the extension with the Rust backend
- Compile the VS Code extension
- Run VS Code extension tests
- Run `mypy`, `bandit`, or `radon`
- Enforce coverage

### 6. Web Server and API Not Tested — P2

`web/server.py` (16% coverage) and `web/api.py` (20%) handle all HTTP bridge traffic. These are invoked externally by agents and MCP clients. Their untested error paths could return uncaught exceptions as HTTP 500 with stack traces.

### 7. requirements.txt Drift Risk — P2

`requirements.txt` is a duplicate of `pyproject.toml` dependencies, without the optional `ml`, `dev`, or `tui` extras. CI installs from `requirements.txt` but the actual package is built from `pyproject.toml`. The two files can drift silently.

### 8. Single-File Extension Architecture — P2

`extension.ts` is 1,121 lines. It contains UI logic, business logic, HTML templates, CSS, inline JavaScript, and binary resolution — all interleaved. This makes the extension hard to test, maintain, or extend. The webview HTML/JS should be extracted into separate template files.

### 9. Version Number Mismatch — P3

`pyproject.toml` declares `version = "0.5.0"`. `Cargo.toml` declares `version = "0.1.0"`. `vscode-extension/package.json` declares `"version": "0.2.0"`. None of these are coordinated. A release of `0.6.0` for the Python package would not automatically update the Rust or extension versions.

---

## Dependency Diagram (Simplified)

```
vscode-extension
  └─ depends on: codexa CLI (via execFile, no version check)

codexa CLI
  └─ depends on: semantic_code_intelligence (Python package)
     └─ depends on: codexa_core (optional Rust wheel)
        └─ depends on: pyo3, tree-sitter, instant-distance, blake3, rayon

semantic_code_intelligence
  └─ depends on: sentence-transformers, faiss-cpu (ml extra)
  └─ depends on: mcp, click, pydantic, rich, watchfiles
```

**Circular dependencies:** None detected.

**Architectural observation:** The Rust extension is a pure performance optimization layer — it does not introduce new features. This is a good design choice. The concern is that the fallback is silent and the two paths are not integration-tested.
