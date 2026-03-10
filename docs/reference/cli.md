# CLI Reference

Auto-generated from the registered Click command tree. All commands support `--json` for machine-readable output.

## Core Commands

### `codexa init`

Initialize a project for semantic code indexing. Creates a `.codexa/` directory with default configuration.

```bash
codexa init [PATH]
codexa init --index          # Init + build index
codexa init --vscode         # Init + VS Code MCP config
codexa init --index --vscode # Full setup in one command
```

### `codexa index`

Index a codebase for semantic search. Scans files, extracts chunks, generates embeddings.

```bash
codexa index .
codexa index . --force    # Full re-index
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--force` | boolean | false | Force full re-index, ignoring cache |

### `codexa doctor`

Check environment health, dependencies, and project status.

```bash
codexa doctor
codexa doctor --json
```

## Search & Discovery

### `codexa search`

Search the indexed codebase using a natural language query.

```bash
codexa search "jwt verification"
codexa search "database connection" --mode hybrid
codexa search "def\s+authenticate" --mode regex -n
codexa search "error handling" --mode keyword --full-section
codexa search "TODO" --mode regex -l
codexa search "pattern" --jsonl | jq .file_path
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | — | Number of results |
| `--json-output, --json` | boolean | false | JSON output |
| `--jsonl` | boolean | false | One JSON object per line |
| `--mode, -m` | choice | semantic | `semantic`, `keyword`, `regex`, or `hybrid` |
| `--full-section, --full` | boolean | false | Show full enclosing function/class |
| `--no-auto-index` | boolean | false | Disable automatic indexing |
| `--case-sensitive, -s` | boolean | false | Case-sensitive (regex only) |
| `--context-lines, -C` | integer | 0 | Context lines around matches |
| `--files-only, -l` | boolean | false | Print only file paths (grep -l) |
| `--files-without-match, -L` | boolean | false | Print paths without matches (grep -L) |
| `--line-numbers, -n` | boolean | false | Prefix with line numbers (grep -n) |
| `--path, -p` | directory | . | Project root path |

### `codexa explain`

Explain a code symbol or all symbols in a file.

```bash
codexa explain MyClass -f src/models.py
codexa explain --file src/main.py .
codexa explain search_codebase --json
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--file, -f` | path | — | Source file containing the symbol |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codexa context`

Generate structured context for external AI pipelines.

```bash
codexa context query "authentication"
codexa context symbol MyClass
codexa context file src/main.py
codexa context repo
```

Modes: `query` (semantic search), `symbol` (symbol context), `file` (file context), `repo` (repo summary).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | 5 | Results for query mode |
| `--file-path, -f` | text | — | File path hint (symbol mode) |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codexa deps`

Show the dependency/import map for a file or project.

```bash
codexa deps src/main.py
codexa deps . --json
```

### `codexa summary`

Generate a structured summary of the repository.

```bash
codexa summary
codexa summary --json
```

## AI-Powered Commands

### `codexa ask`

Ask a natural-language question about the codebase.

```bash
codexa ask "How does authentication work?"
codexa ask "What does search_codebase do?" --json
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | 5 | Context snippets to retrieve |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codexa chat`

Multi-turn conversation about the codebase.

```bash
codexa chat "How does auth work?"
codexa chat --session my-session "Follow up"
codexa chat --list-sessions
codexa chat --stream "Explain the flow"
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--session, -s` | text | — | Session ID to resume |
| `--list-sessions` | boolean | false | List all sessions |
| `--max-turns, -t` | integer | 20 | Max conversation turns |
| `--stream` | boolean | false | Stream tokens |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codexa investigate`

Autonomous multi-step investigation to answer a question.

