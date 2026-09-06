"""Tests for the embedding generator."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from semantic_code_intelligence.embeddings.generator import (
    _model_cache,
    generate_embeddings,
    get_embedding_dimension,
    get_model,
)


class TestGetModel:
    """Tests for model loading."""

    def test_jina_model_uses_supported_attention_implementation(self, monkeypatch: pytest.MonkeyPatch):
        calls: list[dict] = []

        class FakeSentenceTransformer:
            def __init__(self, model_name: str, **kwargs):
                calls.append({"model_name": model_name, **kwargs})

        monkeypatch.setitem(
            sys.modules,
            "sentence_transformers",
            SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
        )
        monkeypatch.setattr(
            "semantic_code_intelligence.embeddings.generator._model_cached_locally",
            lambda model_name: False,
        )
        monkeypatch.setattr(
            "semantic_code_intelligence.embeddings.generator._show_download_banner",
            lambda model_name: None,
        )
        monkeypatch.setattr(
            "semantic_code_intelligence.embeddings.generator._onnx_available",
            lambda: False,
        )
        _model_cache.clear()

        get_model("jinaai/jina-embeddings-v2-base-code", backend="torch")

        assert calls == [
            {
                "model_name": "jinaai/jina-embeddings-v2-base-code",
                "model_kwargs": {"attn_implementation": "eager"},
                "trust_remote_code": True,
            }
        ]

    def test_loads_model(self):
        model = get_model("all-MiniLM-L6-v2")
        assert model is not None

    def test_model_cached(self):
        m1 = get_model("all-MiniLM-L6-v2")
        m2 = get_model("all-MiniLM-L6-v2")
        assert m1 is m2


class TestGenerateEmbeddings:
    """Tests for embedding generation."""

    def test_returns_numpy_array(self):
        emb = generate_embeddings(["hello world"])
        assert isinstance(emb, np.ndarray)

    def test_correct_shape(self):
        texts = ["hello", "world", "foo"]
        emb = generate_embeddings(texts)
        assert emb.shape[0] == 3
        assert emb.shape[1] > 0

    def test_empty_input(self):
        emb = generate_embeddings([])
        assert emb.shape == (0, 0)

    def test_embeddings_normalized(self):
        emb = generate_embeddings(["test string"])
        norm = np.linalg.norm(emb[0])
        assert abs(norm - 1.0) < 0.01

    def test_similar_texts_close(self):
        emb = generate_embeddings([
            "def authenticate_user(username, password):",
            "def verify_user_credentials(user, pwd):",
            "import random; x = random.randint(0, 100)",
        ])
        # Cosine similarity (already normalized, so dot product)
        sim_related = np.dot(emb[0], emb[1])
        sim_unrelated = np.dot(emb[0], emb[2])
        assert sim_related > sim_unrelated


class TestGetEmbeddingDimension:
    """Tests for embedding dimension retrieval."""

    def test_returns_positive_int(self):
        dim = get_embedding_dimension()
        assert isinstance(dim, int)
        assert dim > 0

    def test_matches_actual_embedding(self):
        dim = get_embedding_dimension()
        emb = generate_embeddings(["test"])
        assert emb.shape[1] == dim
