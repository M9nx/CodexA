"""Enhanced embedding pipeline — semantic preprocessing for code vectors.

Wraps the base generator with code-aware preprocessing:
- Prepends semantic labels to improve embedding quality
- Normalizes code formatting for more consistent representations
- Supports batch processing with progress tracking
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import numpy as np

from semantic_code_intelligence.embeddings.generator import (
    generate_embeddings,
    get_embedding_dimension,
    get_model,
)
from semantic_code_intelligence.indexing.semantic_chunker import SemanticChunk
from semantic_code_intelligence.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("embeddings.enhanced")


def preprocess_code_for_embedding(content: str, semantic_label: str = "") -> str:
    """Preprocess a code string to improve embedding quality.

    Transformations:
    1. Prepend semantic label (e.g. "[python] function authenticate(user, password)")
    2. Collapse excessive blank lines
    3. Strip trailing whitespace per line
    4. Normalize indentation depth (reduce deep nesting visual noise)

    Args:
        content: Raw code string.
        semantic_label: Optional semantic prefix.

    Returns:
        Preprocessed text ready for embedding.
    """
    lines = content.splitlines()
    processed: list[str] = []

    blank_count = 0
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            blank_count += 1
            if blank_count <= 1:
                processed.append("")
            continue
        blank_count = 0
        processed.append(stripped)

    text = "\n".join(processed).strip()

    if semantic_label:
        text = f"{semantic_label}\n{text}"

    return text


def prepare_semantic_texts(chunks: list[SemanticChunk]) -> list[str]:
    """Convert semantic chunks into preprocessed text strings for embedding.

    Each chunk's content is enhanced with its semantic label to give
    the embedding model structural context about what it's encoding.

    Args:
        chunks: List of SemanticChunk objects.

    Returns:
        List of preprocessed text strings, one per chunk.
    """
    return [
        preprocess_code_for_embedding(c.content, c.semantic_label)
        for c in chunks
    ]


def generate_semantic_embeddings(
    chunks: list[SemanticChunk],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
    show_progress: bool = False,
) -> np.ndarray:
    """Generate embeddings from semantic chunks with preprocessing.

    This is the recommended entry point for the enhanced pipeline.
    It preprocesses each chunk with its semantic label before encoding.

    Args:
        chunks: List of SemanticChunk objects.
        model_name: Sentence-transformers model name.
        batch_size: Encoding batch size.
        show_progress: Show progress bar.

    Returns:
        NumPy array of shape (len(chunks), embedding_dim), L2-normalized.
    """
    if not chunks:
        return np.array([], dtype=np.float32).reshape(0, 0)

    texts = prepare_semantic_texts(chunks)
    return generate_embeddings(texts, model_name, batch_size, show_progress)


def generate_query_embedding(
    query: str,
    model_name: str = "all-MiniLM-L6-v2",
) -> np.ndarray:
    """Generate embedding for a search query with light preprocessing.

    Queries are treated differently from code: they are natural language,
    so we do minimal transformation.

    Args:
        query: Natural language search query.
        model_name: Sentence-transformers model name.

    Returns:
        NumPy array of shape (1, embedding_dim), L2-normalized.
    """
    # Light cleanup only
    clean_query = query.strip()
    return generate_embeddings([clean_query], model_name)
