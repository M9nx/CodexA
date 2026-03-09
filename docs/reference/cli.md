# CLI Reference

Auto-generated from the registered Click command tree. All commands support `--json` for machine-readable output.

## Core Commands

### `codex init`

Initialize a project for semantic code indexing. Creates a `.codex/` directory with default configuration.

```bash
codex init [PATH]
```

### `codex index`

Index a codebase for semantic search. Scans files, extracts chunks, generates embeddings.

```bash
codex index .
codex index . --force    # Full re-index
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--force` | boolean | false | Force full re-index, ignoring cache |

### `codex doctor`

Check environment health, dependencies, and project status.

```bash
codex doctor
codex doctor --json
```

## Search & Discovery

### `codex search`

Search the indexed codebase using a natural language query.

```bash
codex search "jwt verification"
codex search "database connection" --mode hybrid
codex search "def\s+authenticate" --mode regex -n
codex search "error handling" --mode keyword --full-section
codex search "TODO" --mode regex -l
codex search "pattern" --jsonl | jq .file_path
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

### `codex explain`

Explain a code symbol or all symbols in a file.

```bash
codex explain MyClass -f src/models.py
codex explain --file src/main.py .
codex explain search_codebase --json
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--file, -f` | path | — | Source file containing the symbol |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codex context`

Generate structured context for external AI pipelines.

```bash
codex context query "authentication"
codex context symbol MyClass
codex context file src/main.py
codex context repo
```

Modes: `query` (semantic search), `symbol` (symbol context), `file` (file context), `repo` (repo summary).

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | 5 | Results for query mode |
| `--file-path, -f` | text | — | File path hint (symbol mode) |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codex deps`

Show the dependency/import map for a file or project.

```bash
codex deps src/main.py
codex deps . --json
```

### `codex summary`

Generate a structured summary of the repository.

```bash
codex summary
codex summary --json
```

## AI-Powered Commands

### `codex ask`

Ask a natural-language question about the codebase.

```bash
codex ask "How does authentication work?"
codex ask "What does search_codebase do?" --json
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | 5 | Context snippets to retrieve |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codex chat`

Multi-turn conversation about the codebase.

```bash
codex chat "How does auth work?"
codex chat --session my-session "Follow up"
codex chat --list-sessions
codex chat --stream "Explain the flow"
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--session, -s` | text | — | Session ID to resume |
| `--list-sessions` | boolean | false | List all sessions |
| `--max-turns, -t` | integer | 20 | Max conversation turns |
| `--stream` | boolean | false | Stream tokens |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codex investigate`

Autonomous multi-step investigation to answer a question.

```bash
codex investigate "Find all security vulnerabilities"
codex investigate "How is payment flow implemented?" --max-steps 10
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-steps, -n` | integer | 6 | Maximum steps before conclusion |
| `--stream` | boolean | false | Stream conclusion tokens |
| `--json-output, --json` | boolean | false | JSON output |
| `--path, -p` | directory | . | Project root path |

### `codex review`

AI-assisted code review.

```bash
codex review src/main.py
codex review src/utils.py --json
```

### `codex refactor`

AI-powered refactoring suggestions.

```bash
codex refactor src/main.py
codex refactor src/utils.py -i "Extract duplicated logic"
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--instruction, -i` | text | Improve quality | Refactoring instruction |
| `--json-output, --json` | boolean | false | JSON output |

### `codex suggest`

Intelligent suggestions for a symbol, file, or topic.

```bash
codex suggest search_codebase
codex suggest "error handling patterns" --json
```

### `codex cross-refactor`

Find duplicate logic across workspace repos.

```bash
codex cross-refactor --threshold 0.70
```

## Quality & Metrics

### `codex quality`

Analyze code quality — complexity, dead code, duplicates, security.

```bash
codex quality
codex quality --json
codex quality --safety-only --pipe
codex quality --complexity-threshold 15
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--complexity-threshold` | integer | 10 | Min complexity to report |
| `--safety-only` | boolean | false | Security-only fast mode |
| `--json-output, --json` | boolean | false | JSON output |
| `--pipe` | boolean | false | Plain text for CI |
| `--path, -p` | directory | . | Project root path |

### `codex metrics`

Compute quality metrics, save snapshots, track trends.

```bash
codex metrics
codex metrics --snapshot --json
codex metrics --history 10
codex metrics --trend
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--snapshot` | boolean | false | Save a quality snapshot |
| `--history` | integer | 0 | Show last N snapshots |
| `--trend` | boolean | false | Show trend analysis |
| `--json-output, --json` | boolean | false | JSON output |
| `--pipe` | boolean | false | Plain text for CI |

