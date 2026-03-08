"""CLI command: impact — analyse blast radius of code changes."""

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

logger = get_logger("cli.impact")


@click.command("impact")
@click.argument("target")
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
def impact_cmd(
    ctx: click.Context,
    target: str,
    path: str,
    json_mode: bool,
    pipe: bool,
    max_depth: int,
) -> None:
    """Analyse the blast radius of a change to TARGET.

    TARGET can be a symbol name (function/class) or a file path relative
    to the project root.

    Examples:

        codex impact parse_file

        codex impact src/parser.py --json

        codex impact MyClass --max-depth 3 --pipe
    """
    from semantic_code_intelligence.ci.impact import analyze_impact
    from semantic_code_intelligence.context.engine import CallGraph, ContextBuilder, DependencyMap

    root = Path(path).resolve()
    builder = ContextBuilder()
    dep_map = DependencyMap()

    py_files = sorted(root.rglob("*.py"))
    py_files = [f for f in py_files if ".venv" not in f.parts and "__pycache__" not in f.parts]

    for fp in py_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            builder.index_file(str(fp), content)
            dep_map.add_file(str(fp), content)
        except Exception:
            continue

    symbols = builder.get_all_symbols()
    call_graph = CallGraph()
    call_graph.build(symbols)

    report = analyze_impact(
        target, symbols, call_graph, dep_map, root,
        max_depth=max_depth,
    )

    if json_mode:
        click.echo(json_mod.dumps(report.to_dict(), indent=2))
    elif pipe:
        click.echo(f"target={report.target} kind={report.target_kind} affected={report.total_affected}")
        for s in report.direct_symbols:
            click.echo(f"  DIRECT  {s.relationship:<20}  {s.file_path}:{s.name}")
        for s in report.transitive_symbols:
            click.echo(f"  TRANS   {s.relationship:<20}  {s.file_path}:{s.name}")
        for m in report.affected_modules:
            click.echo(f"  MODULE  {m.relationship:<20}  {m.file_path}")
    else:
        console.print(f"\n[bold]Impact Analysis[/bold] — target: [cyan]{report.target}[/cyan] ({report.target_kind})\n")
        if report.total_affected == 0:
            print_success("No downstream impact detected.")
            return

        if report.direct_symbols:
            console.print("[bold]Direct callers:[/bold]")
            for s in report.direct_symbols:
                console.print(f"  [yellow]{s.name}[/yellow]  ({s.kind})  [dim]{s.file_path}[/dim]")

        if report.transitive_symbols:
            console.print("\n[bold]Transitive callers:[/bold]")
            for s in report.transitive_symbols:
                console.print(f"  [yellow]{s.name}[/yellow]  depth={s.depth}  [dim]{s.file_path}[/dim]")

        if report.affected_modules:
            console.print("\n[bold]Affected modules:[/bold]")
            for m in report.affected_modules:
                console.print(f"  [cyan]{m.file_path}[/cyan]  ({m.relationship}, depth={m.depth})")

        console.print(f"\n[bold]Total affected:[/bold] {report.total_affected}")
        console.print()
