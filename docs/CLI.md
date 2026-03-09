# CLI Reference

Auto-generated from the registered Click command tree.

## `codex ask`

Ask a natural-language question about the codebase.

    Uses semantic search + LLM to answer questions about your code.

    Examples:

        codex ask "How does authentication work?"

        codex ask "What does the search_codebase function do?" --json

**Arguments:**

- `question` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | 5 | Number of context snippets to retrieve. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--path, -p` | directory | . | Project root path. |

---

## `codex chat`

Continue or start a multi-turn conversation about the codebase.

    Each conversation is persisted to disk so you can resume later with
    --session <id>.  Use --list-sessions to see saved conversations.

**Arguments:**

- `message` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--session, -s` | text |  | Session ID to resume. Creates a new session if not given. |
| `--list-sessions` | boolean | false | List all stored chat sessions and exit. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--max-turns, -t` | integer | 20 | Maximum conversation turns to send to LLM. |
| `--path, -p` | directory | . | Project root path. |
| `--stream` | boolean | false | Stream tokens incrementally as they arrive. |
| `--pipe` | boolean | false |  |

---

## `codex ci-gen`

Generate CI/CD workflow templates for CodexA integration.

    Available templates:

    - analysis  — Full analysis workflow (quality + PR summary)

    - safety    — Lightweight safety-only workflow

    - precommit — Pre-commit hook configuration

    Examples:

        codex ci-gen analysis

        codex ci-gen safety -o .github/workflows/codex-safety.yml

        codex ci-gen precommit -o .pre-commit-config.yaml

**Arguments:**

- `template` — choice

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output, -o` | text |  | Write output to a file instead of stdout. |
| `--python-version` | text | 3.12 | Python version for workflow (default: 3.12). |

---

## `codex context`

Generate structured context for external AI pipelines.

    
    Modes:
      query   — semantic search (TARGET = search query)
      symbol  — symbol context  (TARGET = symbol name)
      file    — file context    (TARGET = file path)
      repo    — repo summary    (no TARGET needed)

**Arguments:**

- `mode` — choice
- `target` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | 5 | Number of results for query mode. |
| `--file-path, -f` | text |  | File path hint (for symbol mode). |
| `--json-output, --json` | boolean | false | Output raw JSON (default is pretty-printed). |
| `--path, -p` | directory | . | Project root path. |

---

## `codex cross-refactor`

Analyse workspace repos for cross-repo refactoring opportunities.

    Scans all registered repositories in the workspace for duplicate logic,
    inconsistent patterns, and symbols that could be extracted into a shared
    library.  When an LLM is configured, generates actionable suggestions.

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--threshold, -t` | float | 0.7 | Similarity threshold for duplicate detection (0.0-1.0). |
| `--path, -p` | directory | . | Workspace root path. |
| `--pipe` | boolean | false |  |

---

## `codex deps`

Show the dependency/import map for a file or the whole project.

    TARGET can be a specific file path or '.' for the whole project.

    Examples:

        codex deps src/main.py

        codex deps .

        codex deps . --json

**Arguments:**

- `target` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |

---

## `codex docs`

Generate Markdown documentation for CodexA components.

    Produces auto-generated reference docs for CLI commands, plugin hooks,
    bridge protocol, and tool registry.

    Examples:

        codex docs

        codex docs --section plugins -o reference/

        codex docs --json

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output, -o` | directory | docs | Output directory for generated docs. |
| `--section, -s` | choice | all | Which documentation section to generate. |
| `--json-output, --json` | boolean | false | Output file list as JSON. |

---

## `codex doctor`

Check environment health, dependencies, and project status.

    Useful for debugging installation issues or verifying that all
    required packages are available.

    Examples:

        codex doctor

        codex doctor --json

        codex doctor -p /path/to/project

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output results in JSON format. |

---

## `codex evolve`

