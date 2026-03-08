"""CLI command: tool — invoke and manage AI agent tools."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_success,
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

    executor = ToolExecutor(Path(".").resolve())
    tools = executor.available_tools

    if json_mode:
        click.echo(json_mod.dumps({"tools": tools, "count": len(tools)}, indent=2))
        return

    console.print(f"\n[bold cyan]Available Tools[/bold cyan] ({len(tools)} total)\n")
    for t in tools:
        source = t.get("source", "built-in")
        console.print(f"  [bold]{t['name']}[/bold] [{source}]")
        console.print(f"    {t.get('description', 'No description')}")
        params = t.get("parameters", {})
        if params:
            for pname, pdef in params.items():
                req = " [required]" if pdef.get("required") else ""
                ptype = pdef.get("type", "any")
                console.print(f"      --{pname} ({ptype}){req}")
        console.print()


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
    result = executor.execute(invocation)

    if json_mode or pipe:
        click.echo(result.to_json(indent=2 if json_mode else None))
        return

    if result.success:
        print_success(f"Tool '{tool_name}' executed successfully")
        console.print(f"  [dim]Execution time: {result.execution_time_ms:.1f}ms[/dim]")
        console.print()
        payload = result.result_payload
        if payload:
            click.echo(json_mod.dumps(payload, indent=2))
    else:
        print_error(f"Tool '{tool_name}' failed")
        if result.error:
            console.print(f"  [red]Error code:[/red] {result.error.error_code}")
            console.print(f"  [red]Message:[/red] {result.error.error_message}")


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
        return

    if json_mode:
        click.echo(json_mod.dumps(schema, indent=2))
        return

    console.print(f"\n[bold cyan]{schema['name']}[/bold cyan]")
    console.print(f"  {schema.get('description', 'No description')}")
    console.print()
    params = schema.get("parameters", {})
    if params:
        console.print("  [bold]Parameters:[/bold]")
        for pname, pdef in params.items():
            req = " [required]" if pdef.get("required") else ""
            ptype = pdef.get("type", "any")
            desc = pdef.get("description", "")
            default = pdef.get("default")
            line = f"    {pname} ({ptype}){req}"
            if default is not None:
                line += f" [default: {default}]"
            console.print(line)
            if desc:
                console.print(f"      {desc}")
    else:
        console.print("  [dim]No parameters[/dim]")
    console.print()
