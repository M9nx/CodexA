"""Reasoning engine — orchestrates context gathering and LLM interaction.

Provides the core logic behind ``codex ask``, ``codex review``, and
``codex refactor`` by combining:
1. Semantic search results
2. Parsed symbol / context data
3. LLM conversations

Each public method returns structured data suitable for CLI display and
machine consumption.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.analysis.ai_features import (
    explain_symbol,
    generate_ai_context,
    summarize_repository,
)
from semantic_code_intelligence.context.engine import ContextBuilder
from semantic_code_intelligence.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
)
from semantic_code_intelligence.services.search_service import search_codebase
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.reasoning")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class AskResult:
    """Result of an ``ask`` operation."""

    question: str
    answer: str
    context_snippets: list[dict[str, Any]] = field(default_factory=list)
    llm_response: LLMResponse | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "context_snippets": self.context_snippets,
            "usage": self.llm_response.usage if self.llm_response else {},
        }


@dataclass
class ReviewResult:
    """Result of a ``review`` operation."""

    file_path: str
    issues: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    llm_response: LLMResponse | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "issues": self.issues,
            "summary": self.summary,
            "usage": self.llm_response.usage if self.llm_response else {},
        }


@dataclass
class RefactorResult:
    """Result of a ``refactor`` operation."""

    file_path: str
    original_code: str = ""
    refactored_code: str = ""
    explanation: str = ""
    llm_response: LLMResponse | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "original_code": self.original_code,
            "refactored_code": self.refactored_code,
            "explanation": self.explanation,
            "usage": self.llm_response.usage if self.llm_response else {},
        }


@dataclass
class SuggestResult:
    """Result of a ``suggest`` operation."""

    target: str
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    llm_response: LLMResponse | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "suggestions": self.suggestions,
            "usage": self.llm_response.usage if self.llm_response else {},
        }


# ---------------------------------------------------------------------------
# Reasoning Engine
# ---------------------------------------------------------------------------

class ReasoningEngine:
    """High-level reasoning engine that combines semantic context with LLM.

    This is the central orchestrator for all AI workflows in CodexA.
    """

    def __init__(
        self,
        provider: LLMProvider,
        project_root: Path,
        *,
        builder: ContextBuilder | None = None,
    ) -> None:
        self._provider = provider
        self._root = project_root.resolve()
        self._builder = builder or ContextBuilder()
        self._indexed = False

    def _ensure_indexed(self) -> None:
        """Lazy-index the project for symbol/context lookups."""
        if self._indexed:
            return
        from semantic_code_intelligence.config.settings import load_config
        from semantic_code_intelligence.indexing.scanner import scan_repository

        config = load_config(self._root)
        scanned = scan_repository(self._root, config.index)
        for sf in scanned:
            full_path = str(self._root / sf.relative_path)
            try:
                self._builder.index_file(full_path)
            except Exception:
                logger.debug("Failed to index %s", full_path)
        self._indexed = True

    # --- gather context helpers ---

    def _search_context(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Run semantic search and return snippet dicts."""
        try:
            results = search_codebase(query, self._root, top_k=top_k, threshold=0.2)
            return [r.to_dict() for r in results]
        except Exception:
            logger.debug("Semantic search unavailable, proceeding without search context.")
            return []

    def _file_context(self, file_path: str) -> str:
        """Read a file's content, returning the text."""
        try:
            return Path(file_path).read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            return ""

    def _symbol_context(self, symbol_name: str) -> str:
        """Build a text summary of a symbol for use in prompts."""
        self._ensure_indexed()
        matches = self._builder.find_symbol(symbol_name)
        if not matches:
            return ""
        explanations = [explain_symbol(s, self._builder) for s in matches[:3]]
        parts: list[str] = []
        for exp in explanations:
            parts.append(exp.render())
        return "\n\n".join(parts)

    # --- public AI workflows ---

    def ask(self, question: str, *, top_k: int = 5) -> AskResult:
        """Answer a natural-language question about the codebase.

        Gathers semantic search results and repo context, then asks the LLM.
        """
        snippets = self._search_context(question, top_k=top_k)
        self._ensure_indexed()
        repo_summary = summarize_repository(self._builder).render()

        # Build prompt
        context_text = ""
        for snip in snippets:
            context_text += (
                f"\n--- {snip.get('file_path', '?')} "
                f"(score: {snip.get('score', 0):.2f}) ---\n"
                f"{snip.get('content', snip.get('chunk', ''))}\n"
            )

        system = (
            "You are CodexA, an AI coding assistant. Answer questions about the "
            "user's codebase using the provided context. Be concise, accurate, "
            "and cite file paths when relevant."
        )
        user_msg = (
            f"Repository summary:\n{repo_summary}\n\n"
            f"Relevant code snippets:{context_text}\n\n"
            f"Question: {question}"
        )

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=system),
            LLMMessage(role=MessageRole.USER, content=user_msg),
        ]
        resp = self._provider.chat(messages)

        return AskResult(
            question=question,
            answer=resp.content,
            context_snippets=snippets,
            llm_response=resp,
        )

    def review(self, file_path: str) -> ReviewResult:
        """Review a file for potential issues, bugs, and improvements."""
        content = self._file_context(file_path)
        if not content:
            return ReviewResult(file_path=file_path, summary="File not found or empty.")

        self._ensure_indexed()
        symbols = self._builder.get_symbols(file_path)
        symbol_info = "\n".join(
            f"  - {s.kind} '{s.name}' (L{s.start_line}-{s.end_line})"
            for s in symbols[:30]
        )

        system = (
            "You are CodexA, a code reviewer. Analyze the provided file and "
            "return a JSON object with keys: 'issues' (list of objects with "
            "'severity', 'line', 'message', 'suggestion') and 'summary' (string). "
            "Severities: 'error', 'warning', 'info'. Be precise and actionable."
        )
        user_msg = (
            f"File: {file_path}\n\n"
            f"Symbols:\n{symbol_info}\n\n"
            f"Source code:\n```\n{content[:8000]}\n```"
        )

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=system),
            LLMMessage(role=MessageRole.USER, content=user_msg),
        ]
        resp = self._provider.chat(messages)

        # Parse JSON from response — fallback to raw text
        issues: list[dict[str, Any]] = []
        summary = resp.content
        try:
            parsed = json.loads(resp.content)
            if isinstance(parsed, dict):
                issues = parsed.get("issues", [])
                summary = parsed.get("summary", resp.content)
        except (json.JSONDecodeError, TypeError):
            pass

        return ReviewResult(
            file_path=file_path,
            issues=issues,
            summary=summary,
            llm_response=resp,
        )

    def refactor(
        self,
        file_path: str,
        instruction: str = "Improve code quality, readability, and performance.",
    ) -> RefactorResult:
        """Suggest refactored code for a file based on an instruction."""
        content = self._file_context(file_path)
        if not content:
            return RefactorResult(file_path=file_path, explanation="File not found or empty.")

        system = (
            "You are CodexA, a code refactoring assistant. Given the source code "
            "and an instruction, return a JSON object with 'refactored_code' "
            "(the improved code as a string) and 'explanation' (what you changed "
            "and why). Do NOT include markdown fences inside the JSON values."
        )
        user_msg = (
            f"File: {file_path}\n"
            f"Instruction: {instruction}\n\n"
            f"Source code:\n```\n{content[:8000]}\n```"
        )

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=system),
            LLMMessage(role=MessageRole.USER, content=user_msg),
        ]
        resp = self._provider.chat(messages)

        refactored = ""
        explanation = resp.content
        try:
            parsed = json.loads(resp.content)
            if isinstance(parsed, dict):
                refactored = parsed.get("refactored_code", "")
                explanation = parsed.get("explanation", resp.content)
        except (json.JSONDecodeError, TypeError):
            pass

        return RefactorResult(
            file_path=file_path,
            original_code=content,
            refactored_code=refactored,
            explanation=explanation,
            llm_response=resp,
        )

    def suggest(self, target: str, *, top_k: int = 5) -> SuggestResult:
        """Generate intelligent suggestions for a symbol, file, or topic.

        Combines call-graph, dependency, and semantic data with LLM reasoning
        to produce actionable suggestions with "why" reasoning.
        """
        self._ensure_indexed()
        snippets = self._search_context(target, top_k=top_k)
        sym_context = self._symbol_context(target)

        system = (
            "You are CodexA, an intelligent code suggestion engine. Given context "
            "about a codebase element, provide suggestions for improvements, fixes, "
            "or optimizations. Return a JSON object with 'suggestions' — a list of "
            "objects each having 'title', 'description', 'reason', and 'priority' "
            "(high/medium/low)."
        )
        context_text = ""
        for snip in snippets:
            context_text += (
                f"\n--- {snip.get('file_path', '?')} ---\n"
                f"{snip.get('content', snip.get('chunk', ''))}\n"
            )

        user_msg = (
            f"Target: {target}\n\n"
            f"Symbol info:\n{sym_context}\n\n"
            f"Related code:{context_text}"
        )

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=system),
            LLMMessage(role=MessageRole.USER, content=user_msg),
        ]
        resp = self._provider.chat(messages)

        suggestions: list[dict[str, Any]] = []
        try:
            parsed = json.loads(resp.content)
            if isinstance(parsed, dict):
                suggestions = parsed.get("suggestions", [])
            elif isinstance(parsed, list):
                suggestions = parsed
        except (json.JSONDecodeError, TypeError):
            suggestions = [{"title": "Raw response", "description": resp.content, "reason": "", "priority": "medium"}]

        return SuggestResult(
            target=target,
            suggestions=suggestions,
            llm_response=resp,
        )
