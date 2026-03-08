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
| Version | 0.25.0 | 0.7.4 |
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
| Regex / keyword search | ❌ (delegates to grep) | ✅ Full grep-compatible CLI (`-n`, `-i`, `-A`, `-B`, `-l`, `-L`, etc.) |
| Hybrid search (semantic + keyword) | ❌ | ✅ Reciprocal Rank Fusion |
| Threshold / score filtering | ✅ `--threshold` | ✅ `--threshold`, `--scores` |
| Full-section extraction | ❌ | ✅ `--full-section` returns entire functions/classes |
| JSONL / JSON output | ✅ `--json` on all commands | ✅ `--json`, `--jsonl` |

**Verdict:** ck wins on raw search flexibility — it's a purpose-built search tool with grep parity. CodexA's search is one component of a larger system.

---

## Indexing & Embeddings

| Feature | CodexA | ck |
|---------|--------|-----|
| Embedding library | sentence-transformers (Python) | FastEmbed (Rust) |
| Default model | `all-MiniLM-L6-v2` (384-dim) | `bge-small` (384-dim) |
| Model options | Single default (configurable) | 4 built-in: BGE-Small, Mixedbread xsmall, Nomic V1.5, Jina Code |
| Vector store | FAISS `IndexFlatIP` | Custom ANN index + Tantivy full-text |
| Incremental indexing | ✅ Hash-based, stale vector removal (v0.25.0) | ✅ Chunk-level caching, 80-90% hit rate |
| Chunk-level delta | File-level (re-embeds all chunks of changed file) | Chunk-level (only re-embeds changed chunks) |
| Tree-sitter parsing | ✅ 12 languages | ✅ 7+ languages |
| Auto-index on search | ❌ (explicit `codex index`) | ✅ Transparent build on first search |
| `.gitignore` respect | ✅ | ✅ (plus `.ckignore`) |

**Verdict:** ck has finer-grained (chunk-level) incremental indexing and more model choices. CodexA offers broader parsing coverage (12 vs 7 languages).

---

## AI Agent Integration

| Feature | CodexA | ck |
|---------|--------|-----|
| Protocol | HTTP bridge (port 24842) + 8 structured tools | MCP server (`ck --serve`) |
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
| Call graph extraction | ✅ Regex-based, bidirectional | ❌ |
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
| CLI commands | 32 click-based commands | Single multi-flag binary |
| Web UI | ✅ 4-page server-rendered UI (search, symbols, workspace, viz) | ❌ |
| REST API | ✅ 8 endpoints | ❌ (MCP only) |
| TUI (terminal UI) | ❌ | ✅ ratatui-based interactive search |
| VS Code extension | ❌ | ✅ (in development) |
| Mermaid visualizations | ✅ Call graphs + dependency graphs | ❌ |

**Verdict:** Different strengths — CodexA offers a web UI and visual graphs; ck offers an interactive TUI and emerging VS Code integration.

---

## Performance

| Metric | CodexA | ck |
|--------|--------|-----|
| Implementation | Python (interpreted) | Rust (compiled, native speed) |
| Indexing speed | Moderate (~minutes for large repos) | Fast (~1M LOC in <2 min) |
| Search latency | Sub-second (FAISS) | Sub-500ms |
| Binary size | N/A (Python package) | Single static binary |
| Memory | Higher (Python + PyTorch + FAISS) | Lower (Rust + ONNX runtime) |

**Verdict:** ck is faster and leaner — Rust's performance advantage is real for a search-focused tool.

---

## When to Use Which

| Scenario | Recommended |
|----------|------------|
| Fast semantic grep replacement on the terminal | **ck** |
| AI agent that needs deep codebase context (call graphs, deps, symbols) | **CodexA** |
| CI pipeline quality gates (complexity, dead code, metrics) | **CodexA** |
| Interactive terminal search with preview panes | **ck** |
| Web dashboard for codebase exploration | **CodexA** |
| Drop-in grep replacement with semantic boost | **ck** |
| LLM-powered code investigation / chat | **CodexA** |
| Minimal install, zero Python dependency | **ck** |
| Plugin-extensible analysis platform | **CodexA** |

---

## Summary

**ck** is a polished, fast, Rust-based *semantic grep* — it does search exceptionally well with grep compatibility, hybrid modes, a TUI, and MCP integration.

**CodexA** is a broader *developer intelligence engine* — search is one of 30+ capabilities including code analysis, quality CI, AI-agent tooling, LLM orchestration, visualization, and a self-improving development loop.

They solve different problems at different layers of the stack and could even complement each other: ck for blazing-fast terminal search, CodexA for deep analysis and AI cooperation.
