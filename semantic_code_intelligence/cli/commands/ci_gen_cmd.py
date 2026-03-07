"""CLI command: ci-gen — generate CI workflow templates."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_info,
    print_success,
)

logger = get_logger("cli.ci_gen")


@click.command("ci-gen")
@click.argument(
    "template",
    type=click.Choice(["analysis", "safety", "precommit"], case_sensitive=False),
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Write output to a file instead of stdout.",
)
@click.option(
    "--python-version",
    default="3.12",
    help="Python version for workflow (default: 3.12).",
)
@click.pass_context
def ci_gen_cmd(
    ctx: click.Context,
    template: str,
    output: str | None,
    python_version: str,
) -> None:
    """Generate CI/CD workflow templates for CodexA integration.

    Available templates:

    - analysis  — Full analysis workflow (quality + PR summary)

    - safety    — Lightweight safety-only workflow

    - precommit — Pre-commit hook configuration

    Examples:

        codex ci-gen analysis

        codex ci-gen safety -o .github/workflows/codex-safety.yml

        codex ci-gen precommit -o .pre-commit-config.yaml
    """
    from semantic_code_intelligence.ci.templates import get_template

    kwargs = {}
    if template != "precommit":
        kwargs["python_version"] = python_version

    content = get_template(template, **kwargs)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print_success(f"Written to {output}")
    else:
        click.echo(content)
