"""RAG (Retrieval-Augmented Generation) pipeline for LLM commands.

Provides a structured pipeline that sits between the search/context layer
and the LLM layer, replacing the ad-hoc context assembly in ReasoningEngine.

Pipeline stages:
1. **Retrieve** — multi-strategy retrieval (semantic + keyword + hybrid)
2. **Re-rank** — cross-encoder or score-based re-ranking
3. **Assemble** — token-aware context assembly with budget allocation
4. **Cite** — source citation tracking (file + line references)

Usage::

    pipeline = RAGPipeline(project_root, config)
    context = pipeline.retrieve_and_assemble(query, strategy="hybrid", budget=4000)
    # context.text — assembled context string for LLM prompt
    # context.citations — list of SourceCitation for post-processing
    # context.stats — retrieval stats for explainability
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from semantic_code_intelligence.services.search_service import (
    SearchResult,
    search_codebase,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.rag")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class RetrievalStrategy(str, Enum):
    """Strategy for retrieving context chunks."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    MULTI = "multi"  # Runs semantic + keyword, then merges


@dataclass
class SourceCitation:
    """A source reference for a context chunk used in generation."""

    id: int
    file_path: str
    start_line: int
    end_line: int
    language: str
    score: float
    strategy: str

    def label(self) -> str:
        """Short citation label for inline references."""
        return f"[{self.id}]"

    def reference(self) -> str:
        """Full reference string."""
        name = Path(self.file_path).name
        return f"[{self.id}] {name}:{self.start_line}-{self.end_line}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "score": round(self.score, 4),
            "strategy": self.strategy,
        }


@dataclass
class RetrievalStats:
    """Statistics about the retrieval pipeline for explainability."""

    total_retrieved: int = 0
    after_dedup: int = 0
    after_rerank: int = 0
    after_budget: int = 0
    strategies_used: list[str] = field(default_factory=list)
    total_chars: int = 0
    budget_chars: int = 0
    budget_utilization: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_retrieved": self.total_retrieved,
            "after_dedup": self.after_dedup,
            "after_rerank": self.after_rerank,
            "after_budget": self.after_budget,
            "strategies_used": self.strategies_used,
            "total_chars": self.total_chars,
            "budget_chars": self.budget_chars,
            "budget_utilization": round(self.budget_utilization, 3),
        }


@dataclass
class RAGContext:
    """Assembled context ready for LLM prompt injection."""

    text: str
    chunks: list[dict[str, Any]]
    citations: list[SourceCitation]
    stats: RetrievalStats

    def citation_footer(self) -> str:
        """Build a references section for the LLM prompt."""
        if not self.citations:
            return ""
        lines = ["\nSources:"]
        for c in self.citations:
            lines.append(f"  {c.reference()}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_text_length": len(self.text),
            "chunk_count": len(self.chunks),
            "citations": [c.to_dict() for c in self.citations],
            "stats": self.stats.to_dict(),
        }


# ---------------------------------------------------------------------------
# Re-ranking
# ---------------------------------------------------------------------------

def _keyword_overlap_score(content: str, query_words: list[str]) -> float:
    """Score a chunk by keyword overlap with the query."""
    if not query_words:
        return 0.0
    content_lower = content.lower()
    found = sum(1 for w in query_words if w in content_lower)
    return found / len(query_words)


def _rerank_chunks(
    chunks: list[dict[str, Any]],
    query: str,
    *,
    cross_encoder: bool = False,
) -> list[dict[str, Any]]:
    """Re-rank retrieved chunks by relevance.

    If a cross-encoder model is available and requested, uses it for
    precise re-ranking. Otherwise falls back to a fast heuristic that
    combines the original retrieval score with keyword overlap.

    Args:
        chunks: Retrieved chunks with 'content' and 'score' keys.
        query: The user's query string.
        cross_encoder: Whether to attempt cross-encoder re-ranking.
    """
    if cross_encoder:
        reranked = _cross_encoder_rerank(chunks, query)
        if reranked is not None:
            return reranked

    # Heuristic re-ranking: semantic score + keyword overlap + freshness
    query_words = [w.lower() for w in query.split() if len(w) > 2]

    for chunk in chunks:
        content = chunk.get("content", chunk.get("chunk", ""))
        base_score = float(chunk.get("score", 0.0))
        overlap = _keyword_overlap_score(content, query_words)

        # Boost: exact query substring match
        exact_bonus = 0.15 if query.lower() in content.lower() else 0.0

        # Boost: shorter, focused chunks (less noise)
        length_penalty = max(0, 1.0 - len(content) / 5000) * 0.05

        chunk["rag_score"] = round(
            base_score * 0.6 + overlap * 0.25 + exact_bonus + length_penalty, 4
        )

    chunks.sort(key=lambda c: c.get("rag_score", 0), reverse=True)
    return chunks