Run the self-improving development loop.

    Automatically selects small improvement tasks (fix tests, add type
    hints, improve error handling, reduce duplication) and applies them
    using the configured LLM.  Every change is tested; failures are
    reverted and successes are committed.

    Examples:

        codex evolve

        codex evolve --iterations 5 --budget 50000

        codex evolve --path /my/project --timeout 300

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--iterations, -n` | integer range | 3 | Maximum number of improvement iterations. |
| `--budget, -b` | integer range | 20000 | Maximum total tokens to spend across all LLM calls. |
| `--timeout, -t` | integer range | 600 | Maximum wall-clock seconds for the entire run. |
| `--path, -p` | directory | . | Project root path. |

---

## `codex explain`

Explain a code symbol or all symbols in a file.

    Examples:

        codex explain MyClass -f src/models.py

        codex explain --file src/main.py .

        codex explain search_codebase

**Arguments:**

- `target` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--file, -f` | path |  | Source file containing the symbol. |
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |

---

## `codex gate`

Enforce quality gates — fail CI builds that violate quality policies.

    Runs full quality analysis plus maintainability metrics and checks
    results against configurable thresholds.

    Examples:

        codex gate

        codex gate --strict --json

        codex gate --min-maintainability 60 --max-complexity 15

        codex gate --pipe --strict

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--pipe` | boolean | false | Plain text output for piping / CI. |
| `--min-maintainability` | float | 40.0 | Minimum maintainability index (default: 40). |
| `--max-complexity` | integer | 25 | Maximum allowed complexity (default: 25). |
| `--max-issues` | integer | 20 | Maximum allowed total issues (default: 20). |
| `--strict` | boolean | false | Exit with code 1 on gate failure (for CI). |

---

## `codex hotspots`

Identify high-risk code hotspots via multi-factor analysis.

    Combines complexity, duplication, fan-in/out, and git churn to
    score symbols by maintenance risk.

    Examples:

        codex hotspots

        codex hotspots --top-n 10 --json

        codex hotspots --no-git --pipe

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--pipe` | boolean | false | Plain text output for piping / CI. |
| `--top-n, -n` | integer | 20 | Number of hotspots to report (default: 20). |
| `--include-git, --no-git` | boolean | true | Include git churn data (default: enabled). |

---

## `codex impact`

Analyse the blast radius of a change to TARGET.

    TARGET can be a symbol name (function/class) or a file path relative
    to the project root.

    Examples:

        codex impact parse_file

        codex impact src/parser.py --json

        codex impact MyClass --max-depth 3 --pipe

**Arguments:**

- `target` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--pipe` | boolean | false | Plain text output for piping / CI. |
| `--max-depth, -d` | integer | 5 | Maximum traversal depth (default: 5). |

---

## `codex index`

Index a codebase for semantic search.

    Scans the target directory, extracts code chunks, generates embeddings,
    and stores them in the vector index.

**Arguments:**

- `path` — directory

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--force` | boolean | false | Force full re-index, ignoring cache. |

---

## `codex init`

Initialize a project for semantic code indexing.

    Creates a .codex/ directory with default configuration and an empty index.

**Arguments:**

- `path` — directory

---

## `codex investigate`

Run an autonomous multi-step investigation to answer a question.

    CodexA iteratively searches, analyses symbols, and examines dependencies
    until it can confidently answer your question.  Each step is visible
    so you can follow the reasoning chain.

**Arguments:**

- `question` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-steps, -n` | integer | 6 | Maximum investigation steps before forcing a conclusion. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--path, -p` | directory | . | Project root path. |
| `--stream` | boolean | false | Stream the conclusion tokens incrementally. |
| `--pipe` | boolean | false |  |

---

## `codex lsp`

Start the CodexA Language Server Protocol server.

    Runs over stdio using standard LSP Content-Length framing.
    Compatible with any LSP client: VS Code, Neovim, Sublime, JetBrains.

    
    VS Code settings.json:
      "codex.lsp.path": "/path/to/your/project"

    
    Neovim (nvim-lspconfig):
      require('lspconfig').codex.setup {
        cmd = { "codex", "lsp", "--path", "/your/project" },
      }

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |

---

## `codex mcp`

