"""Auto-documentation generator for CodexA.

Generates Markdown documentation for:
- CLI commands (from Click command tree)
- Plugin hooks (from PluginHook enum)
- Bridge protocol (from RequestKind and data classes)
- Tool registry (from ToolRegistry definitions)
"""

from __future__ import annotations

import inspect
import textwrap
from pathlib import Path
from typing import Any

import click


def generate_cli_reference(cli_group: click.Group) -> str:
    """Generate Markdown documentation for all CLI commands.

    Walks the Click command tree and produces a reference with
    usage, options, and help text for every registered command.
    """
    lines: list[str] = [
        "# CLI Reference",
        "",
        "Auto-generated from the registered Click command tree.",
        "",
    ]

    commands = _collect_commands(cli_group, prefix="codex")
    for cmd_path, cmd in commands:
        lines.append(f"## `{cmd_path}`")
        lines.append("")

        # Help text
        help_text = (cmd.help or "").strip()
        if help_text:
            lines.append(help_text)
            lines.append("")

        # Arguments
        params_args = [p for p in cmd.params if isinstance(p, click.Argument)]
        if params_args:
            lines.append("**Arguments:**")
            lines.append("")
            for arg in params_args:
                lines.append(f"- `{arg.name}` — {arg.type.name}")
            lines.append("")

        # Options
        params_opts = [p for p in cmd.params if isinstance(p, click.Option)]
        if params_opts:
            lines.append("**Options:**")
            lines.append("")
            lines.append("| Flag | Type | Default | Description |")
            lines.append("|------|------|---------|-------------|")
            for opt in params_opts:
                flags = ", ".join(opt.opts + opt.secondary_opts)
                type_name = opt.type.name if opt.type else ""
                default = opt.default if opt.default is not None else ""
                if isinstance(default, bool):
                    default = str(default).lower()
                help_str = (opt.help or "").replace("|", "\\|")
                lines.append(f"| `{flags}` | {type_name} | {default} | {help_str} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _collect_commands(
    group: click.BaseCommand,
    prefix: str,
) -> list[tuple[str, click.Command]]:
    """Recursively collect all commands from a Click group."""
    results: list[tuple[str, click.Command]] = []

    if isinstance(group, click.Group):
        for name in sorted(group.commands):
            cmd = group.commands[name]
            full = f"{prefix} {name}"
            if isinstance(cmd, click.Group):
                # Add the group itself
                results.append((full, cmd))
                results.extend(_collect_commands(cmd, full))
            else:
                results.append((full, cmd))
    return results


