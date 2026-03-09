# Installation

## Requirements

- **Python 3.11+** (3.12 recommended)
- **pip** or **uv** package manager
- **Git** (for version-controlled projects)

## Install from Source

```bash
git clone https://github.com/M9nx/CodexA.git
cd CodexA
pip install -e "."
```

## Optional Extras

Install with optional dependencies for additional features:

::: code-group

```bash [Development]
pip install -e ".[dev]"
# Includes: pytest, pytest-cov
```

```bash [TUI]
pip install -e ".[tui]"
# Includes: textual (interactive terminal UI)
```

```bash [Everything]
pip install -e ".[dev,tui]"
```

:::

## Verify Installation

```bash
codex --version
# codex-ai 0.29.0

codex doctor
# Checks environment health
```

## First-Time Setup

Initialize CodexA in your project:

```bash
cd /path/to/your-project
codex init
```

This creates a `.codex/` directory with:

```
.codex/
├── config.json     # Configuration (embedding, search, LLM settings)
├── index/          # FAISS vector index (after indexing)
├── cache/          # Query and embedding caches
└── plugins/        # Custom plugins directory
```

## LLM Configuration (Optional)

For AI-powered commands (`ask`, `review`, `refactor`, `chat`, etc.), configure an LLM provider in `.codex/config.json`:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "sk-...",
    "temperature": 0.2,
    "max_tokens": 2048
  }
}
```

Supported providers: `openai`, `ollama` (local), `mock` (testing).

## Next Steps

- [Quick Start](quickstart) — Index a project and start searching
- [Configuration](configuration) — Full configuration reference
- [AI Agent Setup](ai-agent-setup) — Integrate with VS Code Copilot
