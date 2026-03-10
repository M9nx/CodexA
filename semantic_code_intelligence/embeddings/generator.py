"""Embedding generator — converts code chunks into vector embeddings.

Supports two backends:
- **sentence-transformers** (default): PyTorch-based, full-featured.
- **onnx**: Lightweight ONNX Runtime backend via ``optimum`` — lower
  memory (~50% less) and often faster inference on CPU.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any

import numpy as np

from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
from semantic_code_intelligence.utils.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger("embeddings")

# Module-level cache for loaded model instances
_model_cache: dict[str, "SentenceTransformer"] = {}
_MIN_TORCH_RAM_BYTES = 2 * 1024 * 1024 * 1024


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


def _model_cached_locally(model_name: str) -> bool:
    """Check if a HuggingFace model is already downloaded to the local cache.

    Looks in the standard ``HF_HOME`` / ``TRANSFORMERS_CACHE`` directory
    for a snapshot of the model so we can skip network calls when loading.
    """
    try:
        from huggingface_hub import try_to_load_from_cache
        # Check for key model file in the cache
        result = try_to_load_from_cache(model_name, "config.json")
        return isinstance(result, str)  # str path means it's cached
    except Exception:
        # Also check via the default HF cache directory structure
        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        hub_dir = hf_home / "hub"
        if not hub_dir.exists():
            return False
        # HF stores models as models--org--name
        model_dir_name = "models--" + model_name.replace("/", "--")
        model_dir = hub_dir / model_dir_name
        return model_dir.exists() and any(model_dir.rglob("config.json"))


def _get_available_memory_bytes() -> int | None:
    """Return approximate available system memory, if detectable."""
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemAvailable:"):
                        parts = line.split()
                        return int(parts[1]) * 1024
        except OSError:
            return None

    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullAvailPhys)
        except Exception:
            return None

    return None


def _check_memory_requirements(use_onnx: bool) -> None:
    """Warn on low-memory systems when using the torch backend."""
    if use_onnx:
        return

    available_memory = _get_available_memory_bytes()
    if available_memory is None or available_memory >= _MIN_TORCH_RAM_BYTES:
        return

    available_gb = available_memory / (1024 * 1024 * 1024)
    required_gb = _MIN_TORCH_RAM_BYTES / (1024 * 1024 * 1024)
    logger.warning(
        "Low available RAM detected for the PyTorch embedding backend "
        "(%.1f GB available, about %.0f GB recommended). If indexing fails, "
        "prefer the ONNX backend or a machine with more memory.",
        available_gb,
        required_gb,
    )


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

        # Suppress noisy HuggingFace Hub HTTP logs when model is cached
        local_only = _model_cached_locally(model_name)
        if local_only:
            logger.debug("Model %s found in local cache — skipping network checks.", model_name)
        # Quieten HF/transformers loggers that spam HTTP HEAD requests
        for noisy_logger in ("huggingface_hub", "transformers", "sentence_transformers"):
            logging.getLogger(noisy_logger).setLevel(logging.WARNING)

        use_onnx = False
        if backend == "onnx":
            if _onnx_available():
                use_onnx = True
            else:
                logger.warning("ONNX requested but optimum/onnxruntime not installed; falling back to PyTorch.")
        elif backend == "auto" and _onnx_available():
            use_onnx = True

        _check_memory_requirements(use_onnx)

        logger.info("Loading embedding model: %s (backend=%s)", model_name, "onnx" if use_onnx else "torch")

        load_kwargs: dict[str, Any] = {}
        if local_only:
            load_kwargs["local_files_only"] = True

        if use_onnx:
            try:
                _model_cache[cache_key] = SentenceTransformer(model_name, backend="onnx", **load_kwargs)
                logger.info("Model loaded with ONNX backend.")
                return _model_cache[cache_key]
            except Exception:
                logger.warning("ONNX load failed; falling back to PyTorch.")

        try:
            _model_cache[cache_key] = SentenceTransformer(model_name, **load_kwargs)
        except OSError:
            if local_only:
                # Cache may be corrupted — retry with network access
                logger.warning("Local cache load failed; re-downloading model.")
                _model_cache[cache_key] = SentenceTransformer(model_name)
            else:
                raise
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower():
                raise MemoryError(
                    "Embedding model loading ran out of memory. Try the ONNX backend or use a machine with at least 2 GB of available RAM."
                ) from exc
            raise
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
