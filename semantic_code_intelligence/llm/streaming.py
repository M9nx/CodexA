"""Streaming LLM support — delivers tokens incrementally with plugin hooks.

Provides:
- ``stream_chat()`` wrapper that works with any LLMProvider
- ``StreamEvent`` lightweight token container
- Plugin dispatch through ``PluginHook.ON_STREAM`` for each token
- Accumulator helpers for building final ``LLMResponse`` from a stream
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generator

from semantic_code_intelligence.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.streaming")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class StreamEvent:
    """A single streaming event (token, status change, or error)."""

    kind: str  # "token" | "start" | "done" | "error"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "content": self.content, "metadata": self.metadata}

    def to_sse(self) -> str:
        """Format as a Server-Sent Event line."""
        import json

        return f"data: {json.dumps(self.to_dict())}\n\n"


# ---------------------------------------------------------------------------
# Streaming wrappers for each provider
# ---------------------------------------------------------------------------

def _stream_ollama(
    provider: Any,
    messages: list[LLMMessage],
    **kwargs: Any,
) -> Generator[StreamEvent, None, LLMResponse | None]:
    """Stream tokens from an Ollama provider."""
    import json as json_mod
    from urllib.request import Request, urlopen

    temperature = kwargs.get("temperature", provider._temperature)
    payload: dict[str, Any] = {
        "model": provider._model,
        "messages": [m.to_dict() for m in messages],
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": kwargs.get("max_tokens", provider._max_tokens),
        },
    }

    url = f"{provider._base_url}/api/chat"
    data = json_mod.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})

    yield StreamEvent(kind="start", metadata={"model": provider._model, "provider": "ollama"})

    accumulated = ""
    prompt_tokens = 0
    completion_tokens = 0

    try:
        with urlopen(req, timeout=120) as resp:  # noqa: S310 — localhost only
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    chunk = json_mod.loads(line)
                except json_mod.JSONDecodeError:
                    continue
                msg = chunk.get("message", {})
                token = msg.get("content", "")
                if token:
                    accumulated += token
                    yield StreamEvent(kind="token", content=token)

                if chunk.get("done"):
                    prompt_tokens = chunk.get("prompt_eval_count", 0)
                    completion_tokens = chunk.get("eval_count", 0)
    except Exception as exc:
        yield StreamEvent(kind="error", content=str(exc))
        return None

    yield StreamEvent(kind="done")
    return LLMResponse(
        content=accumulated,
        model=provider._model,
        provider="ollama",
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )


def _stream_openai(
    provider: Any,
    messages: list[LLMMessage],
    **kwargs: Any,
) -> Generator[StreamEvent, None, LLMResponse | None]:
    """Stream tokens from an OpenAI provider."""
    client = provider._get_client()
    temperature = kwargs.get("temperature", provider._temperature)
    max_tokens = kwargs.get("max_tokens", provider._max_tokens)

    api_messages = [m.to_dict() for m in messages]

    yield StreamEvent(kind="start", metadata={"model": provider._model, "provider": "openai"})

    accumulated = ""
    try:
        response = client.chat.completions.create(
            model=provider._model,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                accumulated += delta.content
                yield StreamEvent(kind="token", content=delta.content)
    except Exception as exc:
        yield StreamEvent(kind="error", content=str(exc))
        return None

    yield StreamEvent(kind="done")
    return LLMResponse(
        content=accumulated,
        model=provider._model,
        provider="openai",
        usage={"completion_tokens": len(accumulated) // 4},
    )


def _stream_mock(
    provider: Any,
    messages: list[LLMMessage],
    **kwargs: Any,
) -> Generator[StreamEvent, None, LLMResponse | None]:
    """Simulate streaming from a MockProvider by yielding word-by-word."""
    yield StreamEvent(kind="start", metadata={"model": provider._model, "provider": "mock"})

    content = provider._next_response()
    provider._call_history.append({
        "method": "stream_chat",
        "messages": [m.to_dict() for m in messages],
        "response": content,
    })

    words = content.split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else " " + word
        yield StreamEvent(kind="token", content=token)

    yield StreamEvent(kind="done")
    return LLMResponse(
        content=content,
        model=provider._model,
        provider="mock",
        usage={"completion_tokens": len(content) // 4},
    )


# ---------------------------------------------------------------------------
# Unified streaming API
# ---------------------------------------------------------------------------

def stream_chat(
    provider: LLMProvider,
    messages: list[LLMMessage],
    *,
    plugin_manager: Any | None = None,
    **kwargs: Any,
) -> Generator[StreamEvent, None, LLMResponse | None]:
    """Stream chat tokens from any supported LLM provider.

    Yields ``StreamEvent`` objects for each token.  If a *plugin_manager*
    is provided, dispatches ``PluginHook.ON_STREAM`` for each token event.

    Usage::

        gen = stream_chat(provider, messages)
        for event in gen:
            print(event.content, end="", flush=True)

    The generator's return value (accessible via StopIteration.value) is
    the accumulated ``LLMResponse``.
    """
    from semantic_code_intelligence.llm.ollama_provider import OllamaProvider
    from semantic_code_intelligence.llm.openai_provider import OpenAIProvider
    from semantic_code_intelligence.llm.mock_provider import MockProvider

    # Select the appropriate streaming implementation
    if isinstance(provider, OllamaProvider):
        inner = _stream_ollama(provider, messages, **kwargs)
    elif isinstance(provider, OpenAIProvider):
        inner = _stream_openai(provider, messages, **kwargs)
    elif isinstance(provider, MockProvider):
        inner = _stream_mock(provider, messages, **kwargs)
    else:
        # Fallback — non-streaming: call chat() and emit as single token
        resp = provider.chat(messages, **kwargs)
        yield StreamEvent(kind="start", metadata={"provider": provider.name})
        yield StreamEvent(kind="token", content=resp.content)
        yield StreamEvent(kind="done")
        return resp

    # Iterate inner generator, dispatching plugin hooks
    result: LLMResponse | None = None
    try:
        while True:
            event = next(inner)
            # Dispatch ON_STREAM plugin hook for token events
            if plugin_manager and event.kind == "token":
                try:
                    from semantic_code_intelligence.plugins import PluginHook

                    plugin_manager.dispatch(
                        PluginHook.ON_STREAM,
                        {"event": event.to_dict(), "accumulated": ""},
                    )
                except Exception:
                    logger.debug("Plugin streaming hook failed")
            yield event
    except StopIteration as stop:
        result = stop.value

    return result
