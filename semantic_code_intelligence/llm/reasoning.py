"""Reasoning engine — orchestrates context gathering and LLM interaction.

Provides the core logic behind ``codexa ask``, ``codexa review``, and
``codexa refactor`` by combining:
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
from semantic_code_intelligence.llm.rag import (
    RAGContext,
    RAGPipeline,
    RetrievalStrategy,
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
    explainability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "context_snippets": self.context_snippets,
            "usage": self.llm_response.usage if self.llm_response else {},
            "explainability": self.explainability,
        }


@dataclass
class ReviewResult:
    """Result of a ``review`` operation."""

    file_path: str
    issues: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    llm_response: LLMResponse | None = None
    explainability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "issues": self.issues,
            "summary": self.summary,
            "usage": self.llm_response.usage if self.llm_response else {},
            "explainability": self.explainability,
        }


@dataclass
class RefactorResult:
    """Result of a ``refactor`` operation."""

    file_path: str
    original_code: str = ""
    refactored_code: str = ""
    explanation: str = ""
    llm_response: LLMResponse | None = None
    explainability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "original_code": self.original_code,
            "refactored_code": self.refactored_code,
            "explanation": self.explanation,
            "usage": self.llm_response.usage if self.llm_response else {},
            "explainability": self.explainability,
        }


@dataclass
class SuggestResult:
    """Result of a ``suggest`` operation."""

    target: str
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    llm_response: LLMResponse | None = None
    explainability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "suggestions": self.suggestions,
            "usage": self.llm_response.usage if self.llm_response else {},
            "explainability": self.explainability,
        }


# ---------------------------------------------------------------------------
# Reasoning Engine
# ---------------------------------------------------------------------------

class ReasoningEngine:
    """High-level reasoning engine that combines semantic context with LLM.

    This is the central orchestrator for all AI workflows in CodexA.
    """

    DEFAULT_MAX_CONTEXT_CHARS = 6000

    def __init__(
        self,
        provider: LLMProvider,
        project_root: Path,
        *,
        builder: ContextBuilder | None = None,
        max_context_chars: int | None = None,
        rag_budget_tokens: int | None = None,
        rag_strategy: str = "hybrid",
        use_cross_encoder: bool = False,
    ) -> None:
        self._provider = provider
        self._root = project_root.resolve()
        self._builder = builder or ContextBuilder()
        self._indexed = False
        self._max_ctx = max_context_chars or self.DEFAULT_MAX_CONTEXT_CHARS
        self._rag = RAGPipeline(
            self._root,
            budget_tokens=rag_budget_tokens or (self._max_ctx // 4),
            use_cross_encoder=use_cross_encoder,
        )
        try:
            self._rag_strategy = RetrievalStrategy(rag_strategy)
        except ValueError:
            self._rag_strategy = RetrievalStrategy.HYBRID

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

    # --- context pruning & scoring (Phase 12) ---

    @staticmethod
    def _score_snippet(snippet: dict[str, Any], query_lower: str) -> float:
        """Compute a priority score for a context snippet.

        Combines the semantic search score with a keyword-overlap bonus.
        """
        base = float(snippet.get("score", 0.0))
        content = snippet.get("content", snippet.get("chunk", "")).lower()
        # Keyword overlap bonus: fraction of query words found in snippet
        words = [w for w in query_lower.split() if len(w) > 2]
        if words:
            found = sum(1 for w in words if w in content)
            base += 0.1 * (found / len(words))
        return round(base, 4)

    def _prune_context(
        self,
        snippets: list[dict[str, Any]],
        query: str,
        max_chars: int | None = None,
    ) -> list[dict[str, Any]]:
        """Score, rank, and prune snippets to stay within token budget.

        Returns a subset of *snippets* sorted by priority score (descending),
        trimmed so total character count stays within *max_chars*.
        """
        limit = max_chars or self._max_ctx
        query_lower = query.lower()
        scored = [
            (self._score_snippet(s, query_lower), s)
            for s in snippets
        ]
        scored.sort(key=lambda t: t[0], reverse=True)

        kept: list[dict[str, Any]] = []
        total = 0
        for score, snip in scored:
            text = snip.get("content", snip.get("chunk", ""))
            if total + len(text) > limit and kept:
                break
            snip["priority_score"] = score
            kept.append(snip)
            total += len(text)
        return kept

    # --- public AI workflows ---

    def ask(self, question: str, *, top_k: int = 5) -> AskResult:
        """Answer a natural-language question about the codebase.

        Uses the RAG pipeline: retrieve → dedup → re-rank → assemble,
        then sends the assembled context to the LLM with source citations.
        """
        rag_ctx = self._rag.retrieve_and_assemble(
            question,
            strategy=self._rag_strategy,
            top_k=top_k,
            include_repo_summary=True,
        )

        system = self._rag.build_system_prompt("answer", cite_sources=True)
        user_msg = (
            f"Context:\n{rag_ctx.text}"
            f"{rag_ctx.citation_footer()}\n\n"
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
            context_snippets=rag_ctx.chunks,
            llm_response=resp,
            explainability={
                **rag_ctx.stats.to_dict(),
                "citations": [c.to_dict() for c in rag_ctx.citations],
                "method": "rag_pipeline",
            },
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

        Uses RAG pipeline for context, plus symbol-specific data when available.
        """
        self._ensure_indexed()
        sym_context = self._symbol_context(target)

        rag_ctx = self._rag.retrieve_and_assemble(
            target,
            strategy=self._rag_strategy,
            top_k=top_k,
            include_repo_summary=False,
        )

        system = (
            "You are CodexA, an intelligent code suggestion engine. Given context "
            "about a codebase element, provide suggestions for improvements, fixes, "
            "or optimizations. Return a JSON object with 'suggestions' — a list of "
            "objects each having 'title', 'description', 'reason', and 'priority' "
            "(high/medium/low). When referencing code, cite sources using [N] markers."
        )

        user_msg = (
            f"Target: {target}\n\n"
            f"Symbol info:\n{sym_context}\n\n"
            f"Related code:{rag_ctx.text}"
            f"{rag_ctx.citation_footer()}"
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
            explainability={
                **rag_ctx.stats.to_dict(),
                "citations": [c.to_dict() for c in rag_ctx.citations],
                "method": "rag_pipeline",
            },
        )
