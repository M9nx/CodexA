"""CLI command: chat — multi-turn conversation with session persistence."""

from __future__ import annotations

import json as json_mod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
)

if TYPE_CHECKING:
    from semantic_code_intelligence.llm.provider import LLMProvider

logger = get_logger("cli.chat")


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


@click.command("chat")
@click.argument("message", type=str)
@click.option(
    "--session", "-s",
    default=None,
    type=str,
    help="Session ID to resume. Creates a new session if not given.",
)
@click.option(
    "--list-sessions", "list_sessions",
    is_flag=True,
    default=False,
    help="List all stored chat sessions and exit.",
)
@click.option(
    "--json-output", "--json", "json_mode",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
@click.option(
    "--max-turns", "-t",
    default=20,
    type=int,
    help="Maximum conversation turns to send to LLM.",
)
@click.option(
    "--path", "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.option(
    "--stream",
    is_flag=True,
    default=False,
    help="Stream tokens incrementally as they arrive.",
)
@click.option("--pipe", is_flag=True, default=False, hidden=True)
@click.pass_context
def chat_cmd(
    ctx: click.Context,
    message: str,
    session: str | None,
    list_sessions: bool,
    json_mode: bool,
    max_turns: int,
    path: str,
    stream: bool,
    pipe: bool,
) -> None:
    """Continue or start a multi-turn conversation about the codebase.

    Each conversation is persisted to disk so you can resume later with
    --session <id>.  Use --list-sessions to see saved conversations.
    """
    from semantic_code_intelligence.config.settings import load_config
    from semantic_code_intelligence.llm.conversation import SessionStore
    from semantic_code_intelligence.llm.reasoning import ReasoningEngine

    root = Path(path).resolve()
    pipe = pipe or ctx.obj.get("pipe", False)

    store = SessionStore(root)

    # --- list sessions mode ---
    if list_sessions:
        sessions = store.list_sessions()
        if json_mode:
            click.echo(json_mod.dumps(sessions, indent=2))
        elif pipe:
            for s in sessions:
                click.echo(f"{s['session_id']}  turns={s['turns']}  {s['title']}")
        else:
            if not sessions:
                print_info("No stored sessions.")
            else:
                from rich.table import Table

                table = Table(title="Chat Sessions")
                table.add_column("ID")
                table.add_column("Title")
                table.add_column("Turns")
                for s in sessions:
                    table.add_row(s["session_id"], s["title"], str(s["turns"]))
                console.print(table)
        return

    # --- conversation mode ---
    config = load_config(root)
    provider = _get_provider(config)

    conv = store.get_or_create(session)

    # If this is a fresh session, set up the system prompt
    if not conv.messages:
        conv.add_system(
            "You are CodexA, an AI coding assistant. Answer questions about the "
            "user's codebase. Be concise, accurate, and cite file paths when relevant."
        )
        conv.title = message[:60]

    # Add user message
    conv.add_user(message)

    # Get context-enriched messages
    messages = conv.get_messages_for_llm(max_turns=max_turns)

    # Also inject search context into the user's message
    engine = ReasoningEngine(provider, root)
    try:
        snippets = engine._search_context(message, top_k=3)
        if snippets:
            ctx_text = "\n".join(
                f"[{s.get('file_path', '?')}] {s.get('content', '')[:200]}"
                for s in snippets[:3]
            )
            # Inject context before the last user message
            messages[-1] = type(messages[-1])(
                role=messages[-1].role,
                content=f"Relevant code:\n{ctx_text}\n\nUser: {message}",
            )
    except Exception:
        logger.debug("Context injection failed; continuing without code context")

    # Call LLM (streaming or batch)
    if stream and not json_mode:
        from semantic_code_intelligence.llm.streaming import stream_chat

        gen = stream_chat(provider, messages)
        accumulated = ""
        if not pipe:
            console.print(f"[bold cyan]CodexA [{conv.session_id}][/]", end="")
            click.echo("")
        for event in gen:
            if event.kind == "token":
                accumulated += event.content
                click.echo(event.content, nl=False)
        click.echo("")  # trailing newline
        conv.add_assistant(accumulated)
        store.save(conv)
        if not pipe:
            print_info(f"Session: {conv.session_id} (use --session {conv.session_id} to continue)")
        return

    resp = provider.chat(messages)
    conv.add_assistant(resp.content)

    # Persist session
    store.save(conv)

    # Output
    if json_mode:
        click.echo(json_mod.dumps({
            "session_id": conv.session_id,
            "answer": resp.content,
            "turns": conv.turn_count,
            "usage": resp.usage,
        }, indent=2))
    elif pipe:
        click.echo(resp.content)
    else:
        from rich.markdown import Markdown
        from rich.panel import Panel

        console.print(Panel(
            Markdown(resp.content),
            title=f"CodexA [{conv.session_id}]",
            subtitle=f"Turn {conv.turn_count // 2}",
        ))
        print_info(f"Session: {conv.session_id} (use --session {conv.session_id} to continue)")
