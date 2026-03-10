"""CLI command: deps — show file/project dependency map."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import load_config
from semantic_code_intelligence.context.engine import DependencyMap
from semantic_code_intelligence.indexing.scanner import scan_repository
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
)

logger = get_logger("cli.deps")


@click.command("deps")
@click.argument("target", type=str, default=".")
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
def deps_cmd(ctx: click.Context, target: str, path: str, json_mode: bool) -> None:
    """Show the dependency/import map for a file or the whole project.

    TARGET can be a specific file path or '.' for the whole project.

    Examples:

        codexa deps src/main.py

        codexa deps .

        codexa deps . --json
    """
    import json as json_mod

    root = Path(path).resolve()
    dep_map = DependencyMap()

    if target != ".":
        # Single file
        fpath = (root / target).resolve()
        if not fpath.exists():
            print_error(f"File not found: {target}")
            return
        content = fpath.read_text(encoding="utf-8", errors="replace")
        dep_map.add_file(str(fpath), content)
    else:
        # Whole project
        config = load_config(root)
        scanned = scan_repository(root, config.index)
        if not json_mode:
            print_info(f"Analyzing dependencies across {len(scanned)} files...")
        for sf in scanned:
            full_path = root / sf.relative_path
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                dep_map.add_file(str(full_path), content)
            except Exception:
                logger.debug("Could not read %s", sf.relative_path)

    data = dep_map.to_dict()

    if json_mode:
        click.echo(json_mod.dumps(data, indent=2))
    else:
        for file_path, deps_list in data.items():
            console.print(f"\n[bold]{file_path}[/bold]")
            if deps_list:
                for dep in deps_list:
                    console.print(f"  → {dep.get('import_text', dep)}")
            else:
                console.print("  (no imports)")
