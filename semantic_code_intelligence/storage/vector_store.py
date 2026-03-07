"""Vector store — FAISS-based storage and retrieval of code embeddings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("storage")


@dataclass
class ChunkMetadata:
    """Metadata associated with a stored code chunk."""

    file_path: str
    start_line: int
    end_line: int
    chunk_index: int
    language: str
    content: str
    content_hash: str = ""


class VectorStore:
    """FAISS-backed vector store for code chunk embeddings.

    Maintains a FAISS index and parallel metadata list.
    Supports save/load to disk for persistence.
    """

    def __init__(self, dimension: int) -> None:
        """Initialize the vector store.

        Args:
            dimension: Dimensionality of the embedding vectors.
        """
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)  # Inner product (cosine for normalized vecs)
        self.metadata: list[ChunkMetadata] = []

    @property
    def size(self) -> int:
        """Return the number of vectors stored."""
        return self.index.ntotal

    def add(
        self,
        embeddings: np.ndarray,
        metadata_list: list[ChunkMetadata],
    ) -> None:
        """Add embeddings and their metadata to the store.

        Args:
            embeddings: NumPy array of shape (n, dimension).
            metadata_list: List of metadata, one per embedding.

        Raises:
            ValueError: If embeddings and metadata counts don't match.
        """
        if len(embeddings) != len(metadata_list):
            raise ValueError(
                f"Embedding count ({len(embeddings)}) != metadata count ({len(metadata_list)})"
            )
        if len(embeddings) == 0:
            return

        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
        self.index.add(embeddings)
        self.metadata.extend(metadata_list)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
    ) -> list[tuple[ChunkMetadata, float]]:
        """Search for the most similar embeddings.

        Args:
            query_embedding: Query vector of shape (dimension,) or (1, dimension).
            top_k: Number of top results to return.

        Returns:
            List of (metadata, score) tuples, ordered by decreasing similarity.
        """
        if self.size == 0:
            return []

        query = np.ascontiguousarray(
            query_embedding.reshape(1, -1), dtype=np.float32
        )
        k = min(top_k, self.size)
        scores, indices = self.index.search(query, k)

        results: list[tuple[ChunkMetadata, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            results.append((self.metadata[idx], float(score)))
        return results

    def save(self, directory: Path) -> None:
        """Persist the vector store to disk.

        Saves the FAISS index and metadata as separate files.

        Args:
            directory: Directory to save into.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        index_path = directory / "vectors.faiss"
        meta_path = directory / "metadata.json"

        faiss.write_index(self.index, str(index_path))

        meta_dicts = [asdict(m) for m in self.metadata]
        meta_path.write_text(
            json.dumps(meta_dicts, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved %d vectors to %s", self.size, directory)

    @classmethod
    def load(cls, directory: Path) -> "VectorStore":
        """Load a vector store from disk.

        Args:
            directory: Directory containing vectors.faiss and metadata.json.

        Returns:
            A populated VectorStore instance.

        Raises:
            FileNotFoundError: If the required files don't exist.
        """
        directory = Path(directory)
        index_path = directory / "vectors.faiss"
        meta_path = directory / "metadata.json"

        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"No vector store found in {directory}")

        index = faiss.read_index(str(index_path))
        dimension = index.d

        meta_dicts = json.loads(meta_path.read_text(encoding="utf-8"))
        metadata = [ChunkMetadata(**m) for m in meta_dicts]

        store = cls(dimension)
        store.index = index
        store.metadata = metadata
        logger.info("Loaded %d vectors from %s", store.size, directory)
        return store

    def clear(self) -> None:
        """Remove all vectors and metadata."""
        self.index.reset()
        self.metadata.clear()
