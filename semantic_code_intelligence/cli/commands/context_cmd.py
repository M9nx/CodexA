"""CLI command: context — generate structured context for external tools."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
)

logger = get_logger("cli.context")


@click.command("context")
@click.argument("mode", type=click.Choice(["query", "symbol", "file", "repo"]))
@click.argument("target", required=False, default=None)
@click.option(
    "--top-k",
    "-k",
    default=5,
    type=int,
    help="Number of results for query mode.",
)
@click.option(
    "--file-path",
    "-f",
    default=None,
    type=str,
    help="File path hint (for symbol mode).",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output raw JSON (default is pretty-printed).",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def context_cmd(
    ctx: click.Context,
    mode: str,
    target: str | None,
    top_k: int,
    file_path: str | None,
    json_mode: bool,
    path: str,
) -> None:
    """Generate structured context for external AI pipelines.

    \b
    Modes:
      query   — semantic search (TARGET = search query)
      symbol  — symbol context  (TARGET = symbol name)
      file    — file context    (TARGET = file path)
      repo    — repo summary    (no TARGET needed)
    """
    from semantic_code_intelligence.bridge.context_provider import ContextProvider

    project_root = Path(path)
    provider = ContextProvider(project_root)

    try:
        if mode == "query":
            if not target:
                print_error("Query mode requires a TARGET argument (the search query).")
                ctx.exit(1)
                return
            data = provider.context_for_query(query=target, top_k=top_k)

        elif mode == "symbol":
            if not target:
                print_error("Symbol mode requires a TARGET argument (symbol name).")
                ctx.exit(1)
                return
            data = provider.context_for_symbol(
                symbol_name=target, file_path=file_path,
            )

        elif mode == "file":
            if not target:
                print_error("File mode requires a TARGET argument (file path).")
                ctx.exit(1)
                return
            data = provider.context_for_file(file_path=target)

        elif mode == "repo":
            data = provider.context_for_repo()

        else:
            print_error(f"Unknown mode: {mode}")
            ctx.exit(1)
            return

    except Exception as exc:
        logger.exception("Context generation failed")
        print_error(f"Error: {exc}")
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json_mod.dumps(data, indent=2))
    else:
        from rich.syntax import Syntax

        formatted = json_mod.dumps(data, indent=2)
        console.print(Syntax(formatted, "json", theme="monokai"))
