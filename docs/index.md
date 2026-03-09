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
  - icon:
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
    title: Semantic Search
    details: Natural-language code search powered by sentence-transformers and FAISS. Find code by meaning, not just keywords — queries are embedded into vectors and matched against your entire codebase.
  - icon:
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>'
    title: AI Agent Protocol
    details: 8 structured tools invocable via CLI, HTTP bridge, MCP, or Python API. Designed for autonomous AI coding agents with structured JSON input/output.
  - icon:
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 10.5V7c0-1.38-1.12-2.5-2.5-2.5S12 5.62 12 7v3.5"/><path d="M7 10.5V7c0-1.38 1.12-2.5 2.5-2.5"/><path d="m2 19 5-5"/><path d="m7 19 5-5"/><path d="m12 19 5-5"/><path d="m17 19 5-5"/></svg>'
    title: Multi-Language Parsing
    details: Tree-sitter AST parsing for 12 languages — Python, TypeScript, Rust, Go, Java, C/C++, and more. Extracts symbols, call graphs, and dependency maps.
  - icon:
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>'
    title: Quality & Metrics
    details: Cyclomatic complexity via Radon, security scanning via Bandit, hotspot detection combining churn and complexity, blast-radius impact analysis, and CI quality gates.
  - icon:
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15.6 2.7a10 10 0 1 0 5.7 5.7"/><circle cx="12" cy="12" r="2"/><path d="M13.4 10.6 19 5"/></svg>'
    title: Plugin System
    details: 22 hook points across the full pipeline — indexing, search, analysis, AI, and output. Build custom plugins with a simple Python API and automatic discovery.
  - icon:
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>'
    title: Self-Improving Loop
    details: Budget-aware evolution engine that autonomously discovers issues, generates patches, validates with tests, and commits improvements to your codebase.
  - icon:
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/></svg>'
    title: 36 CLI Commands
    details: Comprehensive Click-based CLI with --json, --pipe, and --verbose flags. Every command returns structured output suitable for scripting and automation.
  - icon:
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>'
    title: Multiple Interfaces
    details: CLI, Web UI, REST API, Bridge Server, MCP Server, LSP Server, and interactive TUI — all built on the same tool protocol for consistent behavior everywhere.
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
