"""OpenAI LLM provider — integration with the OpenAI Chat Completions API."""

from __future__ import annotations

from typing import Any

from semantic_code_intelligence.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.openai")


class OpenAIProvider(LLMProvider):
    """LLM provider for the OpenAI API (GPT-3.5, GPT-4, etc.).

    Requires the ``openai`` package and a valid API key.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client: Any = None

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self) -> Any:
        """Lazily initialise the OpenAI client."""
        if self._client is None:
            try:
                import openai
            except ImportError as exc:
                raise ImportError(
                    "The 'openai' package is required for OpenAIProvider. "
                    "Install it with: pip install openai"
                ) from exc

            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        messages = [LLMMessage(role=MessageRole.USER, content=prompt)]
        return self.chat(messages, **kwargs)

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        client = self._get_client()
        temperature = kwargs.get("temperature", self._temperature)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)

        api_messages = [m.to_dict() for m in messages]

        logger.debug(
            "OpenAI chat request: model=%s, messages=%d", self._model, len(api_messages)
        )

        response = client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.name,
            usage=usage,
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
        )

    def is_available(self) -> bool:
        return bool(self._api_key)
