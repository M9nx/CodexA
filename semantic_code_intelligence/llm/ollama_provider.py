"""Ollama LLM provider — integration with the Ollama local model server."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from semantic_code_intelligence.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.ollama")


class OllamaProvider(LLMProvider):
    """LLM provider for the Ollama local model server.

    Communicates via HTTP with the Ollama REST API.
    No external packages required beyond the standard library.
    """

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return "ollama"

    def _api_call(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to the Ollama API."""
        url = f"{self._base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"})

        with urlopen(req, timeout=120) as resp:  # noqa: S310 — localhost only
            return json.loads(resp.read().decode("utf-8"))

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        temperature = kwargs.get("temperature", self._temperature)
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": kwargs.get("max_tokens", self._max_tokens),
            },
        }

        logger.debug("Ollama generate request: model=%s", self._model)
        result = self._api_call("/api/generate", payload)

        return LLMResponse(
            content=result.get("response", ""),
            model=self._model,
            provider=self.name,
            usage={
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0),
                "total_tokens": (
                    result.get("prompt_eval_count", 0)
                    + result.get("eval_count", 0)
                ),
            },
        )

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        temperature = kwargs.get("temperature", self._temperature)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": kwargs.get("max_tokens", self._max_tokens),
            },
        }

        logger.debug("Ollama chat request: model=%s, messages=%d", self._model, len(messages))
        result = self._api_call("/api/chat", payload)

        msg = result.get("message", {})
        return LLMResponse(
            content=msg.get("content", ""),
            model=self._model,
            provider=self.name,
            usage={
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0),
                "total_tokens": (
                    result.get("prompt_eval_count", 0)
                    + result.get("eval_count", 0)
                ),
            },
        )

    def is_available(self) -> bool:
        """Check whether the Ollama server is reachable."""
        try:
            url = f"{self._base_url}/api/tags"
            req = Request(url)
            with urlopen(req, timeout=5) as resp:  # noqa: S310 — localhost only
                return resp.status == 200
        except (URLError, OSError):
            return False
