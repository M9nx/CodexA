# CodexA v0.4.0 — First Stable Public Release

**CodexA** is a developer intelligence engine for semantic code search, AI-assisted code understanding, and agent tooling.

## What's New

v0.4.0 is the first stable release of CodexA, focused on packaging, stability, and usability.

## Installation

```bash
pip install codexa
```

Or from source:

```bash
git clone https://github.com/M9nx/CodexA.git
cd CodexA
pip install -e "."
```

Verify:

```bash
codexa --version
# codexa, version 0.4.0
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

## Key Features

### Semantic Code Search
Natural-language search powered by sentence-transformers + FAISS vector index. Find code by meaning, not just keywords.

```bash
codexa search "jwt authentication middleware"
codexa search "database connection pooling" --json
```

### Multi-Mode Search
Semantic, keyword (BM25), regex, hybrid (RRF), and raw filesystem grep with full ripgrep compatibility.

```bash
codexa search "error handling" --mode hybrid
codexa grep "TODO|FIXME" -n
```

### Tree-Sitter Language Parsing
AST-based parsing for 11 languages: Python, JavaScript, TypeScript, TSX, Java, Go, Rust, C++, C#, Ruby, PHP.

```bash
codexa languages --check
```

### AI Agent Integration
13 built-in tools exposed via CLI, HTTP bridge, MCP server, and MCP-over-SSE for AI coding assistants.

```bash
codexa tool list --json
codexa serve --port 24842       # HTTP bridge
codexa mcp --path /your/project # MCP server for Claude/Cursor
```

### Code Quality & Metrics
Complexity analysis (Radon), security scanning (Bandit), hotspot detection, impact analysis, and CI quality gates.

```bash
codexa quality src/
codexa hotspots
codexa gate
```

### Plugin Architecture
22 hook points for extending every layer — indexing, search, analysis, AI, and output.

```bash
codexa plugin list
codexa plugin scaffold my-plugin
```

### 39 CLI Commands
Unix-style developer tool with `--json`, `--pipe`, and `--verbose` flags on every command.

## Stats

| Metric | Value |
|--------|-------|
| CLI Commands | 39 |
| AI Agent Tools | 13 |
| Plugin Hooks | 22 |
| Parsed Languages | 11 |
| Tests | 2595 |
| Python | >= 3.11 |

## Documentation

Full documentation: [codex-a.dev](https://codex-a.dev)

## License

MIT
