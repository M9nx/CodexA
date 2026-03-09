# Contributing

This guide covers everything you need to contribute to CodexA — from setting up your development environment to submitting pull requests.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/M9nx/CodexA.git
cd CodexA

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # macOS/Linux

# Install in development mode with all extras
pip install -e ".[dev]"
pip install -r requirements.txt
```

## Running Tests

CodexA has 2595+ tests covering the full codebase:

```bash
# Run all tests
pytest

# Run with coverage (70% minimum gate)
pytest --cov=semantic_code_intelligence

# Run a specific test file
pytest semantic_code_intelligence/tests/test_phase23.py -v

# Type checking
mypy semantic_code_intelligence --exclude "tests/"
```

## Project Structure

```
CodexA/
├── semantic_code_intelligence/     # Main package
│   ├── analysis/                   # AI features & code explanations
│   ├── bridge/                     # HTTP bridge & IDE integration
│   ├── ci/                         # Quality analysis, metrics, hotspots, impact
│   ├── cli/                        # Click-based CLI commands
│   │   └── commands/               # Individual command modules
│   ├── config/                     # Pydantic-based configuration
│   ├── context/                    # Context engine, call graph, deps
│   ├── daemon/                     # File watcher daemon
│   ├── docs/                       # Auto-documentation generator
│   ├── embeddings/                 # Sentence-transformer embeddings
│   ├── evolution/                  # Self-improving development loop
│   ├── indexing/                   # Scanner, chunker, semantic chunker
│   ├── llm/                        # LLM providers & reasoning engine
│   ├── lsp/                        # Language Server Protocol server
│   ├── mcp/                        # Model Context Protocol server
│   ├── parsing/                    # Tree-sitter parser (12 languages)
│   ├── plugins/                    # Plugin SDK & hook system (22 hooks)
│   ├── scalability/                # Batch processing utilities
│   ├── search/                     # Search backends & formatting
│   ├── services/                   # Indexing & search service layer
│   ├── storage/                    # FAISS vector store & hash store
│   ├── tools/                      # AI tool-calling interface (8 tools)
│   ├── tui/                        # Textual TUI & fallback REPL
│   ├── utils/                      # Logging & shared utilities
│   ├── web/                        # Web UI, REST API, visualization
│   ├── workspace/                  # Multi-repo workspace management
│   └── tests/                      # All test files (2595+ tests)
├── vscode-extension/               # VS Code sidebar extension
├── docs/                           # VitePress documentation
├── pyproject.toml                  # Package metadata & build config
├── requirements.txt                # Pinned dependencies
├── ROADMAP.md                      # Planned features
└── CHANGELOG.md                    # Release history
```

## Development Workflow

### Adding a CLI Command

1. Create `semantic_code_intelligence/cli/commands/your_cmd.py`
2. Define a Click command:
   ```python
   import click
   
   @click.command("your-name")
   @click.option("--json", "as_json", is_flag=True)
   def your_cmd(as_json):
       """Short description of the command."""
       pass
   ```
3. Register it in `semantic_code_intelligence/cli/router.py`
4. Add tests in `semantic_code_intelligence/tests/`

### Adding a Plugin Hook

1. Add the hook to `PluginHook` enum in `semantic_code_intelligence/plugins/__init__.py`
2. Add dispatch calls at the appropriate point in the pipeline
3. Document the hook's data contract (what keys the `data` dict contains)
4. Update the hook count in tests (`test_all_hooks_count`)

### Writing a Plugin

```python
from semantic_code_intelligence.plugins import PluginBase, PluginHook, PluginMetadata

class MyPlugin(PluginBase):
    def metadata(self):
        return PluginMetadata(
            name="my-plugin",
            version="0.1.0",
            description="Does something useful",
            hooks=[PluginHook.POST_SEARCH],
        )

    def on_hook(self, hook, data):
        # Modify and return data
        return data

def create_plugin():
    return MyPlugin()
```

Place plugin files in `.codex/plugins/` for automatic discovery, or register programmatically via `PluginManager`.

## Code Style

- Python 3.11+ with type hints throughout
- Use `from __future__ import annotations` in every module
- Docstrings for public classes and functions
- Import from `semantic_code_intelligence.utils.logging` for consistent output
- Keep modules focused — one responsibility per file

## Writing Tests

- Use **pytest** with the AAA pattern (Arrange-Act-Assert)
- Place tests in `semantic_code_intelligence/tests/`
- Use `tmp_path` fixture for file system tests
- Mock external dependencies (LLM providers, embeddings)

```bash
# Run specific tests
pytest semantic_code_intelligence/tests/test_your_file.py -v

# Run with output
pytest -s semantic_code_intelligence/tests/test_your_file.py
```

## Submitting Changes

1. Fork the repository and create a feature branch
2. Make your changes with tests
3. Ensure all tests pass: `pytest`
4. Commit with a clear message following the convention below
5. Open a pull request against `main`

### Commit Convention

```
<type>: <short description>

<optional body>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

## Building Documentation

The docs use [VitePress](https://vitepress.dev/):

```bash
npm run docs:dev      # Dev server at localhost:5173
npm run docs:build    # Production build
npm run docs:preview  # Preview production build
```

## Reporting Issues

- Use GitHub Issues with the provided templates
- Include: Python version, OS, CodexA version (`codex --version`), and steps to reproduce
- For security vulnerabilities, see [SECURITY.md](https://github.com/M9nx/CodexA/blob/main/SECURITY.md)
