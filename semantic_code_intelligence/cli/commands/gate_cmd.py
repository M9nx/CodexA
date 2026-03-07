"""CLI command: gate — enforce quality gates for CI pipelines."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_success,
)

logger = get_logger("cli.gate")


@click.command("gate")
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
    "--pipe",
    is_flag=True,
    default=False,
    help="Plain text output for piping / CI.",
)
@click.option(
    "--min-maintainability",
    type=float,
    default=40.0,
    help="Minimum maintainability index (default: 40).",
)
@click.option(
    "--max-complexity",
    type=int,
    default=25,
    help="Maximum allowed complexity (default: 25).",
)
@click.option(
    "--max-issues",
    type=int,
    default=20,
    help="Maximum allowed total issues (default: 20).",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Exit with code 1 on gate failure (for CI).",
)
@click.pass_context
def gate_cmd(
    ctx: click.Context,
    path: str,
    json_mode: bool,
    pipe: bool,
    min_maintainability: float,
    max_complexity: int,
    max_issues: int,
    strict: bool,
) -> None:
    """Enforce quality gates — fail CI builds that violate quality policies.

    Runs full quality analysis plus maintainability metrics and checks
    results against configurable thresholds.

    Examples:

        codex gate

        codex gate --strict --json

        codex gate --min-maintainability 60 --max-complexity 15

        codex gate --pipe --strict
    """
    import sys

    from semantic_code_intelligence.ci.metrics import (
        QualityPolicy,
        compute_project_metrics,
        enforce_quality_gate,
    )
    from semantic_code_intelligence.ci.quality import analyze_project

    root = Path(path).resolve()

    report = analyze_project(root)
    pm = compute_project_metrics(root)

    policy = QualityPolicy(
        min_maintainability=min_maintainability,
        max_complexity=max_complexity,
        max_issues=max_issues,
    )

    result = enforce_quality_gate(pm, report, policy)

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
    elif pipe:
        status = "PASS" if result.passed else "FAIL"
        click.echo(f"{status}  MI={pm.maintainability_index:.1f}  issues={report.issue_count}")
        for v in result.violations:
            click.echo(f"  VIOLATION  {v.rule}: {v.message}")
    else:
        if result.passed:
            print_success(
                f"Quality gate passed — MI={pm.maintainability_index:.1f}, "
                f"{report.issue_count} issue(s)"
            )
        else:
            print_error(
                f"Quality gate FAILED — {len(result.violations)} violation(s)"
            )
            for v in result.violations:
                console.print(f"  [red]{v.rule}[/red]: {v.message}")

    if strict and not result.passed:
        sys.exit(1)
