"""Keyword and regex search engine — BM25 scoring + regex matching.

Provides grep-compatible text search and BM25-ranked keyword search
over indexed code chunks, without requiring external dependencies.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from semantic_code_intelligence.storage.vector_store import ChunkMetadata, VectorStore
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("search.keyword")


@dataclass
class KeywordResult:
    """A single keyword/regex search result."""

    file_path: str
    start_line: int
    end_line: int
    language: str
    content: str
    score: float
    chunk_index: int
    match_count: int
    matched_lines: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "content": self.content,
            "score": round(self.score, 4),
            "chunk_index": self.chunk_index,
            "match_count": self.match_count,
            "matched_lines": self.matched_lines,
        }


# ---------------------------------------------------------------------------
# BM25 Scorer
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Split text into tokens by camelCase boundaries, underscores, and whitespace."""
    # First split camelCase: "getValue" -> ["get", "Value"]
    # Then split on underscores, digits separated
    parts = re.findall(r"[a-z]+|[A-Z][a-z]*|[0-9]+", text)
    return parts


def _lower_tokens(text: str) -> list[str]:
    return [t.lower() for t in _tokenize(text)]


class BM25Index:
    """A lightweight in-memory BM25 index over chunk metadata.

    Built lazily from a VectorStore's metadata list so we can share
    the same stored chunks for both semantic and keyword search.
    """

    k1: float = 1.5
    b: float = 0.75

    def __init__(self, metadata: list[ChunkMetadata]) -> None:
        self.metadata = metadata
        self.n = len(metadata)
        self.doc_tokens: list[list[str]] = []
        self.doc_lengths: list[int] = []
        self.avgdl: float = 0.0
        # term -> {doc_idx: term_freq}
        self.inverted: dict[str, dict[int, int]] = {}
        self._build()

    def _build(self) -> None:
        total_len = 0
        for idx, meta in enumerate(self.metadata):
            tokens = _lower_tokens(meta.content)
            self.doc_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)
            seen: dict[str, int] = {}
            for tok in tokens:
                seen[tok] = seen.get(tok, 0) + 1
            for tok, freq in seen.items():
                if tok not in self.inverted:
                    self.inverted[tok] = {}
                self.inverted[tok][idx] = freq
        self.avgdl = total_len / self.n if self.n else 1.0

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Return (doc_index, bm25_score) pairs sorted descending."""
        query_tokens = _lower_tokens(query)
        if not query_tokens:
            return []

        scores: dict[int, float] = {}
        for token in set(query_tokens):
            postings = self.inverted.get(token)
            if not postings:
                continue
            df = len(postings)
            idf = math.log((self.n - df + 0.5) / (df + 0.5) + 1.0)
            for doc_idx, tf in postings.items():
                dl = self.doc_lengths[doc_idx]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * numerator / denominator

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_bm25_cache: dict[str, BM25Index] = {}


def _get_bm25(index_dir: Path, store: VectorStore) -> BM25Index:
    """Get or build a BM25 index for the given vector store."""
    cache_key = str(index_dir)
    cached = _bm25_cache.get(cache_key)
    if cached is not None and cached.n == store.size:
        return cached
    logger.debug("Building BM25 index over %d chunks.", store.size)
    idx = BM25Index(store.metadata)
    _bm25_cache[cache_key] = idx
    return idx


def keyword_search(
    query: str,
    store: VectorStore,
    index_dir: Path,
    top_k: int = 10,
    threshold: float = 0.0,
) -> list[KeywordResult]:
    """BM25-ranked keyword search over indexed chunks.

    Args:
        query: The search query (natural language or keywords).
        store: Loaded VectorStore with metadata.
        index_dir: Path to index directory (for caching).
        top_k: Max results.
        threshold: Minimum BM25 score.

    Returns:
        Sorted list of KeywordResult.
    """
    if store.size == 0:
        return []

    bm25 = _get_bm25(index_dir, store)
    hits = bm25.search(query, top_k=top_k)

    results: list[KeywordResult] = []
    for doc_idx, score in hits:
        if score < threshold:
            continue
        meta = store.metadata[doc_idx]
        results.append(
            KeywordResult(
                file_path=meta.file_path,
                start_line=meta.start_line,
                end_line=meta.end_line,
                language=meta.language,
                content=meta.content,
                score=score,
                chunk_index=meta.chunk_index,
                match_count=0,
                matched_lines=[],
            )
        )
    return results


def regex_search(
    pattern: str,
    store: VectorStore,
    top_k: int = 10,
    case_insensitive: bool = True,
) -> list[KeywordResult]:
    """Regex/grep-style search over indexed chunks.

    Args:
        pattern: Regex pattern string.
        store: Loaded VectorStore with metadata.
        top_k: Max results.
        case_insensitive: Whether to use case-insensitive matching.

    Returns:
        Sorted list of KeywordResult (scored by match count).
    """
    if store.size == 0:
        return []

    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        logger.warning("Invalid regex pattern %r: %s", pattern, exc)
        return []

    results: list[KeywordResult] = []
    for meta in store.metadata:
        lines = meta.content.splitlines()
        matched_lines: list[int] = []
        for i, line in enumerate(lines):
            if compiled.search(line):
                matched_lines.append(meta.start_line + i)
        if matched_lines:
            results.append(
                KeywordResult(
                    file_path=meta.file_path,
                    start_line=meta.start_line,
                    end_line=meta.end_line,
                    language=meta.language,
                    content=meta.content,
                    score=float(len(matched_lines)),
                    chunk_index=meta.chunk_index,
                    match_count=len(matched_lines),
                    matched_lines=matched_lines,
                )
            )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]
