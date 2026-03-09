---
hide:
  - navigation
---

# CodexA

**Developer intelligence CLI — semantic code search, AI-assisted understanding, and workspace tooling.**

<div class="grid cards" markdown>

-   :material-magnify: **Semantic Search**

    ---

    Natural-language code search powered by sentence-transformers and FAISS vector store.

-   :material-robot: **AI Agent Protocol**

    ---

    8 structured tools invocable via CLI, HTTP bridge, MCP, or Python API.

-   :material-file-tree: **Multi-Language Parsing**

    ---

    Tree-sitter AST parsing for 12 languages with symbol extraction.

-   :material-chart-line: **Quality & Metrics**

    ---

    Cyclomatic complexity, maintainability index, hotspots, impact analysis, and quality gates.

-   :material-puzzle: **Plugin System**

    ---

    22 hook points for extending indexing, search, analysis, AI, and more.

-   :material-sync: **Self-Improving Loop**

    ---

    Budget-aware evolution engine that discovers, patches, tests, and commits improvements.

</div>

## At a Glance

| Metric | Value |
|--------|-------|
| **Version** | 0.28.0 |
| **CLI Commands** | 36 |
| **AI Agent Tools** | 8 (+ plugin-registered) |
| **Plugin Hooks** | 22 |
| **Packages** | 26 |
| **Parsed Languages** | 12 |
| **Tests** | 2595+ |

## Quick Links

- [Installation](installation.md) — Get CodexA running in under a minute
- [Quick Start](quickstart.md) — Index a project and start searching
- [CLI Reference](CLI.md) — All 36 commands documented
- [Architecture](architecture.md) — System design and package map
- [Plugin System](PLUGINS.md) — Extend CodexA with custom hooks
- [API Reference](api.md) — REST, Bridge, MCP, and Python APIs

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| CLI | Click |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector Search | FAISS |
| Code Parsing | tree-sitter |
| Data Models | Pydantic |
| Terminal UI | Rich / Textual |
| Security Lint | Bandit |
| Complexity | Radon |
| Agent Protocol | MCP SDK |

## License

MIT — see [LICENSE](https://github.com/M9nx/CodexA/blob/main/LICENSE) for details.