```bash
codexa investigate "Find all security vulnerabilities"
codexa investigate "How is payment flow implemented?" --max-steps 10
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-steps, -n` | integer | 6 | Maximum steps before conclusion |
| `--stream` | boolean | false | Stream conclusion tokens |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codexa review`

AI-assisted code review.

```bash
codexa review src/main.py
codexa review src/utils.py --json
```

### `codexa refactor`

AI-powered refactoring suggestions.

```bash
codexa refactor src/main.py
codexa refactor src/utils.py -i "Extract duplicated logic"
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--instruction, -i` | text | Improve quality | Refactoring instruction |
| `--json-output, --json` | boolean | false | JSON output |

### `codexa suggest`

Intelligent suggestions for a symbol, file, or topic.

```bash
codexa suggest search_codebase
codexa suggest "error handling patterns" --json
```

### `codexa cross-refactor`

Find duplicate logic across workspace repos.

```bash
codexa cross-refactor --threshold 0.70
```

## Quality & Metrics

### `codexa quality`

Analyze code quality — complexity, dead code, duplicates, security.

```bash
codexa quality
codexa quality --json
codexa quality --safety-only --pipe
codexa quality --complexity-threshold 15
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--complexity-threshold` | integer | 10 | Min complexity to report |
| `--safety-only` | boolean | false | Security-only fast mode |
| `--json-output, --json` | boolean | false | JSON output |
| `--pipe` | boolean | false | Plain text for CI |
| `--path, -p` | directory | . | Project root path |

### `codexa metrics`

Compute quality metrics, save snapshots, track trends.

```bash
codexa metrics
codexa metrics --snapshot --json
codexa metrics --history 10
codexa metrics --trend
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--snapshot` | boolean | false | Save a quality snapshot |
| `--history` | integer | 0 | Show last N snapshots |
| `--trend` | boolean | false | Show trend analysis |
| `--json-output, --json` | boolean | false | JSON output |
| `--pipe` | boolean | false | Plain text for CI |

### `codexa gate`

Enforce quality gates for CI.

```bash
codexa gate --strict
codexa gate --min-maintainability 60 --max-complexity 15
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--min-maintainability` | float | 40.0 | Min MI score |
| `--max-complexity` | integer | 25 | Max complexity |
| `--max-issues` | integer | 20 | Max total issues |
| `--strict` | boolean | false | Exit code 1 on failure |

### `codexa hotspots`

Identify high-risk code hotspots.

```bash
codexa hotspots
codexa hotspots --top-n 10 --json
codexa hotspots --no-git --pipe
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-n, -n` | integer | 20 | Number of hotspots |
| `--include-git / --no-git` | boolean | true | Include git churn |

### `codexa impact`

Analyze blast radius of a change.

```bash
codexa impact parse_file
codexa impact src/parser.py --json
codexa impact MyClass --max-depth 3 --pipe
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-depth, -d` | integer | 5 | BFS depth limit |

### `codexa trace`

Trace execution relationships for a symbol.

```bash
codexa trace parse_file
codexa trace MyClass.process --json
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-depth, -d` | integer | 5 | Traversal depth |

### `codexa pr-summary`

Generate a Pull Request intelligence report.

```bash
codexa pr-summary
codexa pr-summary --json
codexa pr-summary -f src/main.py -f src/utils.py
```

## Servers & Integration

### `codexa serve`

Start the HTTP bridge server for AI agents.

```bash
codexa serve --port 24842
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host, -h` | text | 127.0.0.1 | Host to bind |
| `--port, -p` | integer | 24842 | Port to bind |
| `--path` | directory | . | Project root |

### `codexa web`

Start the web interface and REST API.

```bash
codexa web
codexa web --port 9000 --host 0.0.0.0
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host, -h` | text | 127.0.0.1 | Host to bind |
| `--port, -p` | integer | 8080 | Port to bind |
| `--path` | directory | . | Project root |

### `codexa mcp`

Start the MCP server for Claude/Cursor. Exposes 11 tools.

```bash
codexa mcp --path /your/project
```

## Performance & Diagnostics

### `codexa grep`

Search raw files using regex — no index required.

```bash
codexa grep "TODO|FIXME"
codexa grep "def authenticate" -g "*.py"
codexa grep "password" --case-sensitive
codexa grep "import re" --json
codexa grep "class.*Service" -l
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Root directory to search |
| `--case-sensitive, -s` | flag | false | Case-sensitive matching |
| `--max-results, -n` | integer | 100 | Max matches |
| `--glob, -g` | text | *(none)* | File glob filter (e.g. `*.py`) |
| `--no-ripgrep` | flag | false | Force pure-Python search |
| `--json` | flag | false | JSON output |
| `--files-only, -l` | flag | false | Print only file paths |

### `codexa benchmark`

Performance benchmarking — indexing speed, search latency, memory usage.

```bash
codexa benchmark
codexa benchmark --json
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root |
| `--json` | flag | false | JSON output |
```

### `codexa lsp`

Start the Language Server Protocol server (stdio).

```bash
codexa lsp --path /your/project
```

### `codexa tui`

Interactive terminal search interface.

```bash
codexa tui
codexa tui --mode hybrid -k 20
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mode, -m` | choice | hybrid | Default search mode |
| `--top-k, -k` | integer | 10 | Results per query |

## Code Generation & Automation

### `codexa evolve`

Run the self-improving development loop.

```bash
codexa evolve
codexa evolve --iterations 5 --budget 50000
codexa evolve --timeout 300
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--iterations, -n` | integer | 3 | Max improvement iterations |
| `--budget, -b` | integer | 20000 | Max total tokens |
| `--timeout, -t` | integer | 600 | Max wall-clock seconds |

### `codexa ci-gen`

Generate CI/CD workflow templates.

```bash
codexa ci-gen analysis       # Full analysis workflow
codexa ci-gen safety         # Lightweight safety-only
codexa ci-gen precommit      # Pre-commit hook config
```

### `codexa docs`

Generate documentation for CodexA components.

```bash
codexa docs
codexa docs --section plugins -o reference/
```

### `codexa viz`

Generate Mermaid diagrams from codebase analysis.

```bash
codexa viz callgraph
codexa viz deps --target src/main.py
codexa viz symbols --target auth.py
codexa viz workspace
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--target, -t` | text | — | Symbol or file to visualize |
| `--output, -o` | file | — | Write to file instead of stdout |

### `codexa watch`

Watch for changes and re-index automatically.

```bash
codexa watch
codexa watch --interval 5
```

## Model Management

### `codexa models list`

List available embedding models.

### `codexa models info <name>`

Show detailed model information.

### `codexa models download <name>`

Pre-download a model for offline use.

### `codexa models switch <name>`

Switch active embedding model (requires re-index).

## Plugin Management

### `codexa plugin list`

List discovered plugins.

### `codexa plugin info <name>`

Show plugin details.

### `codexa plugin new <name>`

Scaffold a new plugin from template.

```bash
codexa plugin new my-formatter
codexa plugin new lint-checker --hooks CUSTOM_VALIDATION,POST_AI
codexa plugin new metrics -o ./plugins/ -a "Your Name"
```

## Workspace Management

### `codexa workspace init`

Initialize a new workspace.

### `codexa workspace add <name> <path>`

Register a repository in the workspace.

### `codexa workspace list`

List all registered repositories.

### `codexa workspace remove <name>`

Unregister a repository.

### `codexa workspace index`

Index workspace repositories.

### `codexa workspace search <query>`

Search across all workspace repos.

```bash
codexa workspace search "authentication" --top-k 10 --json
codexa workspace search "auth" --repo backend --repo frontend
```
