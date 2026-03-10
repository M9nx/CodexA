"""CLI command: summary — generate structured repository summary."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.analysis.ai_features import summarize_repository
from semantic_code_intelligence.config.settings import load_config
from semantic_code_intelligence.context.engine import ContextBuilder
from semantic_code_intelligence.indexing.scanner import scan_repository
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
    print_success,
)

logger = get_logger("cli.summary")


@click.command("summary")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
@click.pass_context
def summary_cmd(ctx: click.Context, path: str, json_mode: bool) -> None:
    """Generate a structured summary of the repository.

    Shows language breakdown, symbol counts, and top functions/classes.

    Examples:

        codexa summary

        codexa summary --json

        codexa summary -p /path/to/project
    """
    root = Path(path).resolve()
    config = load_config(root)
    scanned = scan_repository(root, config.index)

    if not scanned:
        print_error("No source files found in the project.")
        return

    if not json_mode:
        print_info(f"Analyzing {len(scanned)} files...")
    builder = ContextBuilder()
    for sf in scanned:
        full_path = str(root / sf.relative_path)
        try:
            builder.index_file(full_path)
        except Exception:
            logger.debug("Could not parse %s", sf.relative_path)

    summary = summarize_repository(builder)

    if json_mode:
        click.echo(summary.to_json())
    else:
        console.print(summary.render(), markup=False)
        print_success(f"Summary generated for {summary.total_files} files.")
