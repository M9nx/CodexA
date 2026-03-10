# CodexA v0.4.5 — Release Notes

> **Released:** 2025 · **License:** MIT · **Docs:** [codex-a.dev](https://codex-a.dev)

**CodexA** is a developer intelligence engine for semantic code search, AI-assisted code understanding, and agent tooling.

---

## What's New in v0.4.5

This release implements **Phase 31 — RAG Pipeline for LLM Commands**, replacing the old "dump context into prompt" approach with a proper Retrieval-Augmented Generation pipeline.

### RAG Pipeline
- **4-stage pipeline**: Retrieve → Deduplicate → Re-rank → Assemble — each stage optimized for precision and token efficiency
- **Retrieval strategies**: `semantic` (vector), `keyword` (BM25), `hybrid` (RRF merge), `multi` (parallel with diversity)
- **Cross-encoder re-ranking**: Optional `ms-marco-MiniLM-L-6-v2` model for high-precision re-ranking (set `rag_use_cross_encoder: true`)
- **Token-aware assembly**: Context is assembled within a configurable token budget (default 3000), preventing prompt overflow
- **Source citations**: Responses include numbered `[N]` markers citing exact file paths and line ranges

### Configuration
Three new fields in `llm` config (`.codexa/config.json`):
```json
{
  "llm": {
    "rag_budget_tokens": 3000,
    "rag_strategy": "hybrid",
    "rag_use_cross_encoder": false
  }
}
```

### Integration
- `codexa ask` — RAG-powered context retrieval with citations
- `codexa chat` — RAG context injection into conversation
- `codexa suggest` — RAG-enhanced improvement suggestions
- `codexa investigate` — RAG-powered search actions with citation markers
- Web UI and REST API — RAG config passed through

---

## Previous Releases

### v0.4.4 — Model Flexibility & Smart Defaults
- Tree-sitter grammar packages bundled in core dependencies
- `index.exclude_files` config, `.codexaignore` support
- MemoryError handling for low-RAM machines
- Reduced HuggingFace noise, improved CLI guidance
- Community fixes ([#2](https://github.com/M9nx/CodexA/issues/2))

### v0.4.2 — NumPy Compatibility
- Pinned `numpy < 2` to avoid ABI breakage with FAISS on some platforms

### v0.4.1 — Lightweight Install Split
- Moved heavy ML libraries (`sentence-transformers`, `torch`, `faiss-cpu`) to `[ml]` extra
- Core `pip install codexa` installs the CLI + tree-sitter parsing without ML overhead

### v0.4.0 — First Stable Public Release
- Package renamed `codexa-ai` → `codexa`
- 39 CLI commands, 13 AI agent tools, 22 plugin hooks
- Semantic search (FAISS + sentence-transformers), multi-mode search, quality analysis
- Docker image, Homebrew formula, MCP server, VS Code extension

---

## Installation

```bash
# Lightweight CLI (parsing, grep, quality, explain)
pip install codexa

# Full ML stack (semantic search, vector indexing, embeddings)
pip install "codexa[ml]"
```

Verify:

```bash
codexa --version
# codexa, version 0.4.4
```

## Quick Start

```bash
cd /path/to/your-project
codexa init --index       # Initialize and index in one step
codexa search "auth"      # Semantic code search
codexa explain MyClass    # Structural symbol explanation
codexa quality src/       # Code quality analysis
codexa doctor             # Environment health check
```

## Stats

| Metric | Value |
|--------|-------|
| **Version** | 0.4.4 |
| **CLI Commands** | 39 |
| **AI Agent Tools** | 13 |
| **Plugin Hooks** | 22 |
| **Parsed Languages** | 11 |
| **Tests** | 2596 |
| **Python** | >= 3.11 |

## Documentation

Full documentation: [codex-a.dev](https://codex-a.dev)

## License

MIT
