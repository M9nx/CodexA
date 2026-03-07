"""LLM integration layer — provider abstraction, reasoning engine, and safety.

Provides:
- LLMProvider: abstract base class for LLM backends
- OpenAIProvider: OpenAI API integration
- OllamaProvider: Ollama local model integration
- MockProvider: deterministic mock for testing
- ReasoningEngine: orchestrates context + LLM for AI-assisted tasks
- SafetyValidator: validates LLM outputs before applying
"""

from __future__ import annotations

from semantic_code_intelligence.llm.provider import (
    LLMProvider,
    LLMResponse,
    LLMMessage,
)
from semantic_code_intelligence.llm.openai_provider import OpenAIProvider
from semantic_code_intelligence.llm.ollama_provider import OllamaProvider
from semantic_code_intelligence.llm.mock_provider import MockProvider
from semantic_code_intelligence.llm.reasoning import ReasoningEngine
from semantic_code_intelligence.llm.safety import SafetyValidator

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMMessage",
    "OpenAIProvider",
    "OllamaProvider",
    "MockProvider",
    "ReasoningEngine",
    "SafetyValidator",
]
