"""Mock LLM provider — deterministic responses for testing."""

from __future__ import annotations

from typing import Any

from semantic_code_intelligence.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
)


class MockProvider(LLMProvider):
    """A mock LLM provider that returns configurable responses.

    Useful for unit tests and offline development without a live LLM.
    """

    def __init__(
        self,
        default_response: str = "This is a mock LLM response.",
        model: str = "mock-model",
    ) -> None:
        self._default_response = default_response
        self._model = model
        self._call_history: list[dict[str, Any]] = []
        self._response_queue: list[str] = []

    @property
    def name(self) -> str:
        return "mock"

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Return a log of all calls made to this mock."""
        return list(self._call_history)

    def enqueue_response(self, response: str) -> None:
        """Enqueue a custom response.  FIFO — next call pops from front."""
        self._response_queue.append(response)

    def _next_response(self) -> str:
        if self._response_queue:
            return self._response_queue.pop(0)
        return self._default_response

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        content = self._next_response()
        self._call_history.append({
            "method": "complete",
            "prompt": prompt,
            "kwargs": kwargs,
            "response": content,
        })
        return LLMResponse(
            content=content,
            model=self._model,
            provider=self.name,
            usage={"prompt_tokens": len(prompt) // 4, "completion_tokens": len(content) // 4, "total_tokens": (len(prompt) + len(content)) // 4},
        )

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        content = self._next_response()
        self._call_history.append({
            "method": "chat",
            "messages": [m.to_dict() for m in messages],
            "kwargs": kwargs,
            "response": content,
        })
        total_chars = sum(len(m.content) for m in messages) + len(content)
        return LLMResponse(
            content=content,
            model=self._model,
            provider=self.name,
            usage={"prompt_tokens": total_chars // 4, "completion_tokens": len(content) // 4, "total_tokens": total_chars // 4},
        )
