# Introduction

CodexA is a **developer intelligence engine** — a comprehensive CLI tool that brings
semantic code search, AI-assisted understanding, and workspace tooling to your
development workflow. It's designed for:

- **AI agents** that need reliable code search and analysis via MCP, HTTP bridge, or CLI
- **Developers** who want to find code by what it does, not just what it's named
- **Teams** exploring large codebases and understanding unfamiliar code
- **CI pipelines** that need automated quality gates and impact analysis

## Key Capabilities

### Semantic Search

Find code by concept, not keywords:

```bash
codexa search "error handling"
codexa search "authentication middleware"
codexa search "database connection pooling"
```

### 36 CLI Commands

Comprehensive tooling from the terminal:

```bash
codexa quality src/          # Code quality analysis
codexa hotspots              # Find high-risk code
codexa impact                # Blast radius analysis
codexa explain MyClass       # Structural explanation
```

### AI Agent Integration

Built-in tool protocol for AI coding assistants:

```bash
codexa tool run semantic_search --arg query="auth" --json
codexa serve --port 24842     # HTTP bridge
codexa mcp                    # MCP server for Claude/Cursor
```

### Quality & Metrics

Full quality pipeline with CI integration:

```bash
codexa quality src/           # Radon complexity + Bandit security
codexa gate                   # Pass/fail quality gates
codexa metrics --trend        # Track quality over time
```

## How It Works

1. **Indexing** — CodexA scans source files, parses ASTs with tree-sitter, extracts symbols, and chunks code
2. **Embedding** — Each chunk is converted to a 384-dimensional vector using sentence-transformers
3. **Storage** — Vectors stored in FAISS index, symbols in a registry, metadata in JSON
4. **Search** — Queries encoded to vectors, similar chunks found via cosine similarity, fused with BM25 keyword search
5. **Analysis** — Call graphs, dependency maps, quality metrics, and impact analysis built on top of the index

## Why CodexA?

### vs. grep/ripgrep

- Understands code meaning, not just text patterns
- Finds related code even with different terminology
- Quality analysis, hotspots, impact analysis built-in
- AI agent integration via MCP/HTTP/CLI

### vs. IDE search

- Works across entire codebase from the command line
- Scriptable and automatable for CI/CD
- Semantic understanding beyond symbol search
- 8 structured tools for AI agents

### vs. cloud code search

- 100% offline — no code leaves your machine
- No API keys or subscriptions required
- Fast local inference with sentence-transformers
- Privacy-first design

## Design Philosophy

- **Stdlib-first** — Minimal dependencies, Python 3.11+ only
- **Structured output** — Every command supports `--json` for machine consumption
- **Plugin-extensible** — 22 hooks for customization
- **AI-native** — Built for both humans and AI agents
- **Quality-aware** — Complexity, security, and maintainability analysis built-in

## Next Steps

- [Install CodexA](installation) and get running in under a minute
- [Quick Start](quickstart) — Index a project and start searching
- [AI Agent Setup](ai-agent-setup) — Integrate with Copilot, Claude, or Cursor
- [CLI Reference](../reference/cli) — All 36 commands documented