### `codex gate`

Enforce quality gates for CI.

```bash
codex gate --strict
codex gate --min-maintainability 60 --max-complexity 15
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--min-maintainability` | float | 40.0 | Min MI score |
| `--max-complexity` | integer | 25 | Max complexity |
| `--max-issues` | integer | 20 | Max total issues |
| `--strict` | boolean | false | Exit code 1 on failure |

### `codex hotspots`

Identify high-risk code hotspots.

```bash
codex hotspots
codex hotspots --top-n 10 --json
codex hotspots --no-git --pipe
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-n, -n` | integer | 20 | Number of hotspots |
| `--include-git / --no-git` | boolean | true | Include git churn |

### `codex impact`

Analyze blast radius of a change.

```bash
codex impact parse_file
codex impact src/parser.py --json
codex impact MyClass --max-depth 3 --pipe
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-depth, -d` | integer | 5 | BFS depth limit |

### `codex trace`

Trace execution relationships for a symbol.

```bash
codex trace parse_file
codex trace MyClass.process --json
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-depth, -d` | integer | 5 | Traversal depth |

### `codex pr-summary`

Generate a Pull Request intelligence report.

```bash
codex pr-summary
codex pr-summary --json
codex pr-summary -f src/main.py -f src/utils.py
```

## Servers & Integration

### `codex serve`

Start the HTTP bridge server for AI agents.

```bash
codex serve --port 24842
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host, -h` | text | 127.0.0.1 | Host to bind |
| `--port, -p` | integer | 24842 | Port to bind |
| `--path` | directory | . | Project root |

### `codex web`

Start the web interface and REST API.

```bash
codex web
codex web --port 9000 --host 0.0.0.0
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host, -h` | text | 127.0.0.1 | Host to bind |
| `--port, -p` | integer | 8080 | Port to bind |
| `--path` | directory | . | Project root |

### `codex mcp`

Start the MCP server for Claude/Cursor.

```bash
codex mcp --path /your/project
```

### `codex lsp`

Start the Language Server Protocol server (stdio).

```bash
codex lsp --path /your/project
```

### `codex tui`

Interactive terminal search interface.

```bash
codex tui
codex tui --mode hybrid -k 20
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mode, -m` | choice | hybrid | Default search mode |
| `--top-k, -k` | integer | 10 | Results per query |

## Code Generation & Automation

### `codex evolve`

Run the self-improving development loop.

```bash
codex evolve
codex evolve --iterations 5 --budget 50000
codex evolve --timeout 300
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--iterations, -n` | integer | 3 | Max improvement iterations |
| `--budget, -b` | integer | 20000 | Max total tokens |
| `--timeout, -t` | integer | 600 | Max wall-clock seconds |

### `codex ci-gen`

Generate CI/CD workflow templates.

```bash
codex ci-gen analysis       # Full analysis workflow
codex ci-gen safety         # Lightweight safety-only
codex ci-gen precommit      # Pre-commit hook config
```

### `codex docs`

Generate documentation for CodexA components.

```bash
codex docs
codex docs --section plugins -o reference/
```

### `codex viz`

Generate Mermaid diagrams from codebase analysis.

```bash
codex viz callgraph
codex viz deps --target src/main.py
codex viz symbols --target auth.py
codex viz workspace
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--target, -t` | text | — | Symbol or file to visualize |
| `--output, -o` | file | — | Write to file instead of stdout |

### `codex watch`

Watch for changes and re-index automatically.

```bash
codex watch
codex watch --interval 5
```

## Model Management

### `codex models list`

List available embedding models.

### `codex models info <name>`

Show detailed model information.

### `codex models download <name>`

Pre-download a model for offline use.

### `codex models switch <name>`

Switch active embedding model (requires re-index).

## Plugin Management

### `codex plugin list`

List discovered plugins.

### `codex plugin info <name>`

Show plugin details.

### `codex plugin new <name>`

Scaffold a new plugin from template.

```bash
codex plugin new my-formatter
codex plugin new lint-checker --hooks CUSTOM_VALIDATION,POST_AI
codex plugin new metrics -o ./plugins/ -a "Your Name"
```

## Workspace Management

### `codex workspace init`

Initialize a new workspace.

### `codex workspace add <name> <path>`

Register a repository in the workspace.

### `codex workspace list`

List all registered repositories.

### `codex workspace remove <name>`

Unregister a repository.

### `codex workspace index`

Index workspace repositories.

### `codex workspace search <query>`

Search across all workspace repos.

```bash
codex workspace search "authentication" --top-k 10 --json
codex workspace search "auth" --repo backend --repo frontend
```
