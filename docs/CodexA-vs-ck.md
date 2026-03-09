# CodexA vs ck — Key Differences

A side-by-side comparison of **CodexA** (Developer Intelligence Engine) and
**[ck](https://github.com/BeaconBay/ck)** (Semantic Code Search / grep replacement).

---

## At a Glance

| Dimension | **CodexA** | **ck** |
|-----------|-----------|--------|
| Tagline | Developer intelligence engine | Semantic grep / code search |
| Language | Python 3.11+ | Rust |
| Install | `pip install codex-ai` | `cargo install ck-search` |
| Version | 0.28.0 | 0.7.4 |
| License | MIT | MIT / Apache-2.0 |
| Stars | Private / early-stage | ~1.5 k |
| Offline | Yes | Yes |

---

## Scope & Philosophy

| | CodexA | ck |
|---|---|---|
| **Primary goal** | Full-stack developer intelligence — search, analysis, AI agent tooling, quality CI, self-improving loop | Fast semantic code search that replaces grep |
| **Design** | Monolithic Python package with CLI, web UI, REST API, bridge server, plugin system | Modular Rust workspace focused on a single binary |
| **Audience** | AI agents (Copilot, Cursor, Cline) + developers via CLI/web | Developers on the terminal + AI agents via MCP |

**TL;DR:** ck is a *search tool*; CodexA is an *intelligence platform* that includes search among many other capabilities.

---

## Search Capabilities

| Feature | CodexA | ck |
|---------|--------|-----|
| Semantic search | ✅ Natural-language queries via FAISS | ✅ Embedding-based via custom ANN index |
| Keyword search (BM25) | ✅ Built-in BM25 engine with camelCase/underscore-aware tokenizer (`--mode keyword`) | ✅ Tantivy full-text index |
| Regex search | ✅ Grep-compatible pattern matching (`--mode regex`, `-C`, `-l`, `-L`, `-n`, `--case-sensitive`) | ✅ Full grep-compatible CLI (`-n`, `-i`, `-A`, `-B`, `-l`, `-L`, etc.) |
| Hybrid search (semantic + keyword) | ✅ Reciprocal Rank Fusion with k=60 (`--mode hybrid`) | ✅ Reciprocal Rank Fusion |
| Threshold / score filtering | ✅ `--threshold` | ✅ `--threshold`, `--scores` |
| Full-section extraction | ✅ `--full-section` expands to enclosing function/class via symbol registry | ✅ `--full-section` returns entire functions/classes |
| JSONL / JSON output | ✅ `--json` and `--jsonl` on search (pipe into `jq`/`fzf`) | ✅ `--json`, `--jsonl` |
| Streaming output | ✅ `--stream` for token-by-token chat/investigate responses | ❌ |

**Verdict:** Full search parity — both tools support semantic, keyword, regex, and hybrid modes with grep-style flags (`-C`, `-l`, `-L`, `-n`) and JSONL output. CodexA adds full-section extraction via its symbol registry and streaming LLM output.

---

## Indexing & Embeddings

| Feature | CodexA | ck |
|---------|--------|-----|
| Embedding library | sentence-transformers (Python) + optional ONNX runtime | FastEmbed (Rust) |
| Default model | `all-MiniLM-L6-v2` (384-dim) | `bge-small` (384-dim) |
| Model options | 5 built-in models with `codex models list/info/download/switch` CLI | 4 built-in: BGE-Small, Mixedbread xsmall, Nomic V1.5, Jina Code |
| ONNX acceleration | ✅ Auto-detected via `optimum`/`onnxruntime`, PyTorch fallback | ✅ Native ONNX via FastEmbed |
| Vector store | FAISS `IndexFlatIP` (+ auto-upgrade to `IndexIVFFlat` for >50 k vectors) + BM25 inverted index | Custom ANN index + Tantivy full-text |
| Incremental indexing | ✅ Chunk-level SHA-256 hashing + stale vector removal | ✅ Chunk-level caching, 80-90% hit rate |
| Chunk-level delta | ✅ Chunk-level (SHA-256 per `file:start:end`, skips unchanged) | ✅ Chunk-level (only re-embeds changed chunks) |
| Parallel indexing | ✅ ThreadPoolExecutor with configurable workers | ✅ Rayon parallel iterators |
| Tree-sitter parsing | ✅ 12 languages | ✅ 7+ languages |
| Auto-index on search | ✅ Transparent build on first search (disable with `--no-auto-index`) | ✅ Transparent build on first search |
| Ignore files | ✅ `.gitignore` + `.codexaignore` | ✅ `.gitignore` + `.ckignore` |

**Verdict:** Feature parity on indexing — both have chunk-level incremental indexing, multiple models, ONNX acceleration, and auto-indexing. CodexA offers broader parsing (12 vs 7 languages); ck benefits from Rust's raw throughput.

---

## AI Agent Integration

| Feature | CodexA | ck |
|---------|--------|-----|
| Protocol | HTTP bridge (port 24842) + MCP server (`codex mcp`) + 8 structured tools | MCP server (`ck --serve`) |
| Tool count | 8 (explain_symbol, get_call_graph, get_dependencies, get_context, find_references, explain_file, summarize_repo, search) | 6 (semantic_search, regex_search, hybrid_search, index_status, reindex, health_check) |
| LLM providers | OpenAI, Ollama, Mock (with caching + rate limiting) | None (search only; LLM is external) |
| AI-driven investigation | ✅ `codex investigate` — multi-step ReAct loop | ❌ |
| AI-driven code chat | ✅ `codex chat`, `codex ask` | ❌ |
| Copilot integration | ✅ `.github/copilot-instructions.md` | ✅ Claude Desktop / Cursor via MCP |

**Verdict:** CodexA is designed *to be called by* AI agents and also *to call* LLMs itself. ck provides search as a tool for external AI agents but doesn't include its own LLM layer.

---

## Analysis & Quality

| Feature | CodexA | ck |
|---------|--------|-----|
| Call graph extraction | ✅ AST-based (tree-sitter), bidirectional | ❌ |
| Dependency mapping | ✅ Import/require analysis | ❌ |
| Code quality analysis | ✅ Complexity, dead code, duplicates, security | ❌ |
| Metrics & trends | ✅ Maintainability index, LOC, snapshots, trend tracking | ❌ |
| Hotspot detection | ✅ Change-frequency × complexity | ❌ |
| Impact / blast radius | ✅ Symbol-level change impact | ❌ |
| Safety validation | ✅ OWASP-inspired rules | ❌ |
| PR summary generation | ✅ AI-generated | ❌ |
| Documentation generation | ✅ Auto-generate project docs | ❌ |
| Self-improving loop | ✅ `codex evolve` — auto-fix/improve code | ❌ |

**Verdict:** This is CodexA's unique strength — ck is deliberately scoped to search only.

---

## User Interfaces

| Feature | CodexA | ck |
|---------|--------|-----|
| CLI commands | 36 click-based commands | Single multi-flag binary |
| Web UI | ✅ 7-page server-rendered UI (search, symbols, tools, quality, ask, workspace, viz) | ❌ |
| REST API | ✅ 14 endpoints | ❌ (MCP only) |
| TUI (terminal UI) | ✅ Rich Textual split-pane TUI with syntax preview, mode cycling, keybindings + fallback REPL | ✅ ratatui-based interactive search |
| MCP server | ✅ JSON-RPC over stdio (protocol v2024-11-05, 8 tools) | ✅ JSON-RPC MCP server |
| VS Code extension | ✅ Sidebar search, call graph, Ask CodexA, model management | ✅ (in development) |
| Mermaid visualizations | ✅ Call graphs + dependency graphs | ❌ |

**Verdict:** CodexA now matches or exceeds ck on all UI dimensions — rich TUI, MCP, web UI, REST API, VS Code extension, and Mermaid visualizations.

---

## Performance

| Metric | CodexA | ck |
|--------|--------|-----|
| Implementation | Python (interpreted) + optional ONNX/C++ acceleration | Rust (compiled, native speed) |
| Indexing speed | Moderate — parallel indexing + chunk-level skip + IVF for large repos | Fast (~1M LOC in <2 min) |
| Search latency | Sub-second (FAISS flat); faster with IVF on large repos | Sub-500ms |
| Binary size | ✅ Single binary via PyInstaller (`python build.py`) | Single static binary |
| Memory | Higher (Python + PyTorch + FAISS) | Lower (Rust + ONNX runtime) |

**Verdict:** ck is faster and leaner — Rust's performance advantage is real for a search-focused tool.

---

## When to Use Which

| Scenario | Recommended |
|----------|------------|
| Fast semantic grep replacement on the terminal | **ck** |
| AI agent that needs deep codebase context (call graphs, deps, symbols) | **CodexA** |
| CI pipeline quality gates (complexity, dead code, metrics) | **CodexA** |
| Interactive terminal search with preview panes | **Both** (CodexA Textual TUI, ck ratatui TUI) |
| Web dashboard for codebase exploration | **CodexA** |
| Drop-in grep replacement with semantic boost | **ck** |
| LLM-powered code investigation / chat | **CodexA** |
| Minimal install, zero Python dependency | **ck** |
| Plugin-extensible analysis platform | **CodexA** |

---

## Summary

**ck** is a polished, fast, Rust-based *semantic grep* — it does search exceptionally well with grep compatibility, hybrid modes, a TUI, and MCP integration.

**CodexA** is a broader *developer intelligence engine* — search is one of 36 capabilities including code analysis, quality CI, AI-agent tooling, LLM orchestration, visualization, and a self-improving development loop. As of v0.28.0, CodexA has closed **all remaining gaps** — grep flag parity (`-C`, `-l`, `-L`, `-n`, `--jsonl`), a rich Textual TUI, VS Code extension, model management CLI, IVF-accelerated search, single-binary distribution via PyInstaller, and polished UI/UX across all interfaces (CLI, TUI, Web, VS Code).

They solve different problems at different layers of the stack and could complement each other: ck for blazing-fast Rust-native terminal search, CodexA for deep analysis, AI cooperation, and the full developer intelligence platform.
