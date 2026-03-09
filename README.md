<p align="center">
  <strong>CodexA — Developer Intelligence Engine</strong><br>
  <em>Semantic code search · AI-assisted understanding · Agent tooling protocol</em>
</p>

<p align="center">
  <a href="https://github.com/M9nx/CodexA/actions"><img src="https://github.com/M9nx/CodexA/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/version-0.29.0-green" alt="Version">
  <img src="https://img.shields.io/badge/tests-2595-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-79%25-brightgreen" alt="Coverage">
  <img src="https://img.shields.io/badge/mypy-strict-blue" alt="mypy strict">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

---

**CodexA** is a lightweight developer intelligence engine designed to cooperate
with AI coding assistants (GitHub Copilot, Cursor, Cline, etc.) and developer
tooling. It indexes codebases locally, performs semantic search, and exposes a
structured tool protocol that any AI agent can call over HTTP or CLI.

## Features

| Area | What you get |
|------|-------------|
| **Code Indexing** | Scan repos, extract functions/classes, generate vector embeddings (sentence-transformers + FAISS), ONNX runtime option, parallel indexing, `.codexaignore` support |
| **Multi-Mode Search** | Semantic, keyword (BM25), regex, hybrid (RRF), and raw filesystem grep (ripgrep backend) |
| **Code Context** | Rich context windows — imports, dependencies, AST-based call graphs, surrounding code |
| **Repository Analysis** | Language breakdown, module summaries, component detection |
| **AI Agent Protocol** | 11 built-in tools exposed via HTTP bridge, MCP server (11 tools), or CLI for any AI agent to invoke |
| **Quality & Metrics** | Complexity analysis, maintainability scoring, quality gates for CI |
| **Multi-Repo Workspaces** | Link multiple repos under one workspace for cross-repo search & refactoring |
| **Interactive TUI** | Terminal REPL with mode switching for interactive exploration |
| **Streaming Responses** | Token-by-token streaming for chat and investigation commands |
| **Plugin System** | 22 hooks for extending every layer — from indexing to tool invocation |
| **VS Code Extension** | 4-panel sidebar (Search, Symbols, Quality, Tools), 8 commands, CodeLens, context menus, status bar |

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/M9nx/CodexA.git
cd CodexA

# Create a virtual environment (recommended)
python -m venv .venv

# Activate it
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### 2. Initialize a Project

Navigate to any project you want to analyze and run:

```bash
cd /path/to/your-project
codex init
```

This creates a `.codex/` directory with configuration, index storage, and session data.

### 3. Index the Codebase

```bash
codex index .
```