def generate_plugin_reference() -> str:
    """Generate Markdown documentation for the Plugin SDK."""
    from semantic_code_intelligence.plugins import (
        PluginBase,
        PluginHook,
        PluginMetadata,
    )

    lines: list[str] = [
        "# Plugin SDK Reference",
        "",
        "Auto-generated from the CodexA plugin architecture.",
        "",
        "## Hook Points",
        "",
        f"CodexA provides **{len(PluginHook)}** hook points in the processing pipeline:",
        "",
        "| Hook | Value | Category |",
        "|------|-------|----------|",
    ]

    categories = {
        "PRE_INDEX": "Indexing",
        "POST_INDEX": "Indexing",
        "ON_CHUNK": "Indexing",
        "PRE_SEARCH": "Search",
        "POST_SEARCH": "Search",
        "PRE_ANALYSIS": "Analysis",
        "POST_ANALYSIS": "Analysis",
        "PRE_AI": "AI",
        "POST_AI": "AI",
        "ON_FILE_CHANGE": "File Events",
        "ON_STREAM": "Streaming",
        "CUSTOM_VALIDATION": "Validation",
        "CUSTOM": "Custom",
    }

    for hook in PluginHook:
        cat = categories.get(hook.name, "Other")
        lines.append(f"| `{hook.name}` | `{hook.value}` | {cat} |")

    lines.extend([
        "",
        "## Plugin Base Class",
        "",
        "All plugins extend `PluginBase` and implement the following interface:",
        "",
        "```python",
        "class PluginBase(ABC):",
        "    @abstractmethod",
        "    def metadata(self) -> PluginMetadata:",
        '        """Return plugin name, version, description, and registered hooks."""',
        "",
        "    def activate(self, context: dict) -> None:",
        '        """Called when the plugin is activated."""',
        "",
        "    def deactivate(self) -> None:",
        '        """Called when the plugin is deactivated."""',
        "",
        "    def on_hook(self, hook: PluginHook, data: dict) -> dict:",
        '        """Called when a registered hook fires. Modify and return data."""',
        "```",
        "",
        "## PluginMetadata",
        "",
        "| Field | Type | Description |",
        "|-------|------|-------------|",
        "| `name` | `str` | Unique plugin name |",
        "| `version` | `str` | Semantic version (default: `0.1.0`) |",
        "| `description` | `str` | Human-readable description |",
        "| `author` | `str` | Author name |",
        "| `hooks` | `list[PluginHook]` | Hooks this plugin subscribes to |",
        "",
        "## Discovery",
        "",
        "Plugins are discovered from `.codex/plugins/` directories. Each plugin file",
        "must define a `create_plugin()` factory function that returns a `PluginBase` instance.",
        "",
        "## Lifecycle",
        "",
        "1. **Register** — `PluginManager.register(plugin)` adds the plugin",
        "2. **Activate** — `PluginManager.activate(name, context)` calls `plugin.activate()`",
        "3. **Dispatch** — `PluginManager.dispatch(hook, data)` chains through active plugins",
        "4. **Deactivate** — `PluginManager.deactivate(name)` calls `plugin.deactivate()`",
        "",
    ])

    return "\n".join(lines)


def generate_bridge_reference() -> str:
    """Generate Markdown documentation for the bridge protocol."""
    from semantic_code_intelligence.bridge.protocol import (
        AgentRequest,
        AgentResponse,
        BridgeCapabilities,
        RequestKind,
    )

    lines: list[str] = [
        "# Bridge Protocol Reference",
        "",
        "Auto-generated from the CodexA agent cooperation protocol.",
        "",
        "## Overview",
        "",
        "CodexA exposes a stateless JSON/HTTP bridge (`codex serve`) that any",
        "IDE extension or AI assistant can use to request context.",
        "",
        "## Endpoints",
        "",
        "| Method | Path | Description |",
        "|--------|------|-------------|",
        "| GET | `/` | Capabilities manifest |",
        "| GET | `/health` | Health check |",
        "| POST | `/request` | Handle an AgentRequest |",
        "| OPTIONS | `*` | CORS preflight |",
        "",
        "## Request Kinds",
        "",
        f"The bridge supports **{len(RequestKind)}** request types:",
        "",
        "| Kind | Value |",
        "|------|-------|",
    ]

    for kind in RequestKind:
        lines.append(f"| `{kind.name}` | `{kind.value}` |")

    lines.extend([
        "",
        "## AgentRequest",
        "",
        "```json",
        "{",
        '  "kind": "semantic_search",',
        '  "params": {"query": "authentication", "top_k": 5},',
        '  "request_id": "req-001",',
        '  "source": "copilot"',
        "}",
        "```",
        "",
        "| Field | Type | Description |",
        "|-------|------|-------------|",
        "| `kind` | `string` | One of the RequestKind values |",
        "| `params` | `object` | Operation-specific parameters |",
        "| `request_id` | `string` | Caller-assigned correlation ID |",
        "| `source` | `string` | Identifier of calling agent |",
        "",
        "## AgentResponse",
        "",
        "```json",
        "{",
        '  "success": true,',
        '  "data": {"snippets": [...]},',
        '  "error": "",',
        '  "request_id": "req-001",',
        '  "elapsed_ms": 42.5',
        "}",
        "```",
        "",
        "| Field | Type | Description |",
        "|-------|------|-------------|",
        "| `success` | `boolean` | Whether the request succeeded |",
        "| `data` | `object` | Structured response payload |",
        "| `error` | `string` | Error message if success is false |",
        "| `request_id` | `string` | Echoed correlation ID |",
        "| `elapsed_ms` | `number` | Processing time in milliseconds |",
        "",
    ])

    return "\n".join(lines)


