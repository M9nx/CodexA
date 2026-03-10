"""Embedding generator — converts code chunks into vector embeddings.

Supports two backends:
- **sentence-transformers** (default): PyTorch-based, full-featured.
- **onnx**: Lightweight ONNX Runtime backend via ``optimum`` — lower
  memory (~50% less) and often faster inference on CPU.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
from semantic_code_intelligence.utils.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger("embeddings")

# Module-level cache for loaded model instances
_model_cache: dict[str, "SentenceTransformer"] = {}


def _configure_hf_token() -> None:
    """Set HF_TOKEN from common env vars if not already set.

    Checks ``HF_TOKEN``, ``HUGGING_FACE_HUB_TOKEN``, and
    ``HUGGINGFACE_TOKEN`` so the user only needs to export one.
    """
    if os.environ.get("HF_TOKEN"):
        return
    for var in ("HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        value = os.environ.get(var)
        if value:
            os.environ["HF_TOKEN"] = value
            return


def _onnx_available() -> bool:
    """Check if the ONNX Runtime backend is available."""
    try:
        import optimum  # noqa: F401
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def get_model(
    model_name: str = "all-MiniLM-L6-v2",
    backend: str = "auto",
) -> "SentenceTransformer":
    """Load and cache a sentence-transformers model.

    Args:
        model_name: Name of the model to load (full HF name or alias).
        backend: ``"auto"`` (ONNX if available, else PyTorch),
                 ``"onnx"``, or ``"torch"``.

    Returns:
        A SentenceTransformer model instance.
    """
    model_name = resolve_model_name(model_name)
    cache_key = f"{model_name}:{backend}"

    if cache_key not in _model_cache:
        _configure_hf_token()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embeddings. "
                "Install it with: pip install codexa[ml]"
            ) from None

        use_onnx = False
        if backend == "onnx":
            if _onnx_available():
                use_onnx = True
            else:
                logger.warning("ONNX requested but optimum/onnxruntime not installed; falling back to PyTorch.")
        elif backend == "auto" and _onnx_available():
            use_onnx = True

        logger.info("Loading embedding model: %s (backend=%s)", model_name, "onnx" if use_onnx else "torch")

        if use_onnx:
            try:
                _model_cache[cache_key] = SentenceTransformer(model_name, backend="onnx")
                logger.info("Model loaded with ONNX backend.")
                return _model_cache[cache_key]
            except Exception:
                logger.warning("ONNX load failed; falling back to PyTorch.")

        _model_cache[cache_key] = SentenceTransformer(model_name)
        logger.info("Model loaded successfully (PyTorch).")

    return _model_cache[cache_key]


def generate_embeddings(
    texts: list[str],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
    show_progress: bool = False,
    backend: str = "auto",
) -> np.ndarray:
    """Generate vector embeddings for a list of text strings.

    Args:
        texts: List of code/text strings to embed.
        model_name: Name of the sentence-transformers model (or alias).
        batch_size: Batch size for encoding.
        show_progress: Whether to show a progress bar.
        backend: ``"auto"``, ``"onnx"``, or ``"torch"``.

    Returns:
        NumPy array of shape (len(texts), embedding_dim).
    """
    if not texts:
        return np.array([], dtype=np.float32).reshape(0, 0)

    model = get_model(model_name, backend=backend)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings.astype(np.float32)


def get_embedding_dimension(
    model_name: str = "all-MiniLM-L6-v2",
    backend: str = "auto",
) -> int:
    """Return the dimensionality of embeddings produced by the given model.

    Args:
        model_name: Name of the sentence-transformers model (or alias).
        backend: ``"auto"``, ``"onnx"``, or ``"torch"``.

    Returns:
        Integer dimension of the embedding vectors.
    """
    model = get_model(model_name, backend=backend)
    dim = model.get_sentence_embedding_dimension()
    if dim is None:
        raise RuntimeError(f"Model {model_name!r} returned None for embedding dimension")
    return dim
