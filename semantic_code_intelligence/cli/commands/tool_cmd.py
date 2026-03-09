"""CLI command: tool — invoke and manage AI agent tools."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_header,
    print_separator,
    print_success,
    print_warning,
)

logger = get_logger("cli.tool")


@click.group("tool")
def tool_cmd() -> None:
    """AI Agent Tooling Protocol — invoke and inspect tools.

    Provides a CLI interface to the same tool execution engine that
    AI coding agents use over the Bridge HTTP API.

    Examples:

        codex tool list
        codex tool run semantic_search --arg query="parse file"
        codex tool schema semantic_search
    """


@tool_cmd.command("list")
@click.option(
    "--json-output", "--json", "json_mode",
    is_flag=True, default=False,
    help="Output in JSON format.",
)
def tool_list(json_mode: bool) -> None:
    """List all available tools with their descriptions."""
    from semantic_code_intelligence.tools import TOOL_DEFINITIONS
    from semantic_code_intelligence.tools.executor import ToolExecutor

    from rich.table import Table

    executor = ToolExecutor(Path(".").resolve())
    tools = executor.available_tools

    if json_mode:
        click.echo(json_mod.dumps({"tools": tools, "count": len(tools)}, indent=2))
        return

    print_header("Available Tools", f"{len(tools)} registered")
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Tool", style="bold")
    table.add_column("Source", style="dim")
    table.add_column("Parameters", style="yellow")
    table.add_column("Description")

    for t in tools:
        source = t.get("source", "built-in")
        params = t.get("parameters", {})
        param_names = ", ".join(params.keys()) if params else "-"
        desc = t.get("description", "No description")
        if len(desc) > 60:
            desc = desc[:57] + "..."
        table.add_row(t["name"], source, param_names, desc)

    console.print(table)
    print_separator()


@tool_cmd.command("run")
@click.argument("tool_name")
@click.option(
    "--arg", "-a",
    multiple=True,
    help="Tool argument as key=value (repeatable).",
)
@click.option(
    "--path", "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.option(
    "--json-output", "--json", "json_mode",
    is_flag=True, default=False,
    help="Output in JSON format.",
)
@click.option(
    "--pipe",
    is_flag=True, default=False,
    help="Plain text output for piping / CI.",
)
@click.pass_context
def tool_run(
    ctx: click.Context,
    tool_name: str,
    arg: tuple[str, ...],
    path: str,
    json_mode: bool,
    pipe: bool,
) -> None:
    """Run TOOL_NAME with the given arguments.

    Arguments are passed as --arg key=value pairs.

    Examples:

        codex tool run semantic_search --arg query="parse file"
        codex tool run explain_symbol --arg symbol_name=ToolRegistry
        codex tool run summarize_repo --json
    """
    from semantic_code_intelligence.tools.executor import ToolExecutor
    from semantic_code_intelligence.tools.protocol import ToolInvocation

    project_root = Path(path).resolve()

    # Parse arguments
    arguments: dict[str, str] = {}
    for a in arg:
        if "=" not in a:
            print_error(f"Invalid argument format: {a!r} (expected key=value)")
            ctx.exit(1)
            return
        key, value = a.split("=", 1)
        arguments[key.strip()] = value.strip()

    executor = ToolExecutor(project_root)
    invocation = ToolInvocation(tool_name=tool_name, arguments=arguments)

    if not (json_mode or pipe):
        print_separator(f"Running: {tool_name}")

    result = executor.execute(invocation)

    if json_mode or pipe:
        click.echo(result.to_json(indent=2 if json_mode else None))
        return

    if result.success:
        print_success(f"Tool '{tool_name}' completed in {result.execution_time_ms:.1f}ms")
        print_separator()
        payload = result.result_payload
        if payload:
            _render_tool_result(tool_name, payload)
    else:
        print_error(f"Tool '{tool_name}' failed")
        if result.error:
            console.print(f"  [red]Error code:[/red] {result.error.error_code}")
            console.print(f"  [red]Message:[/red] {result.error.error_message}")
        print_separator()


def _render_tool_result(tool_name: str, payload: dict) -> None:
    """Render a tool result payload with rich formatting."""
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table

    # explanation results (explain_symbol, explain_file, get_context)
    if "explanation" in payload:
        console.print(Panel(payload["explanation"], title="Explanation", border_style="cyan"))
        if payload.get("code_snippet"):
            lang = payload.get("language", "python")
            console.print(Syntax(payload["code_snippet"], lang, theme="monokai", line_numbers=True))
        return

    # search results
    if "results" in payload and isinstance(payload["results"], list):
        results = payload["results"]
        console.print(f"  [bold]{len(results)} result(s)[/bold]\n")
        for i, r in enumerate(results[:20], 1):
            score = r.get("score", r.get("similarity", 0))
            path = r.get("file_path", r.get("path", "?"))
            console.print(f"  [cyan]{i}.[/cyan] [bold]{path}[/bold]  [dim](score: {score:.3f})[/dim]")
            snippet = r.get("content", r.get("snippet", ""))
            if snippet:
                preview = snippet.strip()[:120].replace("\n", " ")
                console.print(f"     [dim]{preview}[/dim]")
        return

    # call graph
    if "call_graph" in payload or "callers" in payload or "callees" in payload:
        if payload.get("callers"):
            console.print("  [bold]Callers:[/bold]")
            for c in payload["callers"]:
                console.print(f"    [green]←[/green] {c}")
        if payload.get("callees"):
            console.print("  [bold]Callees:[/bold]")
            for c in payload["callees"]:
                console.print(f"    [magenta]→[/magenta] {c}")
        return

    # references
    if "references" in payload:
        refs = payload["references"]
        console.print(f"  [bold]{len(refs)} reference(s)[/bold]\n")
        for ref in refs[:30]:
            path = ref.get("file_path", ref.get("path", "?"))
            line = ref.get("line", "?")
            console.print(f"    [cyan]{path}[/cyan]:[yellow]{line}[/yellow]")
        return

    # dependencies
    if "dependencies" in payload or "imports" in payload:
        deps = payload.get("dependencies", payload.get("imports", []))
        console.print(f"  [bold]{len(deps)} dependenc(ies)[/bold]\n")
        for d in deps:
            if isinstance(d, str):
                console.print(f"    [dim]→[/dim] {d}")
            elif isinstance(d, dict):
                console.print(f"    [dim]→[/dim] {d.get('name', d.get('module', str(d)))}")
        return

    # summary
    if "summary" in payload:
        console.print(Panel(payload["summary"], title="Summary", border_style="green"))
        return

    # fallback: pretty-print JSON
    console.print(Syntax(json_mod.dumps(payload, indent=2), "json", theme="monokai"))


@tool_cmd.command("schema")
@click.argument("tool_name")
@click.option(
    "--json-output", "--json", "json_mode",
    is_flag=True, default=False,
    help="Output in JSON format.",
)
def tool_schema(tool_name: str, json_mode: bool) -> None:
    """Show the schema definition for TOOL_NAME.

    Examples:

        codex tool schema semantic_search
        codex tool schema explain_symbol --json
    """
    from semantic_code_intelligence.tools.executor import ToolExecutor

    executor = ToolExecutor(Path(".").resolve())
    schema = executor.get_tool_schema(tool_name)

    if schema is None:
        print_error(f"Unknown tool: {tool_name}")
        available = [t["name"] for t in ToolExecutor(Path(".").resolve()).available_tools]
        if available:
            print_warning(f"Available tools: {', '.join(available)}")
        return

    if json_mode:
        click.echo(json_mod.dumps(schema, indent=2))
        return

    from rich.table import Table

    print_header(schema["name"], schema.get("description", ""))
    params = schema.get("parameters", {})
    if params:
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Parameter", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Required", style="red")
        table.add_column("Default", style="dim")
        table.add_column("Description")
        for pname, pdef in params.items():
            req = "yes" if pdef.get("required") else ""
            ptype = pdef.get("type", "any")
            desc = pdef.get("description", "")
            default = str(pdef["default"]) if "default" in pdef and pdef["default"] is not None else ""
            table.add_row(pname, ptype, req, default, desc)
        console.print(table)
    else:
        console.print("  [dim]No parameters[/dim]")
    print_separator()