Start the MCP server for AI agent integration.

    Runs a JSON-RPC server over stdio, compatible with Claude Desktop,
    Cursor, and other MCP-compatible AI tools.

    
    Configuration for Claude Desktop (claude_desktop_config.json):
      {
        "mcpServers": {
          "codex": {
            "command": "codex",
            "args": ["mcp", "--path", "/your/project"]
          }
        }
      }

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |

---

## `codex metrics`

Compute code quality metrics, save snapshots, and track trends.

    Calculates maintainability index, LOC, complexity, and comment ratios.
    Supports saving metric snapshots for historical trend analysis.

    Examples:

        codex metrics

        codex metrics --snapshot --json

        codex metrics --history 10

        codex metrics --trend

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--pipe` | boolean | false | Plain text output for piping / CI. |
| `--snapshot` | boolean | false | Save a quality snapshot after computing metrics. |
| `--history` | integer | 0 | Show last N snapshots (0 = skip history). |
| `--trend` | boolean | false | Show trend analysis from historical snapshots. |

---

## `codex models`

Manage embedding models — download, list, switch, info.

---

## `codex models download`

Pre-download a model so it is cached locally for offline use.

**Arguments:**

- `model_name` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--backend` | choice | auto |  |

---

## `codex models info`

Show detailed information about a specific model.

**Arguments:**

- `model_name` — text

---

## `codex models list`

List all available embedding models and their properties.

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json-output, --json` | boolean | false | Output as JSON. |

---

## `codex models switch`

Switch the active embedding model for a project.

    Note: after switching models you must re-index (codex index --reindex).

**Arguments:**

- `model_name` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |

---

## `codex plugin`

Manage CodexA plugins.

---

## `codex plugin info`

Show details about a specific plugin.

    Examples:

        codex plugin info my-formatter

**Arguments:**

- `name` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |

---

## `codex plugin list`

List available plugins in the project.

    Scans .codex/plugins/ for discoverable plugin files.

    Examples:

        codex plugin list

        codex plugin list --json

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output results in JSON format. |

---

## `codex plugin new`

Scaffold a new plugin from template.

    Creates a ready-to-use plugin file with the correct structure.

    Examples:

        codex plugin new my-formatter

        codex plugin new lint-checker --hooks CUSTOM_VALIDATION,POST_AI

        codex plugin new metrics -o ./plugins/ -a "Your Name"

**Arguments:**

- `name` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--description, -d` | text | A CodexA plugin | Plugin description. |
| `--author, -a` | text |  | Plugin author name. |
| `--hooks, -H` | text | POST_SEARCH | Comma-separated hook names (e.g. POST_SEARCH,POST_AI). |
| `--output, -o` | directory |  | Output directory (default: .codex/plugins/). |

---

## `codex pr-summary`

Generate a Pull Request intelligence report.

    Analyzes changed files to produce a change summary, semantic impact
    analysis, suggested reviewer domains, and risk scoring.

    All output is advisory — CodexA never modifies repository code.

    Examples:

        codex pr-summary

        codex pr-summary --json

        codex pr-summary -f src/main.py -f src/utils.py

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--files, -f` | text | Sentinel.UNSET | Specific files to analyze (can be repeated). |
| `--pipe` | boolean | false | Plain text output for piping / CI. |

---

## `codex quality`

Analyze code quality — complexity, dead code, duplicates, security.

    Scans the project for quality issues and produces a human-readable or
    JSON report.  Useful for CI pipelines and local development.

    Examples:

        codex quality

        codex quality --json

        codex quality --safety-only --pipe

        codex quality --complexity-threshold 15

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--complexity-threshold` | integer | 10 | Minimum cyclomatic complexity to report (default: 10). |
| `--safety-only` | boolean | false | Run only the safety validator (fast mode). |
| `--pipe` | boolean | false | Plain text output for piping / CI. |

---

## `codex refactor`

Suggest refactored code for a source file.

    Uses structural analysis + LLM to propose improved code with explanations.

    Examples:

        codex refactor src/main.py

        codex refactor src/utils.py -i "Extract duplicated logic into helpers"

