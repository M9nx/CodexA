"""CLI command: viz — generate Mermaid-compatible visualizations."""

from __future__ import annotations

import json
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    console,
)

logger = get_logger("cli.viz")


@click.command("viz")
@click.argument(
    "kind",
    type=click.Choice(["callgraph", "deps", "symbols", "workspace"], case_sensitive=False),
)
@click.option(
    "--target",
    "-t",
    default="",
    type=str,
    help="Symbol name or file path to visualize.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(dir_okay=False, resolve_path=True),
    help="Write Mermaid output to a file instead of stdout.",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output as JSON with a 'mermaid' field.",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def viz_cmd(
    ctx: click.Context,
    kind: str,
    target: str,
    output: str | None,
    json_mode: bool,
    path: str,
) -> None:
    """Generate Mermaid-compatible diagrams from codebase analysis.

    KIND is one of: callgraph, deps, symbols, workspace.

    Examples:

        codexa viz callgraph

        codexa viz deps --target src/main.py

        codexa viz symbols --target auth.py -o symbols.mmd

        codexa viz callgraph --json
    """
    from semantic_code_intelligence.bridge.context_provider import ContextProvider
    from semantic_code_intelligence.web.visualize import (
        render_call_graph,
        render_dependency_graph,
        render_symbol_map,
        render_workspace_graph,
    )

    project_root = Path(path)
    provider = ContextProvider(project_root)

    kind_lower = kind.lower()

    try:
        if kind_lower == "callgraph":
            data = provider.get_call_graph(symbol_name=target)
            mermaid = render_call_graph(data.get("edges", []))
        elif kind_lower == "deps":
            data = provider.get_dependencies(file_path=target)
            mermaid = render_dependency_graph(data)
        elif kind_lower == "symbols":
            builder = provider._ensure_indexed()
            symbols = builder.get_all_symbols()
            if target:
                symbols = [s for s in symbols if target in s.file_path]
            sym_dicts = [s.to_dict() for s in symbols[:100]]
            mermaid = render_symbol_map(sym_dicts, file_path=target)
        elif kind_lower == "workspace":
            # Try to load workspace repos
            try:
                from semantic_code_intelligence.workspace import Workspace
                ws = Workspace.load(project_root)
                repos = [r.to_dict() for r in ws.repos] if ws.repos else []
            except Exception:
                repos = []
            mermaid = render_workspace_graph(repos)
        else:
            print_error(f"Unknown visualization kind: {kind}")
            return
    except Exception as exc:
        print_error(f"Visualization error: {exc}")
        return

    # Output
    if json_mode:
        click.echo(json.dumps({"kind": kind_lower, "mermaid": mermaid}, indent=2))
    elif output:
        Path(output).write_text(mermaid, encoding="utf-8")
        print_info(f"Written to {output}")
    else:
        console.print(mermaid)