def generate_tool_reference() -> str:
    """Generate Markdown documentation for the tool registry."""
    from semantic_code_intelligence.tools import TOOL_DEFINITIONS

    tools = TOOL_DEFINITIONS

    lines: list[str] = [
        "# Tool Registry Reference",
        "",
        "Auto-generated from the CodexA tool-calling interface.",
        "",
        "These tools provide a structured JSON interface for LLM agents.",
        "",
        f"**{len(tools)} tools available:**",
        "",
        "| Tool | Description |",
        "|------|-------------|",
    ]

    for tool in tools:
        desc = tool.get("description", "")
        lines.append(f"| `{tool['name']}` | {desc} |")

    lines.extend([
        "",
        "## Usage",
        "",
        "```python",
        "from semantic_code_intelligence.tools import ToolRegistry",
        "",
        'registry = ToolRegistry(project_root="/path/to/repo")',
        'result = registry.call("search", {"query": "auth"})',
        "print(result.to_json())",
        "```",
        "",
    ])

    return "\n".join(lines)


def generate_web_reference() -> str:
    """Generate Markdown documentation for the Web API and visualization layer."""
    lines: list[str] = [
        "# Web Interface Reference",
        "",
        "Auto-generated from the CodexA web module.",
        "",
        "## Overview",
        "",
        "CodexA ships an **optional** lightweight web interface (`codex web`) that",
        "bundles a REST API and a browser UI on a single port (default 8080).",
        "No external frameworks are required — the server uses Python's `http.server`.",
        "",
        "## REST API Endpoints",
        "",
        "| Method | Path | Description |",
        "|--------|------|-------------|",
        "| GET | `/health` | Server health / project metadata |",
        "| GET | `/api/search?q=&top_k=&threshold=` | Semantic code search |",
        "| GET | `/api/symbols?file=&kind=` | Symbol table browser |",
        "| GET | `/api/deps?file=` | File dependency graph |",
        "| GET | `/api/callgraph?symbol=` | Call graph edges |",
        "| GET | `/api/summary` | Project summary |",
        "| POST | `/api/ask` | Ask a natural-language question |",
        "| POST | `/api/analyze` | Validate or explain a code snippet |",
        "",
        "### POST `/api/ask` body",
        "",
        "```json",
        "{",
        '  "question": "How does authentication work?",',
        '  "top_k": 5',
        "}",
        "```",
        "",
        "### POST `/api/analyze` body",
        "",
        "```json",
        "{",
        '  "code": "def hello(): ...",',
        '  "mode": "validate"',
        "}",
        "```",
        "",
        "## Visualization (Mermaid)",
        "",
        "The `codex viz` command and `/api/viz/{kind}` endpoint produce",
        "Mermaid-compatible diagram source text.",
        "",
        "| Kind | Description |",
        "|------|-------------|",
        "| `callgraph` | Caller → callee flowchart |",
        "| `deps` | File dependency flowchart |",
        "| `symbols` | Class diagram of symbols |",
        "| `workspace` | Hub-and-spoke project map |",
        "",
        "### Example output",
        "",
        "````mermaid",
        "flowchart LR",
        '    main["main"] --> auth["auth"]',
        '    auth["auth"] --> db["db"]',
        "````",
        "",
        "## Web UI Pages",
        "",
        "| Path | Page |",
        "|------|------|",
        "| `/` | Search interface |",
        "| `/symbols` | Symbol browser |",
        "| `/workspace` | Project overview |",
        "| `/viz` | Visualization viewer |",
        "",
        "The UI is server-rendered HTML with inline CSS (dark theme) and",
        "vanilla JavaScript — no build step or npm required.",
        "",
        "## CLI Commands",
        "",
        "- `codex web [--host HOST] [--port PORT] [--path PATH]` — start the web server",
        "- `codex viz KIND [--target T] [--output FILE] [--json] [--path PATH]` — generate a diagram",
        "",
    ]

    return "\n".join(lines)


