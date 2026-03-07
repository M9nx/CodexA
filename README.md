# Codex — Semantic Code Intelligence

Local semantic code search and AI-assisted code understanding.

Codex is a CLI tool that indexes codebases, performs semantic search, and provides
structured code context for AI integration. It runs fully locally and is optimized
for developer productivity.

## Features

- **Code Indexing** — Scan repositories, extract functions/classes, generate embeddings
- **Semantic Search** — Natural language search across your codebase
- **Code Context** — Get surrounding code, imports, dependencies, and call graphs
- **Repository Analysis** — Language breakdown, module summaries, component detection
- **AI Integration** — JSON output mode for programmatic consumption

## Quick Start

### Install

```bash
pip install -e .
```

### Initialize a Project

```bash
codex init
```

### Index the Codebase

```bash
codex index .
```

### Semantic Search

```bash
codex search "jwt verification"
codex search "database connection" --json
codex search "error handling" -k 5
```

## CLI Commands

| Command                  | Description                              |
|--------------------------|------------------------------------------|
| `codex init [path]`     | Initialize project for indexing           |
| `codex index [path]`    | Index codebase for semantic search        |
| `codex search "<query>"`| Search with natural language              |
| `codex context <symbol>`| Get context for a symbol (Phase 5)        |
| `codex summarize`       | Generate repository summary (Phase 6)     |
| `codex stats`           | Show indexing statistics (Phase 6)        |

## Architecture

```
CLI Layer           → click commands
Command Layer       → router dispatches to services
Service Layer       → business logic
Parsing Engine      → tree-sitter code parsing
Embedding Engine    → sentence-transformers vectors
Search Engine       → FAISS similarity search
Analysis Engine     → call graphs, dependency maps
Storage Layer       → embeddings, metadata, cache
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with verbose output
codex --verbose search "query"
```

## Tech Stack

- **Python 3.11+**
- **click** — CLI framework
- **sentence-transformers** — Embedding generation
- **faiss-cpu** — Vector similarity search
- **tree-sitter** — Code parsing
- **pydantic** — Configuration & data models
- **rich** — Terminal UI

## License

MIT
