"""CLI command: search - Perform semantic search across the indexed codebase."""

from __future__ import annotations

import json
from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.services.search_service import search_codebase
from semantic_code_intelligence.search.formatter import format_results_json, format_results_rich
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_warning,
    console,
)

logger = get_logger("cli.search")


@click.command("search")
@click.argument("query", type=str)
@click.option(
    "--top-k",
    "-k",
    default=None,
    type=int,
    help="Number of results to return (overrides config).",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output results in JSON format for AI integration.",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def search_cmd(
    ctx: click.Context,
    query: str,
    top_k: int | None,
    json_mode: bool,
    path: str,
) -> None:
    """Search the indexed codebase using a natural language query.

    Examples:

        codex search "jwt verification"

        codex search "database connection handling" --json

        codex search "error handling" -k 5
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(
            f"Project not initialized at {root}. Run 'codex init' first."
        )
        ctx.exit(1)
        return

    config = load_config(root)
    result_count = top_k or config.search.top_k

    try:
        results = search_codebase(
            query=query,
            project_root=root,
            top_k=result_count,
        )
    except FileNotFoundError:
        if json_mode:
            click.echo(format_results_json(query, [], result_count))
        else:
            print_warning(
                "Search index is empty. Run 'codex index' to build the index."
            )
        return

    if json_mode:
        click.echo(format_results_json(query, results, result_count))
    else:
        format_results_rich(query, results)
