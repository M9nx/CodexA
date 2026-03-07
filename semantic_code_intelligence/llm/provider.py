"""LLM provider abstraction — base class and data types for LLM integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LLMMessage:
    """A single message in an LLM conversation."""

    role: MessageRole
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role.value, "content": self.content}


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str = ""
    provider: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage,
        }


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Subclasses must implement `complete()` and `chat()`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g. 'openai', 'ollama')."""
        ...

    @abstractmethod
    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a completion for a single prompt.

        Args:
            prompt: The text prompt to complete.
            **kwargs: Provider-specific options (temperature, max_tokens, etc.).

        Returns:
            An LLMResponse containing the generated text.
        """
        ...

    @abstractmethod
    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        """Generate a response for a multi-turn conversation.

        Args:
            messages: Conversation history as a list of LLMMessage.
            **kwargs: Provider-specific options.

        Returns:
            An LLMResponse containing the assistant's reply.
        """
        ...

    def is_available(self) -> bool:
        """Check whether the provider is configured and reachable.

        Default: True. Subclasses may override for connectivity checks.
        """
        return True
