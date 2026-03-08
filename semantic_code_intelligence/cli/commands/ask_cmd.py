"""CLI command: ask — ask a natural-language question about the codebase."""

from __future__ import annotations

import json as json_mod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
)

if TYPE_CHECKING:
    from semantic_code_intelligence.llm.provider import LLMProvider

logger = get_logger("cli.ask")


def _wrap_provider(provider: LLMProvider, llm: Any, config: Any) -> LLMProvider:
    """Wrap a provider with caching and rate limiting based on config."""
    from semantic_code_intelligence.llm.cache import LLMCache
    from semantic_code_intelligence.llm.cached_provider import CachedProvider
    from semantic_code_intelligence.llm.rate_limiter import RateLimiter

    cache = None
    if getattr(llm, "cache_enabled", False):
        cache_dir = str(config.config_dir(config.project_root)) if hasattr(config, "config_dir") else None
        cache = LLMCache(
            cache_dir=cache_dir,
            ttl_hours=getattr(llm, "cache_ttl_hours", 24),
            max_entries=getattr(llm, "cache_max_entries", 1000),
        )

    rate_limiter = None
    rpm = getattr(llm, "rate_limit_rpm", 0)
    tpm = getattr(llm, "rate_limit_tpm", 0)
    if rpm > 0 or tpm > 0:
        rate_limiter = RateLimiter(rpm=rpm, tpm=tpm)

    if cache is not None or rate_limiter is not None:
        return CachedProvider(provider, cache=cache, rate_limiter=rate_limiter)
    return provider


def _get_provider(config: Any) -> LLMProvider:
    """Build an LLM provider from the app configuration."""
    from semantic_code_intelligence.config.settings import LLMConfig

    llm: LLMConfig = config.llm
    if llm.provider == "openai":
        from semantic_code_intelligence.llm.openai_provider import OpenAIProvider

        provider: LLMProvider = OpenAIProvider(
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

    return _wrap_provider(provider, llm, config)


@click.command("ask")
@click.argument("question", type=str)
@click.option(
    "--top-k",
    "-k",
    default=5,
    type=int,
    help="Number of context snippets to retrieve.",
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
def ask_cmd(
    ctx: click.Context,
    question: str,
    top_k: int,
    json_mode: bool,
    path: str,
) -> None:
    """Ask a natural-language question about the codebase.

    Uses semantic search + LLM to answer questions about your code.

    Examples:

        codex ask "How does authentication work?"

        codex ask "What does the search_codebase function do?" --json
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codex init' first.")
        ctx.exit(1)
        return

    config = load_config(root)
    provider = _get_provider(config)

    from semantic_code_intelligence.llm.reasoning import ReasoningEngine

    engine = ReasoningEngine(provider, root)
    result = engine.ask(question, top_k=top_k)

    if json_mode:
        click.echo(json_mod.dumps(result.to_dict(), indent=2))
    else:
        console.print(f"\n[bold cyan]Question:[/bold cyan] {result.question}\n")
        console.print(f"[bold green]Answer:[/bold green]\n{result.answer}\n")
        if result.context_snippets:
            console.print(f"[dim]({len(result.context_snippets)} context snippets used)[/dim]")