This parses all source files (Python, JS/TS, Java, Go, Rust, C#, Ruby, C++),
extracts symbols, generates embeddings, and stores them in a local FAISS index.

### 4. Semantic Search

```bash
codex search "jwt authentication"
codex search "database connection pool" --json
codex search "error handling" -k 5
```

### 5. Explore More

```bash
codex explain MyClass              # Structural explanation of a symbol
codex context parse_config         # Rich AI context window
codex deps src/auth.py             # Import / dependency map
codex summary                      # Full repo summary
codex quality src/                 # Code quality analysis
codex hotspots                     # High-risk code hotspots
codex trace handle_request         # Execution trace of a symbol
codex evolve                       # Self-improving development loop
codex grep "TODO|FIXME"            # Raw filesystem grep (ripgrep or Python)
codex benchmark                    # Performance benchmarking
```

---

## Using CodexA with AI Agents (GitHub Copilot, etc.)

CodexA is designed to be called by AI coding assistants as an external tool.
There are **three integration modes**: CLI tool mode, HTTP bridge server, and
in-process Python API.

### Option A — CLI Tool Mode (Recommended for Copilot Chat)

Any AI agent that can run shell commands can use CodexA directly:

```bash
# List available tools
codex tool list --json

# Run a tool with arguments
codex tool run semantic_search --arg query="authentication middleware" --json
codex tool run explain_symbol --arg symbol_name="UserService" --json
codex tool run get_call_graph --arg symbol_name="process_payment" --json
codex tool run get_dependencies --arg file_path="src/auth.py" --json

# Get tool schema (so the agent knows what arguments to pass)
codex tool schema semantic_search --json
```

The `--json` flag ensures machine-readable output. The `--pipe` flag suppresses
colors and spinners for clean piping.

### Option B — HTTP Bridge Server (For MCP / Long-Running Agents)

Start the bridge server to expose all tools over HTTP:

```bash
codex serve --port 24842
```

The server runs on `http://127.0.0.1:24842` and exposes:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/capabilities` | Full capability manifest — version, tools, supported requests |
| `GET` | `/health` | Health check → `{"status": "ok"}` |
| `GET` | `/tools/list` | List all available tools with schemas |
| `POST` | `/tools/invoke` | Execute a tool by name with arguments |
| `GET` | `/tools/stream` | SSE stream — tool discovery + heartbeat |
| `POST` | `/request` | Dispatch any `AgentRequest` (12 request kinds) |

**Example — invoke a tool via HTTP:**

```bash
curl -X POST http://127.0.0.1:24842/tools/invoke \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "semantic_search", "arguments": {"query": "error handling"}}'
```

**Example — list capabilities:**

```bash
curl http://127.0.0.1:24842/capabilities
```

### Option C — Python API (In-Process)

```python
from pathlib import Path
from semantic_code_intelligence.tools.executor import ToolExecutor
from semantic_code_intelligence.tools.protocol import ToolInvocation

executor = ToolExecutor(Path("/path/to/project"))
invocation = ToolInvocation(tool_name="semantic_search", arguments={"query": "auth"})
result = executor.execute(invocation)

print(result.success)           # True
print(result.result_payload)    # dict with search results
print(result.execution_time_ms) # timing in milliseconds
```

---

## Setting Up with VS Code + GitHub Copilot

### Step 1 — Install CodexA globally

```bash
# Clone the repo
git clone https://github.com/M9nx/CodexA.git

# Install it (makes `codex` available system-wide in your venv)
cd CodexA
pip install -e ".[dev]"

# Verify
codex --version    # → codex, version 0.29.0
```

### Step 2 — Initialize your target project

```bash
cd /path/to/your-project
codex init --index  # Creates .codex/ and indexes immediately
# Or separately:
codex init          # Creates .codex/ directory
codex index .       # Index the entire codebase
codex doctor        # Verify everything is healthy
codex search "main" # Quick sanity check
```

### Step 3 — Add Copilot Custom Instructions (System Prompt)

Create the file `.github/copilot-instructions.md` in your project root.
This file acts as a **system prompt** — GitHub Copilot reads it automatically
and follows the instructions in every chat and code generation session.

```bash
mkdir -p .github
```

Then create `.github/copilot-instructions.md` with this content:

````markdown
# Copilot Custom Instructions

## CodexA Integration

This project uses **CodexA** — a local developer intelligence engine.
You have access to the `codex` CLI for semantic code search, symbol
explanation, dependency analysis, and more.

### Available Commands

Before answering questions about this codebase, use CodexA to gather context:

- **Search the codebase:**
  ```bash
  codex search "<natural language query>" --json
  ```

- **Explain a symbol (function/class/method):**
  ```bash
  codex tool run explain_symbol --arg symbol_name="<name>" --json
  ```

- **Get the call graph of a function:**
  ```bash
  codex tool run get_call_graph --arg symbol_name="<name>" --json
  ```

- **Get file dependencies/imports:**
  ```bash
  codex tool run get_dependencies --arg file_path="<path>" --json
  ```

- **Find all references to a symbol:**
  ```bash
  codex tool run find_references --arg symbol_name="<name>" --json
  ```

- **Get rich context for a symbol:**
  ```bash
  codex tool run get_context --arg symbol_name="<name>" --json
  ```

- **Summarize the entire repo:**
  ```bash
  codex tool run summarize_repo --json
  ```

- **Explain all symbols in a file:**
  ```bash
  codex tool run explain_file --arg file_path="<path>" --json
  ```

### Rules

1. Always use `--json` flag for machine-readable output.
2. When asked about code structure, search with `codex search` first.
3. When explaining a function or class, use `codex tool run explain_symbol`.
4. When analyzing impact of changes, use `codex impact`.
5. When reviewing code, run `codex quality <path>` first.
6. Prefer CodexA tools over reading large files manually — they provide
   structured, indexed results.
````

### Step 4 — Configure Copilot Chat to use CodexA

In VS Code, open **Settings** (Ctrl+,) and search for:

| Setting | Value | Purpose |
|---------|-------|---------|
| `github.copilot.chat.codeGeneration.instructions` | Add `.github/copilot-instructions.md` | Auto-loads custom instructions |
| `chat.agent.enabled` | `true` | Enables agent mode in Copilot Chat |

Or add this to your `.vscode/settings.json`:

```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    { "file": ".github/copilot-instructions.md" }
  ]
}
```

### Step 5 — Use Copilot Chat with CodexA

Open **Copilot Chat** in VS Code (Ctrl+Shift+I or the chat panel) and switch
to **Agent mode** (the dropdown at the top). Now Copilot can run terminal
commands and will automatically use CodexA per your instructions.

**Example conversations:**

> **You:** What does the `process_payment` function do and what calls it?
>
> **Copilot** runs:
> ```
> codex tool run explain_symbol --arg symbol_name="process_payment" --json
> codex tool run get_call_graph --arg symbol_name="process_payment" --json
> ```
> Then gives you a structured answer with callers, callees, and explanation.

> **You:** Find all code related to authentication
>
> **Copilot** runs: `codex search "authentication" --json`
> Returns ranked semantic search results across your entire codebase.

> **You:** What would break if I change `UserService`?
>
> **Copilot** runs:
> ```
> codex tool run find_references --arg symbol_name="UserService" --json
> codex impact
> ```
> Shows blast radius and all dependents.

> **You:** Review the code quality of src/api/
>
> **Copilot** runs: `codex quality src/api/ --json`
> Returns complexity scores, dead code, duplicates, and security issues.

### Step 6 — Start the Bridge Server (optional, for MCP)

For persistent connections (MCP servers, custom agent frameworks):

```bash
codex serve --port 24842
```

The agent can then call `http://127.0.0.1:24842/tools/invoke` directly.

