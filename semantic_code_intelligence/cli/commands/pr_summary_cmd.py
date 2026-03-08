"""CLI command: pr-summary — generate PR intelligence report."""

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

logger = get_logger("cli.pr_summary")


def _find_changed_files(root: Path) -> list[str]:
    """Discover changed files using simple heuristics.

    Checks for:
    1. Git diff (if inside a git repo).
    2. Falls back to all supported source files.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(root),
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            files = []
            for line in result.stdout.strip().splitlines():
                fpath = root / line.strip()
                if fpath.exists():
                    files.append(str(fpath))
            if files:
                return files
    except Exception:
        logger.debug("git diff-tree failed; falling back to full file scan")

    # Fallback: list all supported source files
    from semantic_code_intelligence.parsing.parser import EXTENSION_TO_LANGUAGE
    files = []
    for f in root.rglob("*"):
        if f.is_file() and f.suffix in EXTENSION_TO_LANGUAGE:
            parts = f.relative_to(root).parts
            if any(p.startswith(".") or p in ("__pycache__", "node_modules") for p in parts):
                continue
            files.append(str(f))
    return files


@click.command("pr-summary")
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
@click.option(
    "--files",
    "-f",
    multiple=True,
    help="Specific files to analyze (can be repeated).",
)
@click.option(
    "--pipe",
    is_flag=True,
    default=False,
    help="Plain text output for piping / CI.",
)
@click.pass_context
def pr_summary_cmd(
    ctx: click.Context,
    path: str,
    json_mode: bool,
    files: tuple[str, ...],
    pipe: bool,
) -> None:
    """Generate a Pull Request intelligence report.

    Analyzes changed files to produce a change summary, semantic impact
    analysis, suggested reviewer domains, and risk scoring.

    All output is advisory — CodexA never modifies repository code.

    Examples:

        codex pr-summary

        codex pr-summary --json

        codex pr-summary -f src/main.py -f src/utils.py
    """
    from semantic_code_intelligence.ci.pr import generate_pr_report

    root = Path(path).resolve()
    changed = list(files) if files else _find_changed_files(root)

    if not changed:
        if json_mode:
            click.echo(json_mod.dumps({"error": "No changed files found"}, indent=2))
        else:
            print_info("No changed files found")
        return

    report = generate_pr_report(changed, root)

    if json_mode:
        click.echo(json_mod.dumps(report.to_dict(), indent=2))
        return

    cs = report.change_summary
    if pipe:
        click.echo(f"Changed: {cs.files_changed} files  Languages: {', '.join(cs.languages) or 'none'}")
        click.echo(f"Symbols: +{cs.total_symbols_added} -{cs.total_symbols_removed} ~{cs.total_symbols_modified}")
        if report.risk:
            click.echo(f"Risk: {report.risk.level} ({report.risk.score}/100)")
            for f in report.risk.factors:
                click.echo(f"  - {f}")
        return

    # Rich output
    console.print(f"\n[bold cyan]PR Summary[/bold cyan]\n")
    console.print(f"  Files changed: {cs.files_changed}")
    console.print(f"  Languages: {', '.join(cs.languages) or 'none'}")
    console.print(f"  Symbols: [green]+{cs.total_symbols_added}[/green] [red]-{cs.total_symbols_removed}[/red] [yellow]~{cs.total_symbols_modified}[/yellow]\n")

    if cs.file_details:
        console.print("[bold]File Details:[/bold]")
        for fd in cs.file_details:
            lang_tag = f" [{fd.language}]" if fd.language else ""
            console.print(f"  {fd.path}{lang_tag}")
            if fd.symbols_added:
                console.print(f"    [green]+ {', '.join(fd.symbols_added)}[/green]")
            if fd.symbols_removed:
                console.print(f"    [red]- {', '.join(fd.symbols_removed)}[/red]")
            if fd.symbols_modified:
                console.print(f"    [yellow]~ {', '.join(fd.symbols_modified)}[/yellow]")
        console.print()

    if report.impact:
        imp = report.impact
        if imp.affected_symbols:
            console.print("[bold]Impact — Affected Symbols:[/bold]")
            for s in imp.affected_symbols[:20]:
                console.print(f"  {s}")
            console.print()

    if report.reviewers:
        console.print("[bold]Suggested Reviewer Domains:[/bold]")
        for r in report.reviewers[:10]:
            console.print(f"  {r['domain']} ({r['file_count']} file(s))")
        console.print()

    if report.risk:
        color = {"low": "green", "medium": "yellow", "high": "red", "critical": "bold red"}
        c = color.get(report.risk.level, "white")
        console.print(f"[{c}]Risk: {report.risk.level.upper()} ({report.risk.score}/100)[/{c}]")
        for f in report.risk.factors:
            console.print(f"  - {f}")
        console.print()
