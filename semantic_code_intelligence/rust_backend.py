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
_HNSW_AVAILABLE = False
_AST_CHUNKER_AVAILABLE = False
_ONNX_AVAILABLE = False
_TANTIVY_AVAILABLE = False

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

    # HNSW (optional — may fail if instant-distance wasn't linked)
    try:
        from codexa_core import HnswVectorStore  # type: ignore[import-untyped]

        _HNSW_AVAILABLE = True
        logger.debug("HNSW vector store available.")
    except ImportError:
        HnswVectorStore = None  # type: ignore[assignment,misc]

    # AST chunker (optional — requires tree-sitter grammars)
    try:
        from codexa_core import AstChunker  # type: ignore[import-untyped]

        _AST_CHUNKER_AVAILABLE = True
        logger.debug("AST chunker available.")
    except ImportError:
        AstChunker = None  # type: ignore[assignment,misc]

    # ONNX embedder (optional — requires --features onnx)
    try:
        from codexa_core import OnnxEmbedder  # type: ignore[import-untyped]

        _ONNX_AVAILABLE = True
        logger.debug("ONNX embedder available.")
    except ImportError:
        OnnxEmbedder = None  # type: ignore[assignment,misc]

    # Tantivy full-text search (optional — requires --features tantivy-backend)
    try:
        from codexa_core import TantivyIndex  # type: ignore[import-untyped]

        _TANTIVY_AVAILABLE = True
        logger.debug("Tantivy full-text search available.")
    except ImportError:
        TantivyIndex = None  # type: ignore[assignment,misc]

except ImportError:
    logger.debug("Rust backend not available — using Python fallback.")
    HnswVectorStore = None  # type: ignore[assignment,misc]
    AstChunker = None  # type: ignore[assignment,misc]
    OnnxEmbedder = None  # type: ignore[assignment,misc]
    TantivyIndex = None  # type: ignore[assignment,misc]


def use_rust() -> bool:
    """Return True if the Rust native backend is available."""
    return _RUST_AVAILABLE


def use_hnsw() -> bool:
    """Return True if the HNSW vector store is available."""
    return _HNSW_AVAILABLE


def use_ast_chunker() -> bool:
    """Return True if the AST-aware chunker is available."""
    return _AST_CHUNKER_AVAILABLE


def use_onnx() -> bool:
    """Return True if the ONNX embedder is available."""
    return _ONNX_AVAILABLE


def use_tantivy() -> bool:
    """Return True if the Tantivy full-text search engine is available."""
    return _TANTIVY_AVAILABLE


def get_backend_name() -> str:
    """Return the active backend name for diagnostics."""
    return "rust (codexa_core)" if _RUST_AVAILABLE else "python"


# ---------------------------------------------------------------------------
# Public re-exports (only available when Rust is present)
# ---------------------------------------------------------------------------

__all__ = [
    "use_rust",
    "use_hnsw",
    "use_ast_chunker",
    "use_onnx",
    "use_tantivy",
    "get_backend_name",
    "ChunkMeta",
    "RustBM25Index",
    "RustChunker",
    "RustScanner",
    "RustVectorStore",
    "HnswVectorStore",
    "AstChunker",
    "OnnxEmbedder",
    "TantivyIndex",
    "ScannedFileResult",
    "reciprocal_rank_fusion_rs",
]