**Arguments:**

- `file` — file

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--instruction, -i` | text | Improve code quality, readability, and performance. | Refactoring instruction for the AI. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--path, -p` | directory | . | Project root path. |

---

## `codex review`

Review a source file for issues, bugs, and improvements.

    Uses structural analysis + LLM to perform an AI-assisted code review.

    Examples:

        codex review src/main.py

        codex review src/utils.py --json

**Arguments:**

- `file` — file

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--path, -p` | directory | . | Project root path. |

---

## `codex search`

Search the indexed codebase using a natural language query.

    Supports four search modes:

    
      semantic  — vector similarity (default)
      keyword   — BM25 ranked keyword search
      regex     — grep-compatible regex pattern matching
      hybrid    — fused semantic + BM25 via Reciprocal Rank Fusion

    Grep-compatible flags:

    
        -l   show only file paths with matches
        -L   show only file paths without matches
        -n   prefix lines with line numbers
        -C N show N context lines before/after each match

    Examples:

    
        codex search "jwt verification"
        codex search "database connection" --mode hybrid
        codex search "def\s+authenticate" --mode regex -n
        codex search "error handling" --mode keyword --full-section
        codex search "error handling" -k 5 --json
        codex search "TODO" --mode regex -l
        codex search "pattern" --jsonl | jq .file_path

**Arguments:**

- `query` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer |  | Number of results to return (overrides config). |
| `--json-output, --json` | boolean | false | Output results in JSON format for AI integration. |
| `--jsonl` | boolean | false | Output one JSON object per line (JSONL), for piping into jq/fzf. |
| `--path, -p` | directory | . | Project root path. |
| `--mode, -m` | choice | semantic | Search mode: semantic (default), keyword (BM25), regex, or hybrid (RRF). |
| `--full-section, --full` | boolean | false | Expand results to show the full enclosing function/class. |
| `--no-auto-index` | boolean | false | Disable automatic indexing on first search. |
| `--case-sensitive, -s` | boolean | false | Case-sensitive matching (regex mode only). |
| `--context-lines, -C` | integer | 0 | Show N context lines before/after each match (grep-style). |
| `--files-only, -l` | boolean | false | Print only file paths with matches (like grep -l). |
| `--files-without-match, -L` | boolean | false | Print file paths without any matches (like grep -L). |
| `--line-numbers, -n` | boolean | false | Prefix each output line with its line number (like grep -n). |

---

## `codex serve`

Start the CodexA bridge server for external AI integration.

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host, -h` | text | 127.0.0.1 | Host to bind the bridge server to. |
| `--port, -p` | integer | 24842 | Port to bind the bridge server to. |
| `--path` | directory | . | Project root path. |

---

## `codex suggest`

Get intelligent suggestions for a symbol, file, or topic.

    Combines call-graph, dependency, and semantic data with LLM reasoning
    to produce actionable suggestions with "why" reasoning.

    Examples:

        codex suggest search_codebase

        codex suggest "error handling patterns" --json

**Arguments:**

- `target` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | 5 | Number of context snippets to consider. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--path, -p` | directory | . | Project root path. |

---

## `codex summary`

Generate a structured summary of the repository.

    Shows language breakdown, symbol counts, and top functions/classes.

    Examples:

        codex summary

        codex summary --json

        codex summary -p /path/to/project

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |

---

## `codex tool`

AI Agent Tooling Protocol — invoke and inspect tools.

    Provides a CLI interface to the same tool execution engine that
    AI coding agents use over the Bridge HTTP API.

    Examples:

        codex tool list
        codex tool run semantic_search --arg query="parse file"
        codex tool schema semantic_search

---

## `codex tool list`

List all available tools with their descriptions.

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json-output, --json` | boolean | false | Output in JSON format. |

---

## `codex tool run`

Run TOOL_NAME with the given arguments.

    Arguments are passed as --arg key=value pairs.

    Examples:

        codex tool run semantic_search --arg query="parse file"
        codex tool run explain_symbol --arg symbol_name=ToolRegistry
        codex tool run summarize_repo --json

