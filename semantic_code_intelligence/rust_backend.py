"""Rust backend bridge — provides unified Python interface to codexa_core.

When ``codexa_core`` (the Rust native module) is available, all search,
indexing, and scanning operations use the Rust implementation for
dramatically better performance.  When the Rust module is not installed,
the existing pure-Python implementations are used as a transparent
fallback.

Usage
-----
>>> from semantic_code_intelligence.rust_backend import use_rust, get_backend_name
>>> if use_rust():
...     from semantic_code_intelligence.rust_backend import RustVectorStore
"""

from __future__ import annotations

import logging

logger = logging.getLogger("codexa.rust_backend")

# ---------------------------------------------------------------------------
# Feature detection
# ---------------------------------------------------------------------------

_RUST_AVAILABLE = False

try:
    from codexa_core import (  # type: ignore[import-untyped]
        ChunkMeta,
        RustBM25Index,
        RustChunker,
        RustScanner,
        RustVectorStore,
        ScannedFileResult,
        reciprocal_rank_fusion_rs,
    )

    _RUST_AVAILABLE = True
    logger.debug("Rust backend (codexa_core) loaded successfully.")
except ImportError:
    logger.debug("Rust backend not available — using Python fallback.")


def use_rust() -> bool:
    """Return True if the Rust native backend is available."""
    return _RUST_AVAILABLE


def get_backend_name() -> str:
    """Return the active backend name for diagnostics."""
    return "rust (codexa_core)" if _RUST_AVAILABLE else "python"


# ---------------------------------------------------------------------------
# Public re-exports (only available when Rust is present)
# ---------------------------------------------------------------------------

__all__ = [
    "use_rust",
    "get_backend_name",
    "ChunkMeta",
    "RustBM25Index",
    "RustChunker",
    "RustScanner",
    "RustVectorStore",
    "ScannedFileResult",
    "reciprocal_rank_fusion_rs",
]
