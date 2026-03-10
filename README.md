<p align="center">
  <strong>CodexA — Developer Intelligence Engine</strong><br>
  <em>Semantic code search · AI-assisted understanding · Agent tooling protocol</em>
</p>

<p align="center">
  <a href="https://github.com/M9nx/CodexA/actions"><img src="https://github.com/M9nx/CodexA/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/version-0.4.5-green" alt="Version">
  <img src="https://img.shields.io/badge/tests-2596-brightgreen" alt="Tests">
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
| **Code Indexing** | Scan repos, extract functions/classes, generate vector embeddings (sentence-transformers + FAISS), ONNX runtime option, parallel indexing, `--watch` live re-indexing, `.codexaignore` support |
| **Multi-Mode Search** | Semantic, keyword (BM25), regex, hybrid (RRF), and raw filesystem grep (ripgrep backend) with full `-A/-B/-C/-w/-v/-c` flags |
| **Code Context** | Rich context windows — imports, dependencies, AST-based call graphs, surrounding code |
| **Repository Analysis** | Language breakdown (`codexa languages`), module summaries, component detection |
| **AI Agent Protocol** | 13 built-in tools exposed via HTTP bridge, MCP server (13 tools), MCP-over-SSE (`--mcp`), or CLI for any AI agent to invoke |
| **Quality & Metrics** | Complexity analysis, maintainability scoring, quality gates for CI |
| **Multi-Repo Workspaces** | Link multiple repos under one workspace for cross-repo search & refactoring |
| **Interactive TUI** | Terminal REPL with mode switching for interactive exploration |
| **Streaming Responses** | Token-by-token streaming for chat and investigation commands |
| **Plugin System** | 22 hooks for extending every layer — from indexing to tool invocation |
| **VS Code Extension** | 4-panel sidebar (Search, Symbols, Quality, Tools), 8 commands, CodeLens, context menus, status bar |

---

## Quick Start

### 1. Install

```bash
pip install codexa
```

For semantic indexing and vector search, install the ML extras:

```bash
pip install "codexa[ml]"
```

Or install from source:

```bash
git clone https://github.com/M9nx/CodexA.git
cd CodexA
pip install -e ".[dev]"
```

**Alternative installation methods:**

```bash
# Docker
docker build -t codexa .
docker run --rm -v /path/to/project:/workspace codexa search "auth"

# Homebrew (macOS)
brew install --formula Formula/codexa.rb
```

### 2. Initialize a Project

Navigate to any project you want to analyze and run:

```bash
cd /path/to/your-project
codexa init
```

CodexA auto-detects your available RAM and picks the best embedding model.
Or choose a model profile explicitly:

```bash
codexa init --profile fast       # mxbai-embed-xsmall — low RAM (<1 GB)
codexa init --profile balanced   # MiniLM — good balance (~2 GB)
codexa init --profile precise    # jina-code — best quality (~4 GB)
```

This creates a `.codexa/` directory with configuration, index storage, and session data.

### 3. Index the Codebase

```bash
codexa index .
```

