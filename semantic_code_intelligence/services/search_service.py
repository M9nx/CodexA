"""Search service — handles semantic, keyword, regex, and hybrid search.

Supports four modes:
- **semantic** (default): FAISS cosine-similarity search
- **keyword**: BM25-ranked keyword search
- **regex**: grep-compatible regex pattern matching
- **hybrid**: Reciprocal Rank Fusion of semantic + BM25

Also supports ``--full-section`` expansion and auto-indexing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.embeddings.generator import generate_embeddings
from semantic_code_intelligence.storage.query_history import QueryHistory
from semantic_code_intelligence.storage.vector_store import ChunkMetadata, VectorStore
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("services.search")

SearchMode = Literal["semantic", "keyword", "regex", "hybrid"]


@dataclass
class SearchResult:
    """A single search result with metadata and similarity score."""

    file_path: str
    start_line: int
    end_line: int
    language: str
    content: str
    score: float
    chunk_index: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "content": self.content,
            "score": round(self.score, 4),
            "chunk_index": self.chunk_index,
        }


def _auto_index_if_needed(project_root: Path, index_dir: Path) -> None:
    """Run indexing transparently if no vector store exists yet."""
    vectors_faiss = index_dir / "vectors.faiss"
    vectors_bin = index_dir / "vectors.bin"
    if vectors_faiss.exists() or vectors_bin.exists():
        return
    logger.info("No index found — auto-indexing %s", project_root)
    from semantic_code_intelligence.services.indexing_service import run_indexing
    run_indexing(project_root, force=False)


def _load_store(index_dir: Path) -> VectorStore:
    """Load the vector store (raises FileNotFoundError if missing)."""
    store = VectorStore.load(index_dir)
    logger.info("Loaded vector store with %d vectors.", store.size)
    return store


def _record_history(
    index_dir: Path,
    query: str,
    results: list[SearchResult],
) -> None:
    """Record a query in the persistent history (best-effort)."""
    try:
        history = QueryHistory.load(index_dir)
        languages = sorted(set(r.language for r in results if r.language))
        top_files = list(dict.fromkeys(r.file_path for r in results))[:5]
        history.record(
            query=query,
            result_count=len(results),
            top_score=results[0].score if results else 0.0,
            languages=languages,
            top_files=top_files,
        )
        history.save(index_dir)
    except Exception:
        logger.debug("Failed to record query history.")


# ------------------------------------------------------------------
# Semantic search (original behaviour)
# ------------------------------------------------------------------

def _semantic_search(
    query: str,
    store: VectorStore,
    config: Any,
    top_k: int,
    threshold: float,
) -> list[SearchResult]:
    query_embedding = generate_embeddings(
        [query], model_name=config.embedding.model_name,
    )[0]
    raw_results = store.search(query_embedding, top_k=top_k)

    results: list[SearchResult] = []
    for meta, score in raw_results:
        if score < threshold:
            continue
        results.append(
            SearchResult(
                file_path=meta.file_path,
                start_line=meta.start_line,
                end_line=meta.end_line,
                language=meta.language,
                content=meta.content,
                score=score,
                chunk_index=meta.chunk_index,
            )
        )
    return results


# ------------------------------------------------------------------
# Keyword / regex / hybrid helpers
# ------------------------------------------------------------------

def _keyword_search(
    query: str,
    store: VectorStore,
    index_dir: Path,
    top_k: int,
) -> list[SearchResult]:
    from semantic_code_intelligence.search.keyword_search import keyword_search
    hits = keyword_search(query, store, index_dir, top_k=top_k)
    return [
        SearchResult(
            file_path=h.file_path,
            start_line=h.start_line,
            end_line=h.end_line,
            language=h.language,
            content=h.content,
            score=h.score,
            chunk_index=h.chunk_index,
        )
        for h in hits
    ]


def _regex_search(
    pattern: str,
    store: VectorStore,
    top_k: int,
    case_insensitive: bool = True,
) -> list[SearchResult]:
    from semantic_code_intelligence.search.keyword_search import regex_search
    hits = regex_search(pattern, store, top_k=top_k, case_insensitive=case_insensitive)
    return [
        SearchResult(
            file_path=h.file_path,
            start_line=h.start_line,
            end_line=h.end_line,
            language=h.language,
            content=h.content,
            score=h.score,
            chunk_index=h.chunk_index,
        )
        for h in hits
    ]


def _hybrid_search(
    query: str,
    store: VectorStore,
    index_dir: Path,
    config: Any,
    top_k: int,
) -> list[SearchResult]:
    from semantic_code_intelligence.search.hybrid_search import hybrid_search
    hits = hybrid_search(
        query, store, index_dir,
        model_name=config.embedding.model_name,
        top_k=top_k,
    )
    return [
        SearchResult(
            file_path=h.file_path,
            start_line=h.start_line,
            end_line=h.end_line,
            language=h.language,
            content=h.content,
            score=h.score,
            chunk_index=h.chunk_index,
        )
        for h in hits
    ]


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def search_codebase(
    query: str,
    project_root: Path,
    top_k: int | None = None,
    threshold: float | None = None,
    mode: SearchMode = "semantic",
    full_section: bool = False,
    auto_index: bool = True,
    case_insensitive: bool = True,
) -> list[SearchResult]:
    """Search the indexed codebase.

    Args:
        query: Natural language query, keywords, or regex pattern.
        project_root: Root directory of the project.
        top_k: Number of top results to return. Uses config default if None.
        threshold: Minimum similarity score. Uses config default if None.
        mode: One of ``"semantic"``, ``"keyword"``, ``"regex"``, ``"hybrid"``.
        full_section: If True, expand results to full enclosing function/class.
        auto_index: If True, index automatically when no index exists.
        case_insensitive: For regex mode, whether to ignore case.

    Returns:
        List of SearchResult objects sorted by descending score.

    Raises:
        FileNotFoundError: If no vector index exists and auto_index is False.
    """
    project_root = project_root.resolve()
    config = load_config(project_root)
    index_dir = AppConfig.index_dir(project_root)

    top_k = top_k or config.search.top_k
    threshold = threshold if threshold is not None else config.search.similarity_threshold

    # Auto-index if needed
    if auto_index:
        _auto_index_if_needed(project_root, index_dir)

    store = _load_store(index_dir)
    if store.size == 0:
        return []

    # Dispatch to the appropriate search backend
    if mode == "keyword":
        results = _keyword_search(query, store, index_dir, top_k)
    elif mode == "regex":
        results = _regex_search(query, store, top_k, case_insensitive)
    elif mode == "hybrid":
        results = _hybrid_search(query, store, index_dir, config, top_k)
    else:
        results = _semantic_search(query, store, config, top_k, threshold)

    logger.info("Found %d results (mode=%s).", len(results), mode)

    # Full-section expansion
    if full_section and results:
        from semantic_code_intelligence.search.section_expander import expand_to_full_section
        results = expand_to_full_section(results, project_root, index_dir)

    # Record query history
    _record_history(index_dir, query, results)

    return results
