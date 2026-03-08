"""CLI command: trace — trace execution relationships of a symbol."""

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

logger = get_logger("cli.trace")


@click.command("trace")
@click.argument("symbol")
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
@click.option(
    "--max-depth", "-d",
    type=int, default=5,
    help="Maximum traversal depth (default: 5).",
)
@click.pass_context
def trace_cmd(
    ctx: click.Context,
    symbol: str,
    path: str,
    json_mode: bool,
    pipe: bool,
    max_depth: int,
) -> None:
    """Trace execution relationships for SYMBOL.

    Shows upstream callers and downstream callees to map the flow of
    execution through the codebase.

    Examples:

        codex trace parse_file

        codex trace MyClass.process --json

        codex trace build_context --max-depth 3 --pipe
    """
    from semantic_code_intelligence.ci.trace import trace_symbol
    from semantic_code_intelligence.context.engine import CallGraph, ContextBuilder

    root = Path(path).resolve()
    builder = ContextBuilder()

    py_files = sorted(root.rglob("*.py"))
    py_files = [f for f in py_files if ".venv" not in f.parts and "__pycache__" not in f.parts]

    for fp in py_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            builder.index_file(str(fp), content)
        except Exception:
            logger.debug("Failed to index %s", fp)
            continue

    symbols = builder.get_all_symbols()
    call_graph = CallGraph()
    call_graph.build(symbols)
    call_graph.build(symbols)

    result = trace_symbol(symbol, symbols, call_graph, max_depth=max_depth)

    if not result.target_file:
        if json_mode:
            click.echo(json_mod.dumps({"error": f"Symbol '{symbol}' not found"}, indent=2))
        elif pipe:
            click.echo(f"ERROR symbol_not_found {symbol}")
        else:
            print_error(f"Symbol '{symbol}' not found in the project.")
        return

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
    elif pipe:
        click.echo(f"target={result.target} file={result.target_file} up={len(result.upstream)} down={len(result.downstream)}")
        for n in result.upstream:
            click.echo(f"  UP    depth={n.depth}  {n.kind:<10}  {n.file_path}:{n.name}")
        for n in result.downstream:
            click.echo(f"  DOWN  depth={n.depth}  {n.kind:<10}  {n.file_path}:{n.name}")
    else:
        console.print(f"\n[bold]Symbol Trace[/bold] — [cyan]{result.target}[/cyan]  ({result.target_file})\n")
        if not result.upstream and not result.downstream:
            print_success("No execution relationships found.")
            return

        if result.upstream:
            console.print(f"[bold]Upstream callers[/bold] (max depth {result.max_upstream_depth}):")
            for n in result.upstream:
                console.print(f"  [yellow]{n.name}[/yellow]  depth={n.depth}  ({n.kind})  [dim]{n.file_path}[/dim]")

        if result.downstream:
            console.print(f"\n[bold]Downstream callees[/bold] (max depth {result.max_downstream_depth}):")
            for n in result.downstream:
                console.print(f"  [green]{n.name}[/green]  depth={n.depth}  ({n.kind})  [dim]{n.file_path}[/dim]")

        console.print(f"\n[bold]Edges:[/bold] {len(result.edges)}  |  [bold]Total nodes:[/bold] {result.total_nodes}")
        console.print()
