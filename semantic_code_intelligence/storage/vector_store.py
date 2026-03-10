"""Vector store — FAISS-based storage and retrieval of code embeddings.

Supports two index modes:
- **Flat** (default): Brute-force exact search — best for <50 k vectors.
- **IVF**: Inverted-file approximate search — faster for large repos (>50 k).
  Enabled automatically when the vector count crosses *IVF_THRESHOLD* or by
  passing ``use_ivf=True`` to the constructor.

When the Rust native backend (``codexa_core``) is available, the store
transparently delegates to ``RustVectorStore`` for faster search and I/O.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import faiss  # type: ignore[import-untyped]
except ImportError:
    faiss = None  # type: ignore[assignment]

import numpy as np

from semantic_code_intelligence.rust_backend import use_rust
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("storage")

# If the store has more vectors than this, it can benefit from IVF.
IVF_THRESHOLD = 50_000
IVF_NLIST = 100  # number of Voronoi cells
IVF_NPROBE = 10  # cells probed at search time


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

    When *use_ivf* is ``True`` (or the vector count exceeds *IVF_THRESHOLD*),
    the store transparently migrates to a ``faiss.IndexIVFFlat`` for faster
    approximate nearest-neighbour search.
    """

    def __init__(self, dimension: int, *, use_ivf: bool = False) -> None:
        if faiss is None:
            raise ImportError(
                "faiss-cpu is required for vector search. "
                "Install it with: pip install codexa[ml]"
            )
        self.dimension = dimension
        self._use_ivf = use_ivf
        self._rs_store = None  # cached Rust backend (populated lazily)
        if use_ivf:
            quantizer = faiss.IndexFlatIP(dimension)
            self.index = faiss.IndexIVFFlat(quantizer, dimension, IVF_NLIST, faiss.METRIC_INNER_PRODUCT)
            self.index.nprobe = IVF_NPROBE
            self._ivf_trained = False
        else:
            self.index = faiss.IndexFlatIP(dimension)
            self._ivf_trained = True  # flat doesn't need training
        self.metadata: list[ChunkMetadata] = []
        # Reverse index: file_path -> set of vector indices for O(1) lookup
        self._file_index: dict[str, set[int]] = defaultdict(set)

    @property
    def size(self) -> int:
        """Return the number of vectors stored."""
        return int(self.index.ntotal)

    def add(
        self,
        embeddings: np.ndarray,
        metadata_list: list[ChunkMetadata],
    ) -> None:
        """Add embeddings and their metadata to the store.

        If the store uses an IVF index that hasn't been trained yet, the first
        batch of vectors is used to train it.  If the store is in flat mode and
        the total count crosses *IVF_THRESHOLD*, it auto-upgrades to IVF.
        """
        if len(embeddings) != len(metadata_list):
            raise ValueError(
                f"Embedding count ({len(embeddings)}) != metadata count ({len(metadata_list)})"
            )
        if len(embeddings) == 0:
            return

        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

        # Train IVF index on first batch if needed
        if self._use_ivf and not self._ivf_trained:
            if len(embeddings) >= IVF_NLIST:
                self.index.train(embeddings)
                self._ivf_trained = True
            else:
                # Not enough vectors to train — fall back to flat temporarily
                logger.debug("Not enough vectors to train IVF (%d < %d), using flat.", len(embeddings), IVF_NLIST)
                self.index = faiss.IndexFlatIP(self.dimension)
                self._use_ivf = False
                self._ivf_trained = True

        # Update file index before adding
        base = len(self.metadata)
        for i, meta in enumerate(metadata_list):
            self._file_index[meta.file_path].add(base + i)

        self.index.add(embeddings)
        self.metadata.extend(metadata_list)

        # Auto-upgrade from flat to IVF when threshold is crossed
        if not self._use_ivf and self.size >= IVF_THRESHOLD:
            self._upgrade_to_ivf()

        # Rebuild cached Rust store for fast search
        self._sync_rust_store()

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
    ) -> list[tuple[ChunkMetadata, float]]:
        """Search for the most similar embeddings.

        When the Rust backend is available, delegates to the native
        inner-product implementation for better performance.

        Args:
            query_embedding: Query vector of shape (dimension,) or (1, dimension).
            top_k: Number of top results to return.

        Returns:
            List of (metadata, score) tuples, ordered by decreasing similarity.
        """
        if self.size == 0:
            return []

        # --- Rust fast path (uses cached RustVectorStore) ---
        if use_rust() and self._rs_store is not None:
            try:
                return self._rust_search(query_embedding, top_k)
            except Exception:
                logger.debug("Rust search failed, falling back to FAISS.")

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

    def _rust_search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
    ) -> list[tuple[ChunkMetadata, float]]:
        """Perform search via cached Rust backend."""
        q = np.ascontiguousarray(query_embedding.ravel(), dtype=np.float32)
        rust_results = self._rs_store.search(q, top_k)

        return [
            (
                ChunkMetadata(
                    file_path=cm.file_path,
                    start_line=cm.start_line,
                    end_line=cm.end_line,
                    chunk_index=cm.chunk_index,
                    language=cm.language,
                    content=cm.content,
                    content_hash=cm.content_hash,
                ),
                float(score),
            )
            for cm, score in rust_results
        ]

    def _sync_rust_store(self) -> None:
        """Rebuild the cached Rust store from current FAISS vectors + metadata."""
        if not use_rust():
            return
        try:
            from semantic_code_intelligence.rust_backend import (
                ChunkMeta,
                RustVectorStore,
            )
            n = self.size
            if n == 0:
                self._rs_store = None
                return
            dim = self.dimension
            rs = RustVectorStore(dim)
            all_vecs = np.vstack(
                [self.index.reconstruct(i).reshape(1, -1) for i in range(n)]
            ).astype(np.float32)
            rs_meta = [
                ChunkMeta(
                    m.file_path, m.start_line, m.end_line,
                    m.chunk_index, m.language, m.content, m.content_hash,
                )
                for m in self.metadata
            ]
            rs.add(all_vecs, rs_meta)
            self._rs_store = rs
        except Exception:
            self._rs_store = None

    def save(self, directory: Path) -> None:
        """Persist the vector store to disk.

        Saves the FAISS index and metadata as separate files.
        When the Rust backend is available, also writes ``vectors.bin``
        for future fast native loads.

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

        # Also save Rust-format vectors.bin for native backend
        if use_rust() and self.size > 0:
            try:
                from semantic_code_intelligence.rust_backend import (
                    ChunkMeta,
                    RustVectorStore,
                )
                dim = self.dimension
                rs = RustVectorStore(dim)
                all_vecs = np.vstack(
                    [self.index.reconstruct(i).reshape(1, -1) for i in range(self.size)]
                ).astype(np.float32)
                rs_meta = [
                    ChunkMeta(
                        m.file_path, m.start_line, m.end_line,
                        m.chunk_index, m.language, m.content, m.content_hash,
                    )
                    for m in self.metadata
                ]
                rs.add(all_vecs, rs_meta)
                rs.save(str(directory))
            except Exception:
                logger.debug("Failed to write Rust vectors.bin alongside FAISS index.")

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
        # Rebuild file index from loaded metadata
        for i, m in enumerate(metadata):
            store._file_index[m.file_path].add(i)
        logger.info("Loaded %d vectors from %s", store.size, directory)
        # Build Rust mirror for fast search
        store._sync_rust_store()
        return store

    def remove_by_file(self, file_path: str) -> int:
        """Remove all vectors whose metadata references *file_path*.

        Uses the file index for O(1) lookup and batch vector reconstruction.

        Args:
            file_path: The ``file_path`` field to match against.

        Returns:
            Number of vectors removed.
        """
        remove_set = self._file_index.get(file_path)
        if not remove_set:
            return 0

        removed = len(remove_set)
        keep_indices = [
            i for i in range(len(self.metadata)) if i not in remove_set
        ]

        if keep_indices:
            # Batch reconstruct all kept vectors at once (no Python loop)
            kept_vectors = np.empty(
                (len(keep_indices), self.dimension), dtype=np.float32,
            )
            for j, idx in enumerate(keep_indices):
                self.index.reconstruct(idx, kept_vectors[j])
            kept_meta = [self.metadata[i] for i in keep_indices]
        else:
            kept_vectors = np.empty((0, self.dimension), dtype=np.float32)
            kept_meta = []

        self.index.reset()
        if len(kept_vectors) > 0:
            self.index.add(np.ascontiguousarray(kept_vectors))
        self.metadata = kept_meta

        # Rebuild file index
        self._file_index.clear()
        for i, m in enumerate(self.metadata):
            self._file_index[m.file_path].add(i)

        logger.debug("Removed %d vectors for %s", removed, file_path)
        # Invalidate Rust cache (rebuilt lazily on next search or add)
        self._rs_store = None
        return removed

    def get_vectors_for_file(self, file_path: str) -> list[tuple[ChunkMetadata, np.ndarray]]:
        """Return metadata and vectors for all chunks belonging to a file.

        Used by incremental indexing to preserve vectors for unchanged chunks
        before removing the file's entries from the store.

        Returns:
            List of (metadata, vector) pairs.
        """
        indices = self._file_index.get(file_path)
        if not indices:
            return []
        result: list[tuple[ChunkMetadata, np.ndarray]] = []
        for idx in sorted(indices):
            vec = np.empty(self.dimension, dtype=np.float32)
            self.index.reconstruct(idx, vec)
            result.append((self.metadata[idx], vec))
        return result

    def clear(self) -> None:
        """Remove all vectors and metadata."""
        self.index.reset()
        self.metadata.clear()
        self._file_index.clear()
        self._rs_store = None

    # ------------------------------------------------------------------
    # IVF helpers
    # ------------------------------------------------------------------

    def _upgrade_to_ivf(self) -> None:
        """Migrate an in-memory flat index to IVF for faster search."""
        n = self.size
        if n < IVF_NLIST:
            return  # not enough vectors
        logger.info("Auto-upgrading index to IVF (%d vectors).", n)
        all_vecs = np.vstack(
            [self.index.reconstruct(i).reshape(1, -1) for i in range(n)]
        ).astype(np.float32)
        quantizer = faiss.IndexFlatIP(self.dimension)
        ivf = faiss.IndexIVFFlat(quantizer, self.dimension, IVF_NLIST, faiss.METRIC_INNER_PRODUCT)
        ivf.nprobe = IVF_NPROBE
        ivf.train(all_vecs)
        ivf.add(all_vecs)
        self.index = ivf
        self._use_ivf = True
        self._ivf_trained = True