def _cross_encoder_rerank(
    chunks: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]] | None:
    """Attempt cross-encoder re-ranking with sentence-transformers.

    Returns None if the cross-encoder is not available, so the caller
    can fall back to heuristic re-ranking.
    """
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
    except ImportError:
        return None

    try:
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
    except Exception:
        logger.debug("Cross-encoder model not available, using heuristic re-ranking.")
        return None

    pairs = [
        (query, chunk.get("content", chunk.get("chunk", ""))[:500])
        for chunk in chunks
    ]
    scores = model.predict(pairs)  # type: ignore[arg-type]

    for chunk, score in zip(chunks, scores):
        chunk["rag_score"] = float(score)

    chunks.sort(key=lambda c: c.get("rag_score", 0), reverse=True)
    logger.debug("Cross-encoder re-ranked %d chunks.", len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for English/code)."""
    return max(1, len(text) // 4)


def _assemble_context(
    chunks: list[dict[str, Any]],
    budget_tokens: int,
    query: str,
) -> tuple[str, list[SourceCitation], int]:
    """Assemble context text from chunks within a token budget.

    Returns (context_text, citations, total_chars).
    Chunks are assumed to be pre-sorted by relevance (descending).
    """
    parts: list[str] = []
    citations: list[SourceCitation] = []
    used_tokens = 0
    cite_id = 0

    for chunk in chunks:
        content = chunk.get("content", chunk.get("chunk", ""))
        if not content.strip():
            continue

        chunk_tokens = _estimate_tokens(content)
        if used_tokens + chunk_tokens > budget_tokens and parts:
            # Budget exceeded — try truncating the last chunk
            remaining = budget_tokens - used_tokens
            if remaining > 50:
                truncated = content[: remaining * 4]
                content = truncated + "\n... [truncated]"
                chunk_tokens = _estimate_tokens(content)
            else:
                break

        cite_id += 1
        file_path = chunk.get("file_path", "unknown")
        start_line = chunk.get("start_line", 0)
        end_line = chunk.get("end_line", 0)
        score = chunk.get("rag_score", chunk.get("score", 0.0))
        language = chunk.get("language", "")
        strategy = chunk.get("strategy", "semantic")

        citation = SourceCitation(
            id=cite_id,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            language=language,
            score=score,
            strategy=strategy,
        )
        citations.append(citation)

        # Format chunk with citation marker
        parts.append(
            f"\n{citation.label()} {file_path}:{start_line}-{end_line}"
            f" (score: {score:.2f})\n"
            f"```{language}\n{content}\n```"
        )
        used_tokens += chunk_tokens

    text = "\n".join(parts)
    return text, citations, len(text)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove near-duplicate chunks based on file+line overlap."""
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for chunk in chunks:
        key = (
            f"{chunk.get('file_path', '')}:"
            f"{chunk.get('start_line', 0)}-{chunk.get('end_line', 0)}"
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)

    return deduped


# ---------------------------------------------------------------------------
# RAG Pipeline
# ---------------------------------------------------------------------------

