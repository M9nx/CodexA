# Installation

## Requirements

- **Python 3.11+** (3.12 recommended)
- **pip** or **uv** package manager
- **Git** (for version-controlled projects)

## Install from PyPI

```bash
pip install codexa
```

## Install from Source

```bash
git clone https://github.com/M9nx/CodexA.git
cd CodexA
pip install -e "."
```

## Install via Docker

```bash
docker build -t codexa .
docker run --rm -v /path/to/project:/workspace codexa search "auth"
```

The Docker image includes ripgrep, git, and a pre-loaded embedding model.

## Install via Homebrew (macOS)

```bash
brew install --formula Formula/codexa.rb
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
codexa --version
# codexa 0.4.0

codexa doctor
# Checks environment health
```

## First-Time Setup

Initialize CodexA in your project:

```bash
cd /path/to/your-project
codexa init
```

This creates a `.codexa/` directory with:

```
.codexa/
├── config.json     # Configuration (embedding, search, LLM settings)
├── index/          # FAISS vector index (after indexing)
├── cache/          # Query and embedding caches
└── plugins/        # Custom plugins directory
```

## LLM Configuration (Optional)

For AI-powered commands (`ask`, `review`, `refactor`, `chat`, etc.), configure an LLM provider in `.codexa/config.json`:

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