def generate_ci_reference() -> str:
    """Generate Markdown documentation for the CI/CD integration layer."""
    lines: list[str] = [
        "# CI/CD Integration Reference",
        "",
        "Auto-generated from the CodexA CI module.",
        "",
        "## Overview",
        "",
        "CodexA provides optional CI/CD integration for contribution safety and",
        "quality assurance.  All outputs are **advisory** — CodexA never modifies",
        "repository code automatically.",
        "",
        "## Quality Analyzers",
        "",
        "| Analyzer | Description |",
        "|----------|-------------|",
        "| Cyclomatic complexity | Counts decision points per function/method |",
        "| Dead code detection | Identifies unreferenced symbols via call graph |",
        "| Duplicate logic | Trigram Jaccard similarity between function bodies |",
        "| Safety validation | 17 dangerous-pattern checks (existing validator) |",
        "",
        "### Quality Report Format (JSON)",
        "",
        "```json",
        "{",
        '  "files_analyzed": 42,',
        '  "symbol_count": 180,',
        '  "issue_count": 3,',
        '  "complexity_issues": [{"symbol_name": "...", "complexity": 15, "rating": "high"}],',
        '  "dead_code": [{"symbol_name": "...", "kind": "function", "file_path": "..."}],',
        '  "duplicates": [{"symbol_a": "...", "symbol_b": "...", "similarity": 0.82}],',
        '  "safety": {"safe": true, "issues": []}',
        "}",
        "```",
        "",
        "## PR Intelligence",
        "",
        "| Feature | Description |",
        "|---------|-------------|",
        "| Change summary | File-level and symbol-level diff analysis |",
        "| Impact analysis | Blast radius via call graph traversal |",
        "| Suggested reviewers | Domain-based reviewer assignment |",
        "| Risk scoring | 0-100 composite risk with level (low/medium/high/critical) |",
        "",
        "### Risk Factors",
        "",
        "- Changeset size (file count)",
        "- Symbol removals and modifications",
        "- Safety issues in changed code",
        "- Blast radius (affected downstream symbols)",
        "",
        "## CI Workflow Templates",
        "",
        "Generate with `codex ci-gen <template>`:",
        "",
        "| Template | Description |",
        "|----------|-------------|",
        "| `analysis` | Full analysis workflow (quality + PR summary) |",
        "| `safety` | Lightweight safety-only workflow |",
        "| `precommit` | Pre-commit hook configuration |",
        "",
        "## Pre-Commit Hooks",
        "",
        "CodexA supports optional pre-commit validation:",
        "",
        "1. Safety validation — scans for dangerous patterns",
        "2. Plugin hooks — dispatches `CUSTOM_VALIDATION` for user-defined rules",
        "",
        "## CLI Commands",
        "",
        "- `codex quality [--json] [--safety-only] [--complexity-threshold N] [--pipe]`",
        "- `codex metrics [--json] [--snapshot] [--history N] [--trend] [--pipe]`",
        "- `codex gate [--json] [--strict] [--min-maintainability F] [--max-complexity N] [--pipe]`",
        "- `codex pr-summary [--json] [-f FILE ...] [--pipe]`",
        "- `codex ci-gen {analysis|safety|precommit} [-o FILE] [--python-version VER]`",
        "",
    ]

    return "\n".join(lines)


