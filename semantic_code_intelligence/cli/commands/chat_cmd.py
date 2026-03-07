"""CLI command: chat — multi-turn conversation with session persistence."""

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

logger = get_logger("cli.chat")


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
        pass

    # Call LLM
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
