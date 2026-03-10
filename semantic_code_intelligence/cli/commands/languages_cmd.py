"""CLI command: languages — List supported languages and their parsing status."""

from __future__ import annotations

import click

from semantic_code_intelligence.parsing.parser import (
    _LANGUAGE_MODULES,
    EXTENSION_TO_LANGUAGE,
    FUNCTION_NODE_TYPES,
    CLASS_NODE_TYPES,
    IMPORT_NODE_TYPES,
    get_language,
)
from semantic_code_intelligence.utils.logging import get_logger, console

logger = get_logger("cli.languages")


@click.command("languages")
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output as JSON.",
)
@click.option(
    "--check",
    is_flag=True,
    default=False,
    help="Verify each grammar can be loaded (slower).",
)
def languages_cmd(json_mode: bool, check: bool) -> None:
    """List all supported programming languages and their tree-sitter grammar status.

    \b
    Examples:
        codexa languages
        codexa languages --check
        codexa languages --json
    """
    import json as json_mod

    # Build extension map (language -> list of extensions)
    ext_map: dict[str, list[str]] = {}
    for ext, lang in EXTENSION_TO_LANGUAGE.items():
        ext_map.setdefault(lang, []).append(ext)

    rows: list[dict] = []
    for lang_name, module_name in sorted(_LANGUAGE_MODULES.items()):
        extensions = ext_map.get(lang_name, [])
        has_functions = lang_name in FUNCTION_NODE_TYPES
        has_classes = lang_name in CLASS_NODE_TYPES
        has_imports = lang_name in IMPORT_NODE_TYPES

        status = "available"
        if check:
            loaded = get_language(lang_name)
            status = "loaded" if loaded else "missing"

        rows.append({
            "language": lang_name,
            "module": module_name,
            "extensions": sorted(extensions),
            "functions": has_functions,
            "classes": has_classes,
            "imports": has_imports,
            "status": status,
        })

    if json_mode:
        click.echo(json_mod.dumps(rows, indent=2))
        return

    from rich.table import Table

    table = Table(title="Supported Languages", show_lines=False)
    table.add_column("Language", style="cyan bold")
    table.add_column("Extensions", style="green")
    table.add_column("Functions", justify="center")
    table.add_column("Classes", justify="center")
    table.add_column("Imports", justify="center")
    if check:
        table.add_column("Status", justify="center")

    for row in rows:
        exts = ", ".join(row["extensions"])
        fn_icon = "[green]✓[/green]" if row["functions"] else "[red]✗[/red]"
        cls_icon = "[green]✓[/green]" if row["classes"] else "[red]✗[/red]"
        imp_icon = "[green]✓[/green]" if row["imports"] else "[red]✗[/red]"
        cols = [row["language"], exts, fn_icon, cls_icon, imp_icon]
        if check:
            st = row["status"]
            st_icon = "[green]loaded[/green]" if st == "loaded" else "[red]missing[/red]"
            cols.append(st_icon)
        table.add_row(*cols)

    console.print(table)
    console.print(f"\n[dim]{len(rows)} languages supported[/dim]")
