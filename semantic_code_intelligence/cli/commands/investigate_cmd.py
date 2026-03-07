"""CLI command: investigate — autonomous multi-step code investigation."""

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

logger = get_logger("cli.investigate")


def _get_provider(config):
    """Build an LLM provider from the app configuration."""
    from semantic_code_intelligence.config.settings import LLMConfig

    llm: LLMConfig = config.llm
    if llm.provider == "openai":
        from semantic_code_intelligence.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=llm.api_key,
            model=llm.model,
            base_url=llm.base_url or None,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
        )
    elif llm.provider == "ollama":
        from semantic_code_intelligence.llm.ollama_provider import OllamaProvider

        return OllamaProvider(
            model=llm.model,
            base_url=llm.base_url or "http://localhost:11434",
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
        )
    else:
        from semantic_code_intelligence.llm.mock_provider import MockProvider

        return MockProvider()


@click.command("investigate")
@click.argument("question", type=str)
@click.option(
    "--max-steps", "-n",
    default=6,
    type=int,
    help="Maximum investigation steps before forcing a conclusion.",
)
@click.option(
    "--json-output", "--json", "json_mode",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
@click.option(
    "--path", "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.option("--pipe", is_flag=True, default=False, hidden=True)
@click.pass_context
def investigate_cmd(
    ctx: click.Context,
    question: str,
    max_steps: int,
    json_mode: bool,
    path: str,
    pipe: bool,
) -> None:
    """Run an autonomous multi-step investigation to answer a question.

    CodexA iteratively searches, analyses symbols, and examines dependencies
    until it can confidently answer your question.  Each step is visible
    so you can follow the reasoning chain.
    """
    from semantic_code_intelligence.config.settings import load_config
    from semantic_code_intelligence.llm.investigation import InvestigationChain

    root = Path(path).resolve()
    pipe = pipe or ctx.obj.get("pipe", False)

    config = load_config(root)
    provider = _get_provider(config)

    chain = InvestigationChain(provider, root, max_steps=max_steps)
    result = chain.investigate(question)

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
    elif pipe:
        for step in result.steps:
            click.echo(f"[{step['step']}] {step['action']}: {step.get('action_input', '')}")
        click.echo(f"\nConclusion: {result.conclusion}")
    else:
        from rich.panel import Panel
        from rich.markdown import Markdown

        for step in result.steps:
            action = step["action"]
            thought = step.get("thought", "")
            output = step.get("output", "")[:300]
            console.print(
                f"  [bold cyan]Step {step['step']}[/] [{action}] "
                f"[dim]{thought}[/]"
            )
            if output and action != "conclude":
                console.print(f"    [dim]{output}[/dim]")

        console.print()
        console.print(Panel(
            Markdown(result.conclusion),
            title=f"Investigation ({result.total_steps} steps)",
            border_style="green",
        ))