def generate_quality_metrics_reference() -> str:
    """Generate Markdown documentation for Phase 17 quality metrics features."""
    lines: list[str] = [
        "# Quality Metrics & Trends Reference",
        "",
        "Auto-generated documentation for CodexA's quality metrics, trend tracking,",
        "and quality gate enforcement features.",
        "",
        "## Maintainability Index",
        "",
        "CodexA computes a per-file and project-wide maintainability index (0-100)",
        "based on a simplified Software Engineering Institute (SEI) formula:",
        "",
        "- **Lines of code** — penalises overly large files",
        "- **Cyclomatic complexity** — penalises deeply nested logic",
        "- **Comment ratio** — rewards well-documented code",
        "",
        "| MI Range | Rating |",
        "|----------|--------|",
        "| 65-100 | Good (easy to maintain) |",
        "| 40-64 | Moderate |",
        "| 0-39 | Poor (difficult to maintain) |",
        "",
        "## Quality Snapshots",
        "",
        "Save point-in-time quality metrics via `codex metrics --snapshot`.",
        "Snapshots are stored in `.codex/memory.json` and include:",
        "",
        "- Maintainability index",
        "- Lines of code",
        "- Symbol count",
        "- Issue count",
        "- Avg complexity",
        "- Comment ratio",
        "- Timestamp and metadata",
        "",
        "## Trend Analysis",
        "",
        "Use `codex metrics --trend` to compute directional trends from snapshots:",
        "",
        "| Metric Tracked | Higher is Better |",
        "|---------------|-----------------|",
        "| `maintainability_index` | Yes |",
        "| `avg_complexity` | No |",
        "| `issue_count` | No |",
        "| `total_loc` | Yes |",
        "",
        "Trend direction: **improving**, **stable**, or **degrading**.",
        "",
        "## Quality Gates",
        "",
        "Enforce quality policies in CI pipelines with `codex gate`.",
        "",
        "| Policy | Default | Description |",
        "|--------|---------|-------------|",
        "| `min_maintainability` | 40.0 | Minimum MI score |",
        "| `max_complexity` | 25 | Maximum cyclomatic complexity |",
        "| `max_issues` | 20 | Maximum total quality issues |",
        "| `max_dead_code` | 15 | Maximum dead code symbols |",
        "| `max_duplicates` | 10 | Maximum duplicate code pairs |",
        "| `require_safety_pass` | true | Safety check must pass |",
        "",
        "Use `--strict` to exit with code 1 on failure (for CI).",
        "",
        "## CLI Commands",
        "",
        "```",
        "codex metrics                          # Current metrics",
        "codex metrics --snapshot --json        # Save snapshot, JSON output",
        "codex metrics --history 10             # Last 10 snapshots",
        "codex metrics --trend                  # Trend analysis",
        "codex gate --strict                    # CI quality gate",
        "codex gate --min-maintainability 60    # Custom threshold",
        "```",
        "",
        "## Configuration",
        "",
        "Quality settings in `.codex/config.json`:",
        "",
        "```json",
        '{',
        '  "quality": {',
        '    "complexity_threshold": 10,',
        '    "min_maintainability": 40.0,',
        '    "max_issues": 20,',
        '    "snapshot_on_index": false,',
        '    "history_limit": 50',
        '  }',
        '}',
        "```",
        "",
    ]
    return "\n".join(lines)


