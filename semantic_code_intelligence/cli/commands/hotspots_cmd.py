"""CLI command: hotspots — identify high-risk code hotspots."""

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

logger = get_logger("cli.hotspots")


@click.command("hotspots")
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
    "--top-n", "-n",
    type=int, default=20,
    help="Number of hotspots to report (default: 20).",
)
@click.option(
    "--include-git/--no-git",
    default=True,
    help="Include git churn data (default: enabled).",
)
@click.pass_context
def hotspots_cmd(
    ctx: click.Context,
    path: str,
    json_mode: bool,
    pipe: bool,
    top_n: int,
    include_git: bool,
) -> None:
    """Identify high-risk code hotspots via multi-factor analysis.

    Combines complexity, duplication, fan-in/out, and git churn to
    score symbols by maintenance risk.

    Examples:

        codexa hotspots

        codexa hotspots --top-n 10 --json

        codexa hotspots --no-git --pipe
    """
    from semantic_code_intelligence.ci.hotspots import analyze_hotspots
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
            logger.debug("Failed to index %s", fp)
            continue

    symbols = builder.get_all_symbols()
    call_graph = CallGraph()
    call_graph.build(symbols)

    try:
        report = analyze_hotspots(
            symbols, call_graph, dep_map, root,
            top_n=top_n, include_git=include_git,
        )
    except Exception as exc:
        logger.debug("Hotspot analysis failed", exc_info=True)
        print_error(f"Hotspot analysis failed: {exc}")
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json_mod.dumps(report.to_dict(), indent=2))
    elif pipe:
        click.echo(f"files={report.files_analyzed} symbols={report.symbols_analyzed} hotspots={len(report.hotspots)}")
        for h in report.hotspots:
            click.echo(f"  {h.risk_score:.3f}  {h.kind:<10}  {h.file_path}:{h.name}")
    else:
        console.print(f"\n[bold]Hotspot Analysis[/bold] — {report.files_analyzed} files, {report.symbols_analyzed} symbols\n")
        if not report.hotspots:
            print_success("No significant hotspots detected.")
            return
        for i, h in enumerate(report.hotspots, 1):
            colour = "red" if h.risk_score >= 0.7 else "yellow" if h.risk_score >= 0.4 else "green"
            console.print(f"  [{colour}]{i:>3}. {h.risk_score:.3f}[/{colour}]  {h.kind:<10}  [cyan]{h.file_path}[/cyan]:[bold]{h.name}[/bold]")
            for f in h.factors:
                console.print(f"        {f.name}: {f.raw_value:.2f} (norm={f.normalized:.2f}, w={f.weight:.2f})")
        console.print()
