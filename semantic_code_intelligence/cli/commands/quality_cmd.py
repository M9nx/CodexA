"""CLI command: quality — run code quality analysis."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
    print_success,
)

logger = get_logger("cli.quality")


@click.command("quality")
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
    "--complexity-threshold",
    type=int,
    default=10,
    help="Minimum cyclomatic complexity to report (default: 10).",
)
@click.option(
    "--safety-only",
    is_flag=True,
    default=False,
    help="Run only the safety validator (fast mode).",
)
@click.option(
    "--pipe",
    is_flag=True,
    default=False,
    help="Plain text output for piping / CI.",
)
@click.pass_context
def quality_cmd(
    ctx: click.Context,
    path: str,
    json_mode: bool,
    complexity_threshold: int,
    safety_only: bool,
    pipe: bool,
) -> None:
    """Analyze code quality — complexity, dead code, duplicates, security.

    Scans the project for quality issues and produces a human-readable or
    JSON report.  Useful for CI pipelines and local development.

    Examples:

        codex quality

        codex quality --json

        codex quality --safety-only --pipe

        codex quality --complexity-threshold 15
    """
    from semantic_code_intelligence.ci.quality import analyze_project, QualityReport
    from semantic_code_intelligence.llm.safety import SafetyValidator

    root = Path(path).resolve()

    if safety_only:
        # Fast path: only safety scan
        from semantic_code_intelligence.parsing.parser import EXTENSION_TO_LANGUAGE
        code = ""
        count = 0
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in EXTENSION_TO_LANGUAGE:
                parts = f.relative_to(root).parts
                if any(p.startswith(".") or p in ("__pycache__", "node_modules") for p in parts):
                    continue
                try:
                    code += f.read_text(encoding="utf-8", errors="replace") + "\n"
                    count += 1
                except Exception:
                    pass
        validator = SafetyValidator()
        safety = validator.validate(code)

        if json_mode:
            click.echo(json_mod.dumps({
                "files_analyzed": count,
                "safety": safety.to_dict(),
            }, indent=2))
        elif pipe:
            if safety.safe:
                click.echo(f"PASS  {count} files scanned, no safety issues")
            else:
                click.echo(f"FAIL  {count} files scanned, {len(safety.issues)} safety issue(s)")
                for issue in safety.issues:
                    click.echo(f"  L{issue.line_number}: {issue.description}")
        else:
            if safety.safe:
                print_success(f"Safety check passed — {count} files scanned")
            else:
                print_error(f"{len(safety.issues)} safety issue(s) found in {count} files")
                for issue in safety.issues:
                    console.print(f"  [yellow]L{issue.line_number}[/yellow]: {issue.description}")
        return

    # Full quality analysis
    report = analyze_project(
        root,
        complexity_threshold=complexity_threshold,
    )

    if json_mode:
        click.echo(json_mod.dumps(report.to_dict(), indent=2))
        return

    if pipe:
        click.echo(f"Files: {report.files_analyzed}  Symbols: {report.symbol_count}  Issues: {report.issue_count}")
        for c in report.complexity_issues:
            click.echo(f"  COMPLEXITY  {c.symbol_name} ({c.file_path}:{c.start_line}) score={c.complexity} [{c.rating}]")
        for d in report.dead_code:
            click.echo(f"  DEAD_CODE   {d.symbol_name} ({d.file_path}:{d.start_line}) kind={d.kind}")
        for dup in report.duplicates:
            click.echo(f"  DUPLICATE   {dup.symbol_a} ↔ {dup.symbol_b} sim={dup.similarity:.2f}")
        if report.safety and not report.safety.safe:
            for i in report.safety.issues:
                click.echo(f"  SAFETY      L{i.line_number}: {i.description}")
        return

    # Rich output
    console.print(f"\n[bold cyan]Quality Report[/bold cyan] — {root}\n")
    console.print(f"  Files analyzed: {report.files_analyzed}")
    console.print(f"  Symbols: {report.symbol_count}")
    console.print(f"  Issues: {report.issue_count}\n")

    if report.complexity_issues:
        console.print("[bold yellow]High Complexity Functions:[/bold yellow]")
        for c in report.complexity_issues:
            console.print(f"  {c.symbol_name} ({c.file_path}:{c.start_line}) — score {c.complexity} [{c.rating}]")
        console.print()

    if report.dead_code:
        console.print("[bold yellow]Potentially Dead Code:[/bold yellow]")
        for d in report.dead_code:
            console.print(f"  {d.symbol_name} ({d.file_path}:{d.start_line}) — {d.kind}")
        console.print()

    if report.duplicates:
        console.print("[bold yellow]Duplicate Logic:[/bold yellow]")
        for dup in report.duplicates:
            console.print(f"  {dup.symbol_a} ↔ {dup.symbol_b} — {dup.similarity:.0%} similar")
        console.print()

    if report.safety and not report.safety.safe:
        console.print("[bold red]Safety Issues:[/bold red]")
        for i in report.safety.issues:
            console.print(f"  L{i.line_number}: {i.description}")
        console.print()

    if report.issue_count == 0:
        print_success("No quality issues found")