class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for code context.

    Orchestrates multi-strategy retrieval, re-ranking, deduplication,
    and token-aware context assembly into a single call.
    """

    DEFAULT_BUDGET_TOKENS = 3000
    DEFAULT_TOP_K = 10
    DEFAULT_THRESHOLD = 0.15

    def __init__(
        self,
        project_root: Path,
        *,
        budget_tokens: int | None = None,
        top_k: int | None = None,
        threshold: float | None = None,
        use_cross_encoder: bool = False,
    ) -> None:
        self._root = project_root.resolve()
        self._budget = budget_tokens or self.DEFAULT_BUDGET_TOKENS
        self._top_k = top_k or self.DEFAULT_TOP_K
        self._threshold = threshold or self.DEFAULT_THRESHOLD
        self._use_cross_encoder = use_cross_encoder

    def retrieve(
        self,
        query: str,
        *,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant code chunks using the specified strategy.

        For MULTI strategy, runs both semantic and keyword search and
        merges results with boosted diversity.
        """
        k = top_k or self._top_k

        if strategy == RetrievalStrategy.MULTI:
            return self._multi_retrieve(query, k)

        mode = strategy.value
        try:
            results = search_codebase(
                query,
                self._root,
                top_k=k,
                threshold=self._threshold,
                mode=mode,  # type: ignore[arg-type]
            )
        except Exception:
            logger.debug("Search failed for strategy=%s", strategy, exc_info=True)
            return []

        return [
            {**r.to_dict(), "strategy": strategy.value}
            for r in results
        ]

    def _multi_retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Run semantic + keyword searches and merge results."""
        semantic = self.retrieve(
            query, strategy=RetrievalStrategy.SEMANTIC, top_k=top_k
        )
        keyword = self.retrieve(
            query, strategy=RetrievalStrategy.KEYWORD, top_k=top_k
        )

        # Tag strategies
        for c in semantic:
            c["strategy"] = "semantic"
        for c in keyword:
            c["strategy"] = "keyword"

        # Interleave: semantic results first, then unique keyword results
        combined = list(semantic)
        seen_keys = {
            f"{c.get('file_path', '')}:{c.get('start_line', 0)}"
            for c in semantic
        }
        for c in keyword:
            key = f"{c.get('file_path', '')}:{c.get('start_line', 0)}"
            if key not in seen_keys:
                combined.append(c)
                seen_keys.add(key)

        return combined

    def retrieve_and_assemble(
        self,
        query: str,
        *,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        budget_tokens: int | None = None,
        top_k: int | None = None,
        include_repo_summary: bool = True,
    ) -> RAGContext:
        """Full RAG pipeline: retrieve → dedup → re-rank → assemble.

        Args:
            query: The user's question or search query.
            strategy: Retrieval strategy to use.
            budget_tokens: Token budget for assembled context.
            top_k: Number of chunks to retrieve per strategy.
            include_repo_summary: Whether to prepend a repo summary.

        Returns:
            A RAGContext with assembled text, citations, and stats.
        """
        budget = budget_tokens or self._budget
        strategies_used: list[str] = []

        # Stage 1: Retrieve
        chunks = self.retrieve(query, strategy=strategy, top_k=top_k)
        strategies_used.append(strategy.value)
        total_retrieved = len(chunks)

        # Stage 2: Dedup
        chunks = _dedup_chunks(chunks)
        after_dedup = len(chunks)

        # Stage 3: Re-rank
        chunks = _rerank_chunks(
            chunks, query, cross_encoder=self._use_cross_encoder
        )
        after_rerank = len(chunks)

        # Reserve budget for repo summary if requested
        summary_text = ""
        summary_tokens = 0
        if include_repo_summary:
            summary_text = self._get_repo_summary()
            summary_tokens = _estimate_tokens(summary_text)

        chunk_budget = budget - summary_tokens

        # Stage 4: Assemble with token budget
        context_text, citations, total_chars = _assemble_context(
            chunks, max(chunk_budget, 200), query
        )

        # Prepend summary
        if summary_text:
            context_text = f"Repository overview:\n{summary_text}\n\n{context_text}"
            total_chars += len(summary_text)

        after_budget = len(citations)
        budget_utilization = total_chars / max(budget * 4, 1)  # approx

        stats = RetrievalStats(
            total_retrieved=total_retrieved,
            after_dedup=after_dedup,
            after_rerank=after_rerank,
            after_budget=after_budget,
            strategies_used=strategies_used,
            total_chars=total_chars,
            budget_chars=budget * 4,
            budget_utilization=min(budget_utilization, 1.0),
        )

        return RAGContext(
            text=context_text,
            chunks=[c for c in chunks[:after_budget]],
            citations=citations,
            stats=stats,
        )

    def _get_repo_summary(self) -> str:
        """Build a brief repo summary for context."""
        try:
            from semantic_code_intelligence.context.engine import ContextBuilder
            from semantic_code_intelligence.analysis.ai_features import (
                summarize_repository,
            )
            from semantic_code_intelligence.config.settings import load_config
            from semantic_code_intelligence.indexing.scanner import scan_repository

            config = load_config(self._root)
            builder = ContextBuilder()
            scanned = scan_repository(self._root, config.index)
            for sf in scanned[:100]:  # Limit for speed
                try:
                    builder.index_file(str(self._root / sf.relative_path))
                except Exception:
                    pass
            summary = summarize_repository(builder)
            return summary.render()[:1500]  # Cap summary size
        except Exception:
            logger.debug("Repo summary unavailable.", exc_info=True)
            return ""

    # --- convenience methods ---

    def build_system_prompt(
        self,
        task: str = "answer",
        *,
        cite_sources: bool = True,
    ) -> str:
        """Build a system prompt appropriate for the RAG task.

        Args:
            task: One of 'answer', 'review', 'refactor', 'investigate'.
            cite_sources: Whether to ask the LLM to cite sources.
        """
        citation_instruction = ""
        if cite_sources:
            citation_instruction = (
                " When referencing code, cite sources using [N] markers "
                "that match the numbered source references provided in the context."
            )

        prompts = {
            "answer": (
                "You are CodexA, an AI coding assistant. Answer the user's "
                "question about their codebase using ONLY the provided context. "
                "Be concise, accurate, and technical."
                f"{citation_instruction}"
            ),
            "review": (
                "You are CodexA, a code review assistant. Analyze the provided "
                "code and return findings as JSON with 'issues' (list of "
                "{'severity', 'line', 'message', 'suggestion'}) and 'summary'."
                f"{citation_instruction}"
            ),
            "refactor": (
                "You are CodexA, a refactoring assistant. Suggest improvements "
                "to the provided code. Return JSON with 'refactored_code' and "
                "'explanation'."
                f"{citation_instruction}"
            ),
            "investigate": (
                "You are CodexA, an autonomous code investigator. Analyze the "
                "context and decide the next investigation step."
                f"{citation_instruction}"
            ),
        }
        return prompts.get(task, prompts["answer"])
