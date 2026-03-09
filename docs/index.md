---
layout: home

hero:
  name: CodexA
  text: Developer Intelligence Engine
  tagline: Semantic code search, AI-assisted understanding, and workspace tooling for developers and AI agents.
  actions:
    - theme: brand
      text: Get Started
      link: /guide/installation
    - theme: alt
      text: View on GitHub
      link: https://github.com/M9nx/CodexA

features:
  - icon: 🔍
    title: Semantic Search
    details: Natural-language code search powered by sentence-transformers and FAISS vector store. Find code by meaning, not just keywords.
  - icon: 🤖
    title: AI Agent Protocol
    details: 8 structured tools invocable via CLI, HTTP bridge, MCP, or Python API. Built for AI coding assistants.
  - icon: 🌳
    title: Multi-Language Parsing
    details: Tree-sitter AST parsing for 12 languages with symbol extraction, call graphs, and dependency maps.
  - icon: 📊
    title: Quality & Metrics
    details: Cyclomatic complexity (Radon), security lint (Bandit), hotspot detection, impact analysis, and quality gates.
  - icon: 🧩
    title: Plugin System
    details: 22 hook points for extending indexing, search, analysis, AI, and more. Full lifecycle management.
  - icon: 🔄
    title: Self-Improving Loop
    details: Budget-aware evolution engine that discovers, patches, tests, and commits improvements autonomously.
  - icon: 💻
    title: 36 CLI Commands
    details: Comprehensive Click-based CLI with --json, --pipe, and --verbose flags. From search to quality gates.
  - icon: 🌐
    title: Multiple Interfaces
    details: CLI, Web UI, Bridge Server, MCP Server, LSP Server, and interactive TUI — all sharing the same tool protocol.
---

## Quick Start

```bash
# Install
pip install -e "."

# Initialize & index your project
cd /path/to/your-project
codex init
codex index .
codex doctor

# Search your code
codex search "authentication middleware"

# AI-powered analysis
codex ask "How does the auth flow work?"
codex quality src/
codex hotspots
```

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

## Next Steps

- [Installation](guide/installation) — Get CodexA running in under a minute
- [Quick Start](guide/quickstart) — Index a project and start searching
- [CLI Reference](reference/cli) — All 36 commands documented
- [Architecture](reference/architecture) — System design and package map
- [Plugin System](features/plugin-system) — Extend CodexA with custom hooks
- [API Reference](reference/api) — REST, Bridge, MCP, and Python APIs