def generate_ai_workflows_reference() -> str:
    """Generate Markdown documentation for Phase 16 AI workflow features."""
    lines: list[str] = [
        "# AI Workflows Reference",
        "",
        "Auto-generated documentation for CodexA's advanced AI workflow features.",
        "",
        "## Multi-Turn Conversations",
        "",
        "Use `codex chat` for persistent multi-turn conversations about your codebase.",
        "",
        "| Option | Description |",
        "|--------|-------------|",
        "| `--session <id>` | Resume an existing conversation |",
        "| `--list-sessions` | Show all stored sessions |",
        "| `--max-turns <n>` | Context window limit (default: 20) |",
        "| `--json` | JSON output |",
        "| `--pipe` | Machine-readable output |",
        "",
        "### Session Persistence",
        "",
        "Sessions are stored in `.codex/sessions/<id>.json` with full message history.",
        "Each session tracks: session_id, title, messages, created_at, updated_at.",
        "",
        "### API",
        "",
        "| Class | Method | Description |",
        "|-------|--------|-------------|",
        "| `ConversationSession` | `add_user(content)` | Add user message |",
        "| `ConversationSession` | `add_assistant(content)` | Add assistant response |",
        "| `ConversationSession` | `get_messages_for_llm(max_turns)` | Get context-windowed messages |",
        "| `SessionStore` | `save(session)` | Persist to disk |",
        "| `SessionStore` | `load(session_id)` | Load from disk |",
        "| `SessionStore` | `list_sessions()` | List all sessions |",
        "| `SessionStore` | `delete(session_id)` | Remove a session |",
        "| `SessionStore` | `get_or_create(session_id)` | Resume or create |",
        "",
        "---",
        "",
        "## Autonomous Investigation Chains",
        "",
        "Use `codex investigate` for multi-step autonomous code exploration.",
        "",
        "| Option | Description |",
        "|--------|-------------|",
        "| `--max-steps <n>` | Step limit (default: 6) |",
        "| `--json` | JSON output |",
        "| `--pipe` | Machine-readable output |",
        "",
        "### How It Works",
        "",
        "1. The LLM planner receives the user's question",
        "2. It decides an action: `search`, `analyze`, `deps`, or `conclude`",
        "3. The action is executed and results fed back to the planner",
        "4. Loop continues until `conclude` or step limit is reached",
        "",
        "### Investigation Actions",
        "",
        "| Action | Description |",
        "|--------|-------------|",
        "| `search` | Semantic search over the codebase |",
        "| `analyze` | Symbol lookup and context analysis |",
        "| `deps` | Dependency analysis for a file |",
        "| `conclude` | Final answer delivery |",
        "",
        "---",
        "",
        "## Cross-Repo Refactoring",
        "",
        "Use `codex cross-refactor` to find duplicate logic across workspace repos.",
        "",
        "| Option | Description |",
        "|--------|-------------|",
        "| `--threshold <f>` | Similarity threshold (default: 0.70) |",
        "| `--json` | JSON output |",
        "| `--pipe` | Machine-readable output |",
        "",
        "### Analysis Pipeline",
        "",
        "1. Collect symbols from all registered workspace repositories",
        "2. Compare function/method bodies using trigram Jaccard similarity",
        "3. Only cross-repo matches are reported (not intra-repo)",
        "4. If LLM is configured, generates actionable refactoring suggestions",
        "",
        "---",
        "",
        "## Streaming LLM Responses",
        "",
        "The `stream_chat()` function delivers tokens incrementally from any provider.",
        "",
        "### Supported Providers",
        "",
        "| Provider | Streaming Method |",
        "|----------|-----------------|",
        "| Ollama | Native HTTP streaming (`stream: true`) |",
        "| OpenAI | Native streaming API (`stream=True`) |",
        "| Mock | Word-by-word simulation |",
        "| Other | Fallback single-token emit |",
        "",
        "### Plugin Integration",
        "",
        "The `PluginHook.ON_STREAM` hook is dispatched for each token event,",
        "allowing plugins to monitor, transform, or log streaming output.",
        "",
        "### StreamEvent Types",
        "",
        "| Kind | Description |",
        "|------|-------------|",
        "| `start` | Stream initialization with provider metadata |",
        "| `token` | A token of generated text |",
        "| `done` | Stream completed successfully |",
        "| `error` | An error occurred during streaming |",
        "",
    ]
    return "\n".join(lines)


