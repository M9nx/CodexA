"""CLI command: refactor — AI-powered refactoring suggestions for a file."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
)

logger = get_logger("cli.refactor")


@click.command("refactor")
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "--instruction",
    "-i",
    default="Improve code quality, readability, and performance.",
    help="Refactoring instruction for the AI.",
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
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def refactor_cmd(
    ctx: click.Context,
    file: str,
    instruction: str,
    json_mode: bool,
    path: str,
) -> None:
    """Suggest refactored code for a source file.

    Uses structural analysis + LLM to propose improved code with explanations.

    Examples:

        codex refactor src/main.py

        codex refactor src/utils.py -i "Extract duplicated logic into helpers"
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codex init' first.")
        ctx.exit(1)
        return

    config = load_config(root)

    from semantic_code_intelligence.cli.commands.ask_cmd import _get_provider
    from semantic_code_intelligence.llm.reasoning import ReasoningEngine
    from semantic_code_intelligence.llm.safety import SafetyValidator

    provider = _get_provider(config)
    engine = ReasoningEngine(provider, root)
    result = engine.refactor(file, instruction)

    # Safety check on refactored code
    if result.refactored_code:
        validator = SafetyValidator()
        report = validator.validate(result.refactored_code)
        if not report.safe:
            console.print("[bold red]⚠ Safety issues detected in refactored code:[/bold red]")
            for issue in report.issues:
                console.print(f"  L{issue.line_number}: {issue.description}")
            console.print()

    if json_mode:
        console.print(json_mod.dumps(result.to_dict(), indent=2))
    else:
        console.print(f"\n[bold cyan]Refactor:[/bold cyan] {result.file_path}\n")
        console.print(f"[bold green]Explanation:[/bold green]\n{result.explanation}\n")
        if result.refactored_code:
            console.print("[bold]Refactored code:[/bold]")
            console.print(result.refactored_code)
        else:
            print_info("No refactored code produced (check LLM configuration).")
