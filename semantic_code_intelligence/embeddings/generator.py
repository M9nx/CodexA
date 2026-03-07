"""Embedding generator — converts code chunks into vector embeddings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from semantic_code_intelligence.utils.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger("embeddings")

# Module-level cache for the model instance
_model_cache: dict[str, "SentenceTransformer"] = {}


def get_model(model_name: str = "all-MiniLM-L6-v2") -> "SentenceTransformer":
    """Load and cache a sentence-transformers model.

    Args:
        model_name: Name of the model to load.

    Returns:
        A SentenceTransformer model instance.
    """
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", model_name)
        _model_cache[model_name] = SentenceTransformer(model_name)
        logger.info("Model loaded successfully.")
    return _model_cache[model_name]


def generate_embeddings(
    texts: list[str],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
    show_progress: bool = False,
) -> np.ndarray:
    """Generate vector embeddings for a list of text strings.

    Args:
        texts: List of code/text strings to embed.
        model_name: Name of the sentence-transformers model.
        batch_size: Batch size for encoding.
        show_progress: Whether to show a progress bar.

    Returns:
        NumPy array of shape (len(texts), embedding_dim).
    """
    if not texts:
        return np.array([], dtype=np.float32).reshape(0, 0)

    model = get_model(model_name)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings.astype(np.float32)


def get_embedding_dimension(model_name: str = "all-MiniLM-L6-v2") -> int:
    """Return the dimensionality of embeddings produced by the given model.

    Args:
        model_name: Name of the sentence-transformers model.

    Returns:
        Integer dimension of the embedding vectors.
    """
    model = get_model(model_name)
    return model.get_sentence_embedding_dimension()
