"""Tests for the vector store."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from semantic_code_intelligence.storage.vector_store import (
    ChunkMetadata,
    VectorStore,
)


def _make_metadata(n: int) -> list[ChunkMetadata]:
    """Create n dummy metadata entries."""
    return [
        ChunkMetadata(
            file_path=f"file_{i}.py",
            start_line=1,
            end_line=10,
            chunk_index=i,
            language="python",
            content=f"content_{i}",
        )
        for i in range(n)
    ]


def _random_embeddings(n: int, dim: int = 128) -> np.ndarray:
    """Create n random normalized embeddings."""
    vecs = np.random.randn(n, dim).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms


class TestVectorStore:
    """Tests for VectorStore operations."""

    def test_create_empty(self):
        store = VectorStore(128)
        assert store.size == 0
        assert store.dimension == 128

    def test_add_and_size(self):
        store = VectorStore(128)
        emb = _random_embeddings(5)
        meta = _make_metadata(5)
        store.add(emb, meta)
        assert store.size == 5

    def test_add_mismatched_raises(self):
        store = VectorStore(128)
        emb = _random_embeddings(3)
        meta = _make_metadata(5)
        with pytest.raises(ValueError):
            store.add(emb, meta)

    def test_add_empty(self):
        store = VectorStore(128)
        store.add(np.array([], dtype=np.float32).reshape(0, 128), [])
        assert store.size == 0

    def test_search_returns_results(self):
        store = VectorStore(128)
        emb = _random_embeddings(10)
        meta = _make_metadata(10)
        store.add(emb, meta)

        results = store.search(emb[0], top_k=3)
        assert len(results) == 3
        # First result should be the query itself (highest similarity)
        assert results[0][0].file_path == "file_0.py"
        assert results[0][1] > 0.99  # self-similarity ≈ 1.0

    def test_search_empty_store(self):
        store = VectorStore(128)
        query = _random_embeddings(1)[0]
        results = store.search(query, top_k=5)
        assert results == []

    def test_search_top_k_larger_than_store(self):
        store = VectorStore(128)
        emb = _random_embeddings(3)
        meta = _make_metadata(3)
        store.add(emb, meta)
        results = store.search(emb[0], top_k=100)
        assert len(results) == 3

    def test_search_scores_descending(self):
        store = VectorStore(128)
        emb = _random_embeddings(20)
        meta = _make_metadata(20)
        store.add(emb, meta)

        results = store.search(emb[0], top_k=10)
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestVectorStorePersistence:
    """Tests for save/load functionality."""

    def test_save_creates_files(self, tmp_path: Path):
        store = VectorStore(128)
        emb = _random_embeddings(5)
        meta = _make_metadata(5)
        store.add(emb, meta)
        store.save(tmp_path / "index")

        assert (tmp_path / "index" / "vectors.faiss").exists()
        assert (tmp_path / "index" / "metadata.json").exists()

    def test_load_roundtrip(self, tmp_path: Path):
        store = VectorStore(128)
        emb = _random_embeddings(5)
        meta = _make_metadata(5)
        store.add(emb, meta)
        store.save(tmp_path / "index")

        loaded = VectorStore.load(tmp_path / "index")
        assert loaded.size == 5
        assert loaded.dimension == 128
        assert len(loaded.metadata) == 5
        assert loaded.metadata[0].file_path == "file_0.py"

    def test_load_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            VectorStore.load(tmp_path / "nonexistent")

    def test_search_after_load(self, tmp_path: Path):
        store = VectorStore(128)
        emb = _random_embeddings(10)
        meta = _make_metadata(10)
        store.add(emb, meta)
        store.save(tmp_path / "index")

        loaded = VectorStore.load(tmp_path / "index")
        results = loaded.search(emb[0], top_k=3)
        assert len(results) == 3
        assert results[0][0].file_path == "file_0.py"

    def test_clear(self):
        store = VectorStore(128)
        emb = _random_embeddings(5)
        meta = _make_metadata(5)
        store.add(emb, meta)
        store.clear()
        assert store.size == 0
        assert store.metadata == []