**Arguments:**

- `tool_name` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--arg, -a` | text | Sentinel.UNSET | Tool argument as key=value (repeatable). |
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--pipe` | boolean | false | Plain text output for piping / CI. |

---

## `codex tool schema`

Show the schema definition for TOOL_NAME.

    Examples:

        codex tool schema semantic_search
        codex tool schema explain_symbol --json

**Arguments:**

- `tool_name` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json-output, --json` | boolean | false | Output in JSON format. |

---

## `codex trace`

Trace execution relationships for SYMBOL.

    Shows upstream callers and downstream callees to map the flow of
    execution through the codebase.

    Examples:

        codex trace parse_file

        codex trace MyClass.process --json

        codex trace build_context --max-depth 3 --pipe

**Arguments:**

- `symbol` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--pipe` | boolean | false | Plain text output for piping / CI. |
| `--max-depth, -d` | integer | 5 | Maximum traversal depth (default: 5). |

---

## `codex tui`

Launch the interactive terminal search interface.

    Provides a live search REPL with mode switching and result preview.

    Examples:

    
        codex tui
        codex tui --mode hybrid -k 20

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--mode, -m` | choice | hybrid | Default search mode. |
| `--top-k, -k` | integer | 10 | Results per query. |

---

## `codex viz`

Generate Mermaid-compatible diagrams from codebase analysis.

    KIND is one of: callgraph, deps, symbols, workspace.

    Examples:

        codex viz callgraph

        codex viz deps --target src/main.py

        codex viz symbols --target auth.py -o symbols.mmd

        codex viz callgraph --json

**Arguments:**

- `kind` — choice

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--target, -t` | text |  | Symbol name or file path to visualize. |
| `--output, -o` | file |  | Write Mermaid output to a file instead of stdout. |
| `--json-output, --json` | boolean | false | Output as JSON with a 'mermaid' field. |
| `--path, -p` | directory | . | Project root path. |

---

## `codex watch`

Watch the repository for changes and re-index automatically.

    Starts a background daemon that polls for file changes and triggers
    incremental re-indexing.

    Press Ctrl+C to stop.

    Examples:

        codex watch

        codex watch --interval 5

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Project root path. |
| `--interval, -i` | float | 2.0 | Polling interval in seconds. |

---

## `codex web`

Start the CodexA web interface and REST API server.

    Provides a browser-based search UI and JSON REST endpoints
    for programmatic access.  Uses only the Python standard library.

    Examples:

        codex web

        codex web --port 9000

        codex web --host 0.0.0.0 --port 8080 --path /my/project

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host, -h` | text | 127.0.0.1 | Host to bind the web server to. |
| `--port, -p` | integer | 8080 | Port to bind the web server to. |
| `--path` | directory | . | Project root path. |

---

## `codex workspace`

Manage multi-repository workspaces.

---

## `codex workspace add`

Register a repository in the workspace.

**Arguments:**

- `name` — text
- `repo_path` — directory

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Workspace root directory. |

---

## `codex workspace index`

Index repositories in the workspace.

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--repo, -r` | text |  | Index only this repository (by name). |
| `--force` | boolean | false | Force full re-index. |
| `--path, -p` | directory | . | Workspace root directory. |

---

## `codex workspace init`

Initialise a new workspace.

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Workspace root directory. |

---

## `codex workspace list`

List all repositories in the workspace.

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--path, -p` | directory | . | Workspace root directory. |

---

## `codex workspace remove`

Unregister a repository from the workspace.

**Arguments:**

- `name` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--path, -p` | directory | . | Workspace root directory. |

---

## `codex workspace search`

Search across all workspace repositories.

**Arguments:**

- `query` — text

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--top-k, -k` | integer | 10 | Number of results. |
| `--threshold, -t` | float | 0.3 | Minimum score. |
| `--repo, -r` | text | Sentinel.UNSET | Restrict to specific repos (repeatable). |
| `--json-output, --json` | boolean | false | Output in JSON format. |
| `--path, -p` | directory | . | Workspace root directory. |

---