### Step 7 — Configure LLM provider (optional)

For AI-powered commands (`codex ask`, `codex review`, `codex chat`, etc.),
edit `.codex/config.json`:

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

---

## All CLI Commands

CodexA provides **38 commands** (plus subcommands) organized by capability:

### Core

| Command | Description |
|---------|-------------|
| `codex init [path]` | Initialize project — creates `.codex/` directory (supports `--index` and `--vscode`) |
| `codex index [path]` | Index codebase for semantic search |
| `codex search "<query>"` | Natural-language semantic search |
| `codex explain <symbol>` | Structural explanation of a symbol or file |
| `codex context <symbol>` | Rich context window for AI consumption |
| `codex summary` | Structured repository summary |
| `codex deps <file>` | File/project dependency map |
| `codex watch` | Background indexing daemon (Rust-backed native file watcher) |
| `codex grep "<pattern>"` | Raw filesystem grep — no index required (ripgrep backend) |
| `codex benchmark` | Performance benchmarking (indexing, search, memory) |

### AI-Powered

| Command | Description |
|---------|-------------|
| `codex ask "<question>"` | Ask a question about the codebase (LLM) |
| `codex review <file>` | AI-powered code review |
| `codex refactor <file>` | AI-powered refactoring suggestions |
| `codex suggest <symbol>` | Intelligent improvement suggestions |
| `codex chat` | Multi-turn conversation with session persistence |
| `codex investigate <goal>` | Autonomous multi-step code investigation |

### Quality & Metrics

| Command | Description |
|---------|-------------|
| `codex quality [path]` | Code quality analysis |
| `codex metrics` | Code metrics, snapshots, and trends |
| `codex hotspots` | Identify high-risk code hotspots |
| `codex gate` | Enforce quality gates for CI pipelines |
| `codex impact` | Blast radius analysis of code changes |

### DevOps & Integration

| Command | Description |
|---------|-------------|
| `codex serve` | Start HTTP bridge server for AI agents |
| `codex tool list\|run\|schema` | AI Agent Tooling Protocol commands |
| `codex pr-summary` | Generate PR intelligence report |
| `codex ci-gen` | Generate CI workflow templates |
| `codex web` | Start web interface and REST API |
| `codex viz` | Generate Mermaid visualizations |
| `codex evolve` | Self-improving development loop |

### Workspace & Utilities

| Command | Description |
|---------|-------------|
| `codex workspace` | Multi-repo workspace management |
| `codex cross-refactor` | Cross-repository refactoring |
| `codex trace <symbol>` | Trace execution relationships |
| `codex docs` | Generate project documentation |
| `codex doctor` | Environment health check |
| `codex plugin list\|scaffold\|discover` | Plugin management |
| `codex tui` | Interactive terminal REPL |
| `codex mcp` | Start MCP (Model Context Protocol) server |
| `codex models list\|info\|download\|switch` | Manage embedding models |

### VS Code Extension

