"""Hybrid search — fuses semantic (FAISS) and keyword (BM25) results via RRF.

Reciprocal Rank Fusion combines two ranked lists into a single list that
benefits from both semantic understanding and exact keyword matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.embeddings.generator import generate_embeddings
from semantic_code_intelligence.search.keyword_search import (
    BM25Index,
    KeywordResult,
    _get_bm25,
    keyword_search,
)
from semantic_code_intelligence.storage.vector_store import VectorStore
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("search.hybrid")

# Default RRF constant (k=60 is standard in literature)
RRF_K = 60


@dataclass
class HybridResult:
    """A search result produced by fusing semantic + keyword rankings."""

    file_path: str
    start_line: int
    end_line: int
    language: str
    content: str
    score: float           # fused RRF score
    semantic_score: float  # original cosine similarity (0 if not in semantic)
    keyword_score: float   # original BM25 score (0 if not in keyword)
    chunk_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "content": self.content,
            "score": round(self.score, 6),
            "semantic_score": round(self.semantic_score, 4),
            "keyword_score": round(self.keyword_score, 4),
            "chunk_index": self.chunk_index,
        }


def _chunk_key(meta: Any) -> str:
    """Unique key for de-duplicating chunks across result lists."""
    return f"{meta.file_path}:{meta.start_line}:{meta.end_line}"


def reciprocal_rank_fusion(
    semantic_ranking: list[tuple[int, float]],
    keyword_ranking: list[tuple[int, float]],
    k: int = RRF_K,
) -> list[tuple[int, float, float, float]]:
    """Fuse two ranked lists via Reciprocal Rank Fusion.

    Args:
        semantic_ranking: [(chunk_index_in_store, cosine_score), ...] ordered best-first.
        keyword_ranking:  [(chunk_index_in_store, bm25_score), ...]  ordered best-first.
        k: RRF smoothing constant.

    Returns:
        [(chunk_index, fused_score, semantic_score, keyword_score), ...]
        sorted by fused_score descending.
    """
    scores: dict[int, float] = {}
    sem_scores: dict[int, float] = {}
    kw_scores: dict[int, float] = {}

    for rank, (idx, score) in enumerate(semantic_ranking):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
        sem_scores[idx] = score

    for rank, (idx, score) in enumerate(keyword_ranking):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
        kw_scores[idx] = score

    fused = [
        (idx, fused_score, sem_scores.get(idx, 0.0), kw_scores.get(idx, 0.0))
        for idx, fused_score in scores.items()
    ]
    fused.sort(key=lambda x: x[1], reverse=True)
    return fused


def hybrid_search(
    query: str,
    store: VectorStore,
    index_dir: Path,
    model_name: str = "all-MiniLM-L6-v2",
    top_k: int = 10,
    semantic_weight: int | None = None,
    keyword_weight: int | None = None,
) -> list[HybridResult]:
    """Execute a hybrid search combining semantic and BM25 keyword results.

    Args:
        query: Natural language or keyword query.
        store: Loaded VectorStore.
        index_dir: Path to index directory.
        model_name: Embedding model name.
        top_k: Number of final results.
        semantic_weight: How many candidates to pull from semantic (default 2×top_k).
        keyword_weight: How many candidates to pull from keyword (default 2×top_k).

    Returns:
        List of HybridResult, sorted by fused RRF score.
    """
    if store.size == 0:
        return []

    candidate_k = top_k * 2

    # --- Semantic arm ---
    query_embedding = generate_embeddings([query], model_name=model_name)[0]
    sem_raw = store.search(query_embedding, top_k=semantic_weight or candidate_k)

    # Map (ChunkMetadata, score) → (metadata_index, score)
    # We need the metadata index to identify chunks across both arms
    meta_to_idx: dict[str, int] = {}
    for i, m in enumerate(store.metadata):
        key = _chunk_key(m)
        if key not in meta_to_idx:
            meta_to_idx[key] = i

    semantic_ranking: list[tuple[int, float]] = []
    for meta, score in sem_raw:
        key = _chunk_key(meta)
        idx = meta_to_idx.get(key, -1)
        if idx >= 0:
            semantic_ranking.append((idx, float(score)))

    # --- Keyword arm (BM25) ---
    bm25 = _get_bm25(index_dir, store)
    keyword_ranking = bm25.search(query, top_k=keyword_weight or candidate_k)

    # --- Fusion ---
    fused = reciprocal_rank_fusion(semantic_ranking, keyword_ranking)

    results: list[HybridResult] = []
    for idx, fused_score, sem_score, kw_score in fused[:top_k]:
        meta = store.metadata[idx]
        results.append(
            HybridResult(
                file_path=meta.file_path,
                start_line=meta.start_line,
                end_line=meta.end_line,
                language=meta.language,
                content=meta.content,
                score=fused_score,
                semantic_score=sem_score,
                keyword_score=kw_score,
                chunk_index=meta.chunk_index,
            )
        )

    return results