This parses all source files (Python, JS/TS, Java, Go, Rust, C#, Ruby, C++),
extracts symbols, generates embeddings, and stores them in a local FAISS index.
Semantic indexing requires `codexa[ml]`.

If you need to keep secrets, generated files, or local config files out of the
index, add patterns to `.codexaignore` at the project root or configure
`index.exclude_files` in `.codexa/config.json`.

Typical `.codexaignore` example:

```text
.env*
secrets/*.json
config/local-*.yml
vendor/*
```

The default embedding model is small, but the PyTorch backend still needs about
2 GB of available RAM. On lower-memory machines, prefer the ONNX backend.

### 4. Semantic Search

```bash
codexa search "jwt authentication"
codexa search "database connection pool" --json
codexa search "error handling" -k 5
```

### 5. Explore More

```bash
codexa explain MyClass              # Structural explanation of a symbol
codexa context parse_config         # Rich AI context window
codexa deps src/auth.py             # Import / dependency map
codexa summary                      # Full repo summary
codexa quality src/                 # Code quality analysis
codexa hotspots                     # High-risk code hotspots
codexa trace handle_request         # Execution trace of a symbol
codexa evolve                       # Self-improving development loop
codexa grep "TODO|FIXME"            # Raw filesystem grep (ripgrep or Python)
codexa benchmark                    # Performance benchmarking
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
codexa tool list --json

# Run a tool with arguments
codexa tool run semantic_search --arg query="authentication middleware" --json
codexa tool run explain_symbol --arg symbol_name="UserService" --json
codexa tool run get_call_graph --arg symbol_name="process_payment" --json
codexa tool run get_dependencies --arg file_path="src/auth.py" --json

# Get tool schema (so the agent knows what arguments to pass)
codexa tool schema semantic_search --json
```

The `--json` flag ensures machine-readable output. The `--pipe` flag suppresses
colors and spinners for clean piping.

### Option B — HTTP Bridge Server (For MCP / Long-Running Agents)

Start the bridge server to expose all tools over HTTP:

```bash
codexa serve --port 24842
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

# Install it (makes `codexa` available system-wide in your venv)
cd CodexA
pip install -e ".[dev]"

# Verify
codexa --version    # → codexa, version 0.4.5
```

### Step 2 — Initialize your target project

```bash
cd /path/to/your-project
codexa init --index  # Creates .codexa/ and indexes immediately
# Or separately:
codexa init          # Creates .codexa/ directory
codexa index .       # Index the entire codebase
codexa doctor        # Verify everything is healthy
codexa search "main" # Quick sanity check
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
You have access to the `codexa` CLI for semantic code search, symbol
explanation, dependency analysis, and more.

### Available Commands

Before answering questions about this codebase, use CodexA to gather context:

- **Search the codebase:**
  ```bash
  codexa search "<natural language query>" --json
  ```

- **Explain a symbol (function/class/method):**
  ```bash
  codexa tool run explain_symbol --arg symbol_name="<name>" --json
  ```

- **Get the call graph of a function:**
  ```bash
  codexa tool run get_call_graph --arg symbol_name="<name>" --json
  ```

- **Get file dependencies/imports:**
  ```bash
  codexa tool run get_dependencies --arg file_path="<path>" --json
  ```

- **Find all references to a symbol:**
  ```bash
  codexa tool run find_references --arg symbol_name="<name>" --json
  ```

- **Get rich context for a symbol:**
  ```bash
  codexa tool run get_context --arg symbol_name="<name>" --json
  ```

- **Summarize the entire repo:**
  ```bash
  codexa tool run summarize_repo --json
  ```

- **Explain all symbols in a file:**
  ```bash
  codexa tool run explain_file --arg file_path="<path>" --json
  ```

### Rules

1. Always use `--json` flag for machine-readable output.
2. When asked about code structure, search with `codexa search` first.
3. When explaining a function or class, use `codexa tool run explain_symbol`.
4. When analyzing impact of changes, use `codexa impact`.
5. When reviewing code, run `codexa quality <path>` first.
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
> codexa tool run explain_symbol --arg symbol_name="process_payment" --json
> codexa tool run get_call_graph --arg symbol_name="process_payment" --json
> ```
> Then gives you a structured answer with callers, callees, and explanation.

> **You:** Find all code related to authentication
>
> **Copilot** runs: `codexa search "authentication" --json`
> Returns ranked semantic search results across your entire codebase.

> **You:** What would break if I change `UserService`?
>
> **Copilot** runs:
> ```
> codexa tool run find_references --arg symbol_name="UserService" --json
> codexa impact
> ```
> Shows blast radius and all dependents.

> **You:** Review the code quality of src/api/
>
> **Copilot** runs: `codexa quality src/api/ --json`
> Returns complexity scores, dead code, duplicates, and security issues.

### Step 6 — Start the Bridge Server (optional, for MCP)

For persistent connections (MCP servers, custom agent frameworks):

```bash
codexa serve --port 24842
```

The agent can then call `http://127.0.0.1:24842/tools/invoke` directly.

### Step 7 — Configure LLM provider (optional)

For AI-powered commands (`codexa ask`, `codexa review`, `codexa chat`, etc.),
edit `.codexa/config.json`:

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

CodexA provides **39 commands** (plus subcommands) organized by capability:

### Core

| Command | Description |
|---------|-------------|
| `codexa init [path]` | Initialize project — creates `.codexa/` directory (supports `--index` and `--vscode`) |
| `codexa index [path]` | Index codebase for semantic search |
| `codexa search "<query>"` | Natural-language semantic search |
| `codexa explain <symbol>` | Structural explanation of a symbol or file |
| `codexa context <symbol>` | Rich context window for AI consumption |
| `codexa summary` | Structured repository summary |
| `codexa deps <file>` | File/project dependency map |
| `codexa watch` | Background indexing daemon (Rust-backed native file watcher) |
| `codexa grep "<pattern>"` | Raw filesystem grep — no index required (ripgrep backend) |
| `codexa benchmark` | Performance benchmarking (indexing, search, memory) |
| `codexa languages` | List supported tree-sitter languages with grammar status |

### AI-Powered

| Command | Description |
|---------|-------------|
| `codexa ask "<question>"` | Ask a question about the codebase (LLM) |
| `codexa review <file>` | AI-powered code review |
| `codexa refactor <file>` | AI-powered refactoring suggestions |
| `codexa suggest <symbol>` | Intelligent improvement suggestions |
| `codexa chat` | Multi-turn conversation with session persistence |
| `codexa investigate <goal>` | Autonomous multi-step code investigation |

### Quality & Metrics

| Command | Description |
|---------|-------------|
| `codexa quality [path]` | Code quality analysis |
| `codexa metrics` | Code metrics, snapshots, and trends |
| `codexa hotspots` | Identify high-risk code hotspots |
| `codexa gate` | Enforce quality gates for CI pipelines |
| `codexa impact` | Blast radius analysis of code changes |

### DevOps & Integration

| Command | Description |
|---------|-------------|
| `codexa serve` | Start HTTP bridge server for AI agents |
| `codexa tool list\|run\|schema` | AI Agent Tooling Protocol commands |
| `codexa pr-summary` | Generate PR intelligence report |
| `codexa ci-gen` | Generate CI workflow templates |
| `codexa web` | Start web interface and REST API |
| `codexa viz` | Generate Mermaid visualizations |
| `codexa evolve` | Self-improving development loop |

### Workspace & Utilities

| Command | Description |
|---------|-------------|
| `codexa workspace` | Multi-repo workspace management |
| `codexa cross-refactor` | Cross-repository refactoring |
| `codexa trace <symbol>` | Trace execution relationships |
| `codexa docs` | Generate project documentation |
| `codexa doctor` | Environment health check |
| `codexa plugin list\|scaffold\|discover` | Plugin management |
| `codexa tui` | Interactive terminal REPL |
| `codexa mcp` | Start MCP (Model Context Protocol) server |
| `codexa models list\|info\|download\|switch\|profiles\|benchmark` | Manage and benchmark embedding models |

### VS Code Extension

| Feature | Command / Keybinding |
|---------|---------------------|
| Multi-mode search panel (semantic/keyword/hybrid/regex) | Sidebar → Search |
| Symbol explorer (explain, call graph, deps) | Sidebar → Symbols & Graphs |
| Code quality dashboard (quality, metrics, hotspots) | Sidebar → Quality |
| Agent tool runner (doctor, index, models, 13 tools) | Sidebar → Tools |
| Search codebase | `Ctrl+Shift+F5` |
| Explain symbol at cursor | `Ctrl+Shift+E` |
| Code quality analysis | `Ctrl+Shift+Q` |
| Right-click → Explain / Call Graph | Editor context menu |

---

## Built-in Tools (AI Agent Protocol)

These tools can be invoked via CLI (`codexa tool run`), HTTP (`POST /tools/invoke`),
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
| `get_file_context` | `file_path`, `line` or `symbol_name` | Full-section surrounding code retrieval |
| `get_quality_score` | `file_path` (string, optional) | Code quality analysis — complexity, dead code, duplicates |
| `find_duplicates` | `threshold` (float, optional) | Detect near-duplicate code blocks |
| `grep_files` | `pattern` (string) | Raw filesystem regex search (ripgrep/Python) |
| `list_languages` | *(none)* | List supported tree-sitter languages and grammar status |

Additional tools can be registered via the plugin system using the
`REGISTER_TOOL` hook.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    CLI Layer (click)                 │
│  39 commands · --json · --pipe · --verbose           │
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
│         Storage (.codexa/ — config, index, cache)     │
└─────────────────────────────────────────────────────┘
```

---

## Configuration

After `codexa init`, your project has `.codexa/config.json`:

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

> **Tip:** Instead of editing `model_name` manually, use `codexa init --profile fast|balanced|precise`
> or run `codexa models profiles` to see recommended models for your hardware.

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

# Run all 2595 tests
pytest

# Run with coverage (gate: 70% minimum)
pytest --cov=semantic_code_intelligence

# Run mypy strict type checking
mypy semantic_code_intelligence --exclude "tests/"

# Run specific phase tests
pytest semantic_code_intelligence/tests/test_phase23.py -v

# Run with verbose output
codexa --verbose search "query"
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
