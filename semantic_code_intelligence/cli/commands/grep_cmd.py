"""CLI command: grep — Raw filesystem search without requiring an index.

Unlike ``codex search --mode regex``, this command searches raw files on disk
using ripgrep (if available) or a pure-Python fallback. Zero setup required.
"""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.search.grep import grep_search
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    console,
)

logger = get_logger("cli.grep")


@click.command("grep")
@click.argument("pattern", type=str)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Directory root to search.",
)
@click.option(
    "--case-sensitive",
    "-s",
    is_flag=True,
    default=False,
    help="Case-sensitive matching.",
)
@click.option(
    "--max-results",
    "-n",
    default=100,
    type=int,
    help="Maximum number of matches to return.",
)
@click.option(
    "--glob",
    "-g",
    "file_glob",
    default=None,
    type=str,
    help="Filter files by glob pattern (e.g. '*.py').",
)
@click.option(
    "--no-ripgrep",
    is_flag=True,
    default=False,
    help="Force pure-Python search (skip ripgrep even if available).",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output results as JSON.",
)
@click.option(
    "--files-only",
    "-l",
    is_flag=True,
    default=False,
    help="Print only file paths with matches (like grep -l).",
)
@click.pass_context
def grep_cmd(
    ctx: click.Context,
    pattern: str,
    path: str,
    case_sensitive: bool,
    max_results: int,
    file_glob: str | None,
    no_ripgrep: bool,
    json_mode: bool,
    files_only: bool,
) -> None:
    """Search raw files using regex — no index required.

    Uses ripgrep for maximum speed when available, with a pure-Python
    fallback. Unlike 'codex search --mode regex', this searches the
    actual filesystem, not the index.

    \b
    Examples:
        codex grep "TODO|FIXME"
        codex grep "def authenticate" -g "*.py"
        codex grep "password" --case-sensitive
        codex grep "import re" --json
        codex grep "class.*Service" -l
    """
    import json as json_mod

    root = Path(path).resolve()

    result = grep_search(
        pattern,
        root,
        case_insensitive=not case_sensitive,
        max_results=max_results,
        use_ripgrep=not no_ripgrep,
        file_glob=file_glob,
    )

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
        return

    if not result.matches:
        print_error(f"No matches for pattern: {pattern}")
        ctx.exit(1)
        return

    if files_only:
        seen: set[str] = set()
        for m in result.matches:
            if m.file_path not in seen:
                seen.add(m.file_path)
                click.echo(m.file_path)
        return

    # Rich output
    from rich.text import Text

    for m in result.matches:
        line = Text()
        line.append(m.file_path, style="green")
        line.append(":", style="dim")
        line.append(str(m.line_number), style="yellow")
        line.append(":", style="dim")
        line.append(m.line_content)
        console.print(line)

    console.print(
        f"\n[dim]{len(result.matches)} matches in {result.files_matched} files"
        f" (backend: {result.backend})[/dim]"
    )
