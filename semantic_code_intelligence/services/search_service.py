"""Search service — handles semantic search queries against the vector index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.embeddings.generator import generate_embeddings
from semantic_code_intelligence.storage.vector_store import ChunkMetadata, VectorStore
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("services.search")


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

    def to_dict(self) -> dict:
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


def search_codebase(
    query: str,
    project_root: Path,
    top_k: int | None = None,
    threshold: float | None = None,
) -> list[SearchResult]:
    """Perform semantic search against the indexed codebase.

    Args:
        query: Natural language search query.
        project_root: Root directory of the project.
        top_k: Number of top results to return. Uses config default if None.
        threshold: Minimum similarity score. Uses config default if None.

    Returns:
        List of SearchResult objects sorted by descending similarity.

    Raises:
        FileNotFoundError: If no vector index exists.
    """
    project_root = project_root.resolve()
    config = load_config(project_root)
    index_dir = AppConfig.index_dir(project_root)

    top_k = top_k or config.search.top_k
    threshold = threshold if threshold is not None else config.search.similarity_threshold

    # Load the vector store
    store = VectorStore.load(index_dir)
    logger.info("Loaded vector store with %d vectors.", store.size)

    if store.size == 0:
        return []

    # Generate query embedding
    logger.debug("Generating embedding for query: %s", query)
    query_embedding = generate_embeddings(
        [query],
        model_name=config.embedding.model_name,
    )[0]

    # Search
    raw_results = store.search(query_embedding, top_k=top_k)

    # Filter by threshold and build results
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

    logger.info("Found %d results above threshold %.2f.", len(results), threshold)
    return results
