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

    return generated