def generate_workflow_intelligence_reference() -> str:
    """Generate the Workflow Intelligence reference document."""
    lines = [
        "# Workflow Intelligence Reference",
        "",
        "CodexA provides three developer workflow intelligence tools that combine",
        "static analysis, call-graph traversal, dependency mapping, and optional",
        "git history to surface actionable insights about your codebase.",
        "",
        "---",
        "",
        "## Hotspot Detection (`codex hotspots`)",
        "",
        "Identifies high-risk code areas using a weighted multi-factor heuristic.",
        "",
        "### Factors",
        "",
        "| Factor | Default Weight | Description |",
        "|--------|---------------|-------------|",
        "| Complexity | 0.30 | Cyclomatic complexity of the symbol body |",
        "| Duplication | 0.20 | Duplicate line density in the containing file |",
        "| Fan-in | 0.15 | Number of callers (call graph in-degree) |",
        "| Fan-out | 0.15 | Number of callees (call graph out-degree) |",
        "| Churn | 0.20 | Git change frequency (commits touching the file) |",
        "",
        "When git data is unavailable the churn weight is redistributed equally",
        "across the remaining four factors.",
        "",
        "### CLI Options",
        "",
        "| Option | Description |",
        "|--------|-------------|",
        "| `--path / -p` | Project root (default: `.`) |",
        "| `--top-n / -n` | Number of hotspots to report (default: 20) |",
        "| `--include-git / --no-git` | Toggle git churn analysis |",
        "| `--json` | JSON output |",
        "| `--pipe` | Machine-readable plain text |",
        "",
        "### API",
        "",
        "| Function | Description |",
        "|----------|-------------|",
        "| `analyze_hotspots(symbols, call_graph, dep_map, root, *, top_n, include_git, weights)` | Run full hotspot analysis |",
        "",
        "### Plugin Hooks",
        "",
        "| Hook | When |",
        "|------|------|",
        "| `PRE_HOTSPOT_ANALYSIS` | Before hotspot scoring begins |",
        "| `POST_HOTSPOT_ANALYSIS` | After the hotspot report is built |",
        "",
        "---",
        "",
        "## Impact Analysis (`codex impact <target>`)",
        "",
        "Predicts the blast radius of modifying a symbol or file using BFS over",
        "the call graph and dependency map.",
        "",
        "### How It Works",
        "",
        "1. Resolve the target to symbols or a file path",
        "2. Seed the BFS queue with the target's names and files",
        "3. Walk callers in the call graph (direct → transitive)",
        "4. Walk importers in the dependency map",
        "5. Build dependency chains tracing paths back to the target",
        "",
        "### CLI Options",
        "",
        "| Option | Description |",
        "|--------|-------------|",
        "| `TARGET` | Symbol name or relative file path |",
        "| `--path / -p` | Project root (default: `.`) |",
        "| `--max-depth / -d` | BFS depth limit (default: 5) |",
        "| `--json` | JSON output |",
        "| `--pipe` | Machine-readable plain text |",
        "",
        "### API",
        "",
        "| Function | Description |",
        "|----------|-------------|",
        "| `analyze_impact(target, symbols, call_graph, dep_map, root, *, max_depth)` | Run impact analysis |",
        "",
        "### Plugin Hooks",
        "",
        "| Hook | When |",
        "|------|------|",
        "| `PRE_IMPACT_ANALYSIS` | Before impact BFS begins |",
        "| `POST_IMPACT_ANALYSIS` | After the impact report is built |",
        "",
        "---",
        "",
        "## Symbol Trace (`codex trace <symbol>`)",
        "",
        "Traces execution relationships upstream (callers) and downstream (callees)",
        "to visualise call flow through the codebase.",
        "",
        "### How It Works",
        "",
        "1. Resolve the target symbol",
        "2. BFS upstream: walk `callers_of` edges to find all transitive callers",
        "3. BFS downstream: walk `callees_of` edges to find all transitive callees",
        "4. Collect trace edges connecting the nodes",
        "",
        "### CLI Options",
        "",
        "| Option | Description |",
        "|--------|-------------|",
        "| `SYMBOL` | Symbol name to trace |",
        "| `--path / -p` | Project root (default: `.`) |",
        "| `--max-depth / -d` | BFS depth limit (default: 5) |",
        "| `--json` | JSON output |",
        "| `--pipe` | Machine-readable plain text |",
        "",
        "### API",
        "",
        "| Function | Description |",
        "|----------|-------------|",
        "| `trace_symbol(target, symbols, call_graph, *, max_depth)` | Run symbol trace |",
        "",
        "### Plugin Hooks",
        "",
        "| Hook | When |",
        "|------|------|",
        "| `PRE_TRACE` | Before trace BFS begins |",
        "| `POST_TRACE` | After the trace result is built |",
        "",
        "---",
        "",
        "## Output Formats",
        "",
        "All three commands support three output modes:",
        "",
        "| Flag | Format | Use Case |",
        "|------|--------|----------|",
        "| *(none)* | Rich terminal | Interactive development |",
        "| `--json` | Pretty JSON | Programmatic consumption |",
        "| `--pipe` | Tab-separated text | Shell pipelines and CI |",
        "",
        "---",
        "",
        "## Data Classes",
        "",
        "### Hotspots",
        "",
        "| Class | Fields |",
        "|-------|--------|",
        "| `HotspotFactor` | `name`, `raw_value`, `normalized`, `weight` |",
        "| `Hotspot` | `name`, `file_path`, `kind`, `risk_score`, `factors` |",
        "| `HotspotReport` | `files_analyzed`, `symbols_analyzed`, `hotspots` |",
        "",
        "### Impact",
        "",
        "| Class | Fields |",
        "|-------|--------|",
        "| `AffectedSymbol` | `name`, `file_path`, `kind`, `relationship`, `depth` |",
        "| `AffectedModule` | `file_path`, `relationship`, `depth` |",
        "| `DependencyChain` | `path` (list of strings) |",
        "| `ImpactReport` | `target`, `target_kind`, `direct_symbols`, `transitive_symbols`, `affected_modules`, `chains` |",
        "",
        "### Trace",
        "",
        "| Class | Fields |",
        "|-------|--------|",
        "| `TraceNode` | `name`, `file_path`, `kind`, `depth` |",
        "| `TraceEdge` | `caller`, `callee`, `file_path` |",
        "| `TraceResult` | `target`, `target_file`, `upstream`, `downstream`, `edges` |",
        "",
    ]
    return "\n".join(lines)


