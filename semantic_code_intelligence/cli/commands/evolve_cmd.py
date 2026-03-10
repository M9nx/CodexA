"""CLI command: evolve — run the self-improving development loop."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
)

logger = get_logger("cli.evolve")


def _get_provider(config):
    """Build an LLM provider from the app configuration."""
    from semantic_code_intelligence.config.settings import LLMConfig

    llm: LLMConfig = config.llm
    if llm.provider == "openai":
        from semantic_code_intelligence.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider(
            api_key=llm.api_key,
            model=llm.model,
            base_url=llm.base_url or None,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
        )
    elif llm.provider == "ollama":
        from semantic_code_intelligence.llm.ollama_provider import OllamaProvider

        provider = OllamaProvider(
            model=llm.model,
            base_url=llm.base_url or "http://localhost:11434",
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
        )
    else:
        from semantic_code_intelligence.llm.mock_provider import MockProvider

        provider = MockProvider()

    return provider


@click.command("evolve")
@click.option(
    "--iterations",
    "-n",
    default=3,
    type=click.IntRange(min=1, max=20),
    help="Maximum number of improvement iterations.",
)
@click.option(
    "--budget",
    "-b",
    default=20000,
    type=click.IntRange(min=1000),
    help="Maximum total tokens to spend across all LLM calls.",
)
@click.option(
    "--timeout",
    "-t",
    default=600,
    type=click.IntRange(min=30),
    help="Maximum wall-clock seconds for the entire run.",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def evolve_cmd(
    ctx: click.Context,
    iterations: int,
    budget: int,
    timeout: int,
    path: str,
) -> None:
    """Run the self-improving development loop.

    Automatically selects small improvement tasks (fix tests, add type
    hints, improve error handling, reduce duplication) and applies them
    using the configured LLM.  Every change is tested; failures are
    reverted and successes are committed.

    Examples:

        codexa evolve

        codexa evolve --iterations 5 --budget 50000

        codexa evolve --path /my/project --timeout 300
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codexa init' first.")
        ctx.exit(1)
        return

    config = load_config(root)
    provider = _get_provider(config)

    from semantic_code_intelligence.evolution.budget_guard import BudgetGuard
    from semantic_code_intelligence.evolution.engine import EvolutionEngine

    guard = BudgetGuard(
        max_tokens=budget,
        max_iterations=iterations,
        max_seconds=float(timeout),
    )

    console.print(
        f"\n[bold cyan]Evolution loop[/bold cyan]  "
        f"iterations={iterations}  budget={budget} tokens  "
        f"timeout={timeout}s\n"
    )

    engine = EvolutionEngine(
        project_root=root,
        provider=provider,
        budget=guard,
    )

    result = engine.run()

    # — Summary ————————————————————————————————
    console.print("\n[bold green]Evolution complete[/bold green]\n")
    console.print(f"  Iterations : {result.iterations_completed}")
    console.print(f"  Commits    : {len(result.commits)}")
    console.print(f"  Reverts    : {result.reverts}")
    console.print(f"  Stop reason: {result.stop_reason}")

    bs = result.budget_summary
    console.print(
        f"  Tokens     : {bs.get('tokens_used', 0)}/{bs.get('tokens_max', 0)}"
    )
    console.print(
        f"  Time       : {bs.get('elapsed_seconds', 0)}s / {bs.get('max_seconds', 0)}s"
    )

    if result.commits:
        console.print("\n[bold]Commits:[/bold]")
        for sha in result.commits:
            console.print(f"  {sha}")

    if result.history:
        console.print("\n[bold]Iteration details:[/bold]")
        for rec in result.history:
            status = "[green]committed[/green]" if rec.committed else (
                "[red]reverted[/red]" if rec.reverted else "[yellow]skipped[/yellow]"
            )
            console.print(
                f"  {rec.iteration}. {rec.task_category} — {status}"
                f"  ({rec.patch_lines_changed} lines)"
            )
            if rec.error:
                console.print(f"     [dim]{rec.error}[/dim]")

    print_info("History saved to .codexa/evolution_history.json")
