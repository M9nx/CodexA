"""LLM integration layer — provider abstraction, reasoning engine, and safety.

Provides:
- LLMProvider: abstract base class for LLM backends
- OpenAIProvider: OpenAI API integration
- OllamaProvider: Ollama local model integration
- MockProvider: deterministic mock for testing
- ReasoningEngine: orchestrates context + LLM for AI-assisted tasks
- SafetyValidator: validates LLM outputs before applying
- ConversationSession / SessionStore: multi-turn conversation persistence
- InvestigationChain: autonomous multi-step code investigation
- stream_chat / StreamEvent: streaming LLM responses with plugin hooks
- analyze_cross_repo: cross-repo refactoring suggestions
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
from semantic_code_intelligence.llm.conversation import ConversationSession, SessionStore
from semantic_code_intelligence.llm.investigation import InvestigationChain, InvestigationResult
from semantic_code_intelligence.llm.streaming import stream_chat, StreamEvent
from semantic_code_intelligence.llm.cross_refactor import analyze_cross_repo, CrossRefactorResult

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMMessage",
    "OpenAIProvider",
    "OllamaProvider",
    "MockProvider",
    "ReasoningEngine",
    "SafetyValidator",
    "ConversationSession",
    "SessionStore",
    "InvestigationChain",
    "InvestigationResult",
    "stream_chat",
    "StreamEvent",
    "analyze_cross_repo",
    "CrossRefactorResult",
]