| Feature | Command / Keybinding |
|---------|---------------------|
| Multi-mode search panel (semantic/keyword/hybrid/regex) | Sidebar → Search |
| Symbol explorer (explain, call graph, deps) | Sidebar → Symbols & Graphs |
| Code quality dashboard (quality, metrics, hotspots) | Sidebar → Quality |
| Agent tool runner (doctor, index, models, 8 tools) | Sidebar → Tools |
| Search codebase | `Ctrl+Shift+F5` |
| Explain symbol at cursor | `Ctrl+Shift+E` |
| Code quality analysis | `Ctrl+Shift+Q` |
| Right-click → Explain / Call Graph | Editor context menu |

---

## Built-in Tools (AI Agent Protocol)

These tools can be invoked via CLI (`codex tool run`), HTTP (`POST /tools/invoke`),
or Python API (`ToolExecutor.execute()`):

| Tool | Arguments | Description |
|------|-----------|-------------|
| `semantic_search` | `query` (string) | Search codebase by natural language |
| `explain_symbol` | `symbol_name` (string) | Structural explanation of a symbol |
| `explain_file` | `file_path` (string) | Explain all symbols in a file |
| `summarize_repo` | *(none)* | Full repository summary |
| `find_references` | `symbol_name` (string) | Find all references to a symbol |
| `get_dependencies` | `file_path` (string) | Import / dependency map for a file |
| `get_call_graph` | `symbol_name` (string) | Call graph — callers and callees |
| `get_context` | `symbol_name` (string) | Rich context window for AI tasks |
| `get_quality_score` | `file_path` (string, optional) | Code quality analysis — complexity, dead code, duplicates |
| `find_duplicates` | `threshold` (float, optional) | Detect near-duplicate code blocks |
| `grep_files` | `pattern` (string) | Raw filesystem regex search (ripgrep/Python) |

Additional tools can be registered via the plugin system using the
`REGISTER_TOOL` hook.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    CLI Layer (click)                 │
│  38 commands · --json · --pipe · --verbose           │
├─────────────────────────────────────────────────────┤
│               AI Agent Tooling Protocol              │
│  ToolExecutor · ToolInvocation · ToolExecutionResult │
├─────────────────────────────────────────────────────┤
│                  Bridge Server (HTTP)                │
│  /tools/invoke · /tools/list · /request · SSE stream │
├──────────────┬──────────────┬───────────────────────┤
│ Parsing      │ Embedding    │ Search                │
│ tree-sitter  │ sent-trans   │ FAISS                 │
├──────────────┼──────────────┴───────────────────────┤
│ Evolution    │  Self-improving dev loop              │
│ engine       │  budget · task · patch · test · commit│
├──────────────┴──────────────────────────────────────┤
│              Plugin System (22 hooks)                │
├─────────────────────────────────────────────────────┤
│         Storage (.codex/ — config, index, cache)     │
└─────────────────────────────────────────────────────┘
```

---

## Configuration

After `codex init`, your project has `.codex/config.json`:

```json
{
  "embedding": {
    "model_name": "all-MiniLM-L6-v2",
    "chunk_size": 512,
    "chunk_overlap": 64
  },
  "search": {
    "top_k": 10,
    "similarity_threshold": 0.3
  },
  "index": {
    "use_incremental": true,
    "extensions": [".py", ".js", ".ts", ".java", ".go", ".rs", ".rb", ".cpp", ".cs"]
  },
  "llm": {
    "provider": "mock",
    "model": "",
    "api_key": "",
    "temperature": 0.2,
    "max_tokens": 2048
  }
}
```

---

## Documentation

CodexA ships with a full VitePress documentation site.

```bash
# Install docs dependencies
npm install

# Serve locally (live-reload)
npm run docs:dev

# Build static site
npm run docs:build

# Preview the build
npm run docs:preview
```

Browse the docs at **http://localhost:5173** after running `npm run docs:dev`.

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all 2556 tests
pytest

# Run with coverage (gate: 70% minimum)
pytest --cov=semantic_code_intelligence

# Run mypy strict type checking
mypy semantic_code_intelligence --exclude "tests/"

# Run specific phase tests
pytest semantic_code_intelligence/tests/test_phase23.py -v

# Run with verbose output
codex --verbose search "query"
```

## Tech Stack

- **Python 3.11+** — No heavy frameworks, stdlib-first design
- **click** — CLI framework
- **sentence-transformers** — Embedding generation (`all-MiniLM-L6-v2`)
- **faiss-cpu** — Vector similarity search (O(1) file-level index, batch reconstruction)
- **tree-sitter** — Multi-language code parsing
- **watchfiles** — Rust-backed native file watching (inotify/FSEvents/ReadDirectoryChanges)
- **pydantic** — Configuration & data models
- **rich** — Terminal UI and formatting

## License

MIT — see [LICENSE](LICENSE) for details.
