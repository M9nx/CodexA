"""CLI command: grep — Raw filesystem search without requiring an index.

Unlike ``codexa search --mode regex``, this command searches raw files on disk
using ripgrep (if available) or a pure-Python fallback. Zero setup required.
Supports standard grep flags (-A/-B/-C context, -w word, -v invert, -c count).
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
@click.option(
    "-A",
    "after_context",
    default=0,
    type=int,
    help="Lines of context after each match.",
)
@click.option(
    "-B",
    "before_context",
    default=0,
    type=int,
    help="Lines of context before each match.",
)
@click.option(
    "-C",
    "context",
    default=0,
    type=int,
    help="Lines of context before and after each match (shorthand for -A N -B N).",
)
@click.option(
    "--word",
    "-w",
    is_flag=True,
    default=False,
    help="Match whole words only.",
)
@click.option(
    "--invert-match",
    "-v",
    is_flag=True,
    default=False,
    help="Show lines that do NOT match the pattern.",
)
@click.option(
    "--count",
    "-c",
    "count_only",
    is_flag=True,
    default=False,
    help="Only print a count of matching lines per file.",
)
@click.option(
    "--hidden",
    is_flag=True,
    default=False,
    help="Include hidden files and directories in search.",
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
    after_context: int,
    before_context: int,
    context: int,
    word: bool,
    invert_match: bool,
    count_only: bool,
    hidden: bool,
) -> None:
    """Search raw files using regex — no index required.

    Uses ripgrep for maximum speed when available, with a pure-Python
    fallback. Unlike 'codexa search --mode regex', this searches the
    actual filesystem, not the index.

    \b
    Examples:
        codexa grep "TODO|FIXME"
        codexa grep "def authenticate" -g "*.py"
        codexa grep "password" --case-sensitive
        codexa grep "import re" --json
        codexa grep "class.*Service" -l
        codexa grep "error" -A 3 -B 1
        codexa grep "def main" -C 2
        codexa grep "TODO" -c
        codexa grep "login" -w
        codexa grep "debug" -v
    """
    import json as json_mod

    root = Path(path).resolve()

    # -C sets both before and after context
    ctx_before = context if context > 0 else before_context
    ctx_after = context if context > 0 else after_context

    result = grep_search(
        pattern,
        root,
        case_insensitive=not case_sensitive,
        max_results=max_results,
        use_ripgrep=not no_ripgrep,
        file_glob=file_glob,
        context_before=ctx_before,
        context_after=ctx_after,
        word_match=word,
        invert_match=invert_match,
        include_hidden=hidden,
        count_only=count_only,
    )

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
        return

    if not result.matches:
        print_error(f"No matches for pattern: {pattern}")
        ctx.exit(1)
        return

    if count_only:
        # Aggregate counts per file
        from collections import Counter
        counts: Counter[str] = Counter()
        for m in result.matches:
            if not m.is_context:
                counts[m.file_path] += 1
        for fp, cnt in sorted(counts.items()):
            click.echo(f"{fp}:{cnt}")
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

    prev_file: str | None = None
    for m in result.matches:
        line = Text()
        line.append(m.file_path, style="green")
        line.append(":", style="dim")
        line.append(str(m.line_number), style="yellow")
        if m.is_context:
            line.append("-", style="dim")
        else:
            line.append(":", style="dim")
        line.append(m.line_content)
        console.print(line)

    console.print(
        f"\n[dim]{len([m for m in result.matches if not m.is_context])} matches "
        f"in {result.files_matched} files"
        f" (backend: {result.backend})[/dim]"
    )