def generate_all_docs(output_dir: Path) -> list[str]:
    """Generate all documentation files into the output directory.

    Returns:
        List of generated file paths (relative to output_dir).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    # CLI reference needs the actual CLI group
    try:
        from semantic_code_intelligence.cli.main import cli
        cli_md = generate_cli_reference(cli)
        (output_dir / "CLI.md").write_text(cli_md, encoding="utf-8")
        generated.append("CLI.md")
    except Exception:
        pass

    # Plugin reference
    try:
        plugin_md = generate_plugin_reference()
        (output_dir / "PLUGINS.md").write_text(plugin_md, encoding="utf-8")
        generated.append("PLUGINS.md")
    except Exception:
        pass

    # Bridge reference
    try:
        bridge_md = generate_bridge_reference()
        (output_dir / "BRIDGE.md").write_text(bridge_md, encoding="utf-8")
        generated.append("BRIDGE.md")
    except Exception:
        pass

    # Tool reference
    try:
        tool_md = generate_tool_reference()
        (output_dir / "TOOLS.md").write_text(tool_md, encoding="utf-8")
        generated.append("TOOLS.md")
    except Exception:
        pass

    # Web / API reference
    try:
        web_md = generate_web_reference()
        (output_dir / "WEB.md").write_text(web_md, encoding="utf-8")
        generated.append("WEB.md")
    except Exception:
        pass

    # CI/CD reference
    try:
        ci_md = generate_ci_reference()
        (output_dir / "CI.md").write_text(ci_md, encoding="utf-8")
        generated.append("CI.md")
    except Exception:
        pass

    # AI Workflows reference
    try:
        ai_md = generate_ai_workflows_reference()
        (output_dir / "AI_WORKFLOWS.md").write_text(ai_md, encoding="utf-8")
        generated.append("AI_WORKFLOWS.md")
    except Exception:
        pass

    # Quality Metrics reference
    try:
        qm_md = generate_quality_metrics_reference()
        (output_dir / "QUALITY_METRICS.md").write_text(qm_md, encoding="utf-8")
        generated.append("QUALITY_METRICS.md")
    except Exception:
        pass

    # Workflow Intelligence reference
    try:
        wi_md = generate_workflow_intelligence_reference()
        (output_dir / "WORKFLOW_INTELLIGENCE.md").write_text(wi_md, encoding="utf-8")
        generated.append("WORKFLOW_INTELLIGENCE.md")
    except Exception:
        pass

    return generated
