"""CLI command: explain — structural explanation of a symbol or file."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.analysis.ai_features import explain_file, explain_symbol
from semantic_code_intelligence.context.engine import ContextBuilder
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
)

logger = get_logger("cli.explain")


@click.command("explain")
@click.argument("target", type=str)
@click.option(
    "--file",
    "-f",
    "file_path",
    default=None,
    type=click.Path(exists=True, resolve_path=True),
    help="Source file containing the symbol.",
)
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
def explain_cmd(
    ctx: click.Context,
    target: str,
    file_path: str | None,
    path: str,
    json_mode: bool,
) -> None:
    """Explain a code symbol or all symbols in a file.

    Examples:

        codexa explain MyClass -f src/models.py

        codexa explain --file src/main.py .

        codexa explain search_codebase
    """
    import json as json_mod

    root = Path(path).resolve()

    if target == "." and file_path:
        # Explain entire file
        explanations = explain_file(file_path)
        if json_mode:
            click.echo(json_mod.dumps([e.to_dict() for e in explanations], indent=2))
        else:
            for exp in explanations:
                console.print(exp.render(), markup=False)
                console.print()
        return

    # Explain specific symbol
    builder = ContextBuilder()
    if file_path:
        builder.index_file(file_path)
        symbols = builder.get_symbols(file_path)
        matches = [s for s in symbols if s.name == target]
    else:
        # Scan repo for the symbol
        from semantic_code_intelligence.config.settings import load_config
        from semantic_code_intelligence.indexing.scanner import scan_repository

        config = load_config(root)
        scanned = scan_repository(root, config.index)
        for sf in scanned:
            full_path = str(root / sf.relative_path)
            try:
                builder.index_file(full_path)
            except Exception:
                logger.debug("Failed to index %s", full_path)
                continue
        matches = builder.find_symbol(target)

    if not matches:
        print_error(f"Symbol '{target}' not found.")
        return

    explanations = [explain_symbol(s, builder) for s in matches]
    if json_mode:
        click.echo(json_mod.dumps([e.to_dict() for e in explanations], indent=2))
    else:
        for exp in explanations:
            console.print(exp.render(), markup=False)
            console.print()
        print_info(f"Found {len(explanations)} match(es) for '{target}'.")
