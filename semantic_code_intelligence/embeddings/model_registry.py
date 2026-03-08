"""Embedding model registry — defines available models and their properties.

Provides a catalogue of supported embedding models so users can switch
between models optimised for different use-cases (code-heavy, doc-heavy,
speed vs quality, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    """Metadata about a supported embedding model."""

    name: str
    display_name: str
    dimension: int
    description: str
    recommended_for: str
    backend: str = "sentence-transformers"  # or "onnx"


# Built-in model catalogue — mirrors ck's 4 models plus extras
AVAILABLE_MODELS: dict[str, ModelInfo] = {
    "all-MiniLM-L6-v2": ModelInfo(
        name="all-MiniLM-L6-v2",
        display_name="MiniLM L6 v2",
        dimension=384,
        description="Default balanced model — good quality, fast inference.",
        recommended_for="General purpose, balanced speed/quality.",
        backend="sentence-transformers",
    ),
    "BAAI/bge-small-en-v1.5": ModelInfo(
        name="BAAI/bge-small-en-v1.5",
        display_name="BGE Small EN v1.5",
        dimension=384,
        description="Compact BGE model — strong text retrieval performance.",
        recommended_for="Retrieval-heavy workloads, lower memory.",
        backend="sentence-transformers",
    ),
    "nomic-ai/nomic-embed-text-v1.5": ModelInfo(
        name="nomic-ai/nomic-embed-text-v1.5",
        display_name="Nomic Embed Text v1.5",
        dimension=768,
        description="High-quality long-context model (8192 tokens).",
        recommended_for="Documentation-heavy repos, long files.",
        backend="sentence-transformers",
    ),
    "jinaai/jina-embeddings-v2-base-code": ModelInfo(
        name="jinaai/jina-embeddings-v2-base-code",
        display_name="Jina Code v2",
        dimension=768,
        description="Code-specialised model trained on programming languages.",
        recommended_for="Code-heavy repos, programming-specific search.",
        backend="sentence-transformers",
    ),
    "mixedbread-ai/mxbai-embed-xsmall-v1": ModelInfo(
        name="mixedbread-ai/mxbai-embed-xsmall-v1",
        display_name="Mixedbread XSmall v1",
        dimension=384,
        description="Ultra-compact model — fastest inference, smallest footprint.",
        recommended_for="Large repos where speed matters most.",
        backend="sentence-transformers",
    ),
}

# Shorthand aliases for CLI convenience
MODEL_ALIASES: dict[str, str] = {
    "minilm": "all-MiniLM-L6-v2",
    "bge-small": "BAAI/bge-small-en-v1.5",
    "nomic": "nomic-ai/nomic-embed-text-v1.5",
    "jina-code": "jinaai/jina-embeddings-v2-base-code",
    "mxbai-xsmall": "mixedbread-ai/mxbai-embed-xsmall-v1",
}

DEFAULT_MODEL = "all-MiniLM-L6-v2"


def resolve_model_name(name_or_alias: str) -> str:
    """Resolve a model name or alias to the full model identifier."""
    if name_or_alias in AVAILABLE_MODELS:
        return name_or_alias
    resolved = MODEL_ALIASES.get(name_or_alias.lower())
    if resolved:
        return resolved
    # Assume it's a custom HF model name
    return name_or_alias


def get_model_info(name_or_alias: str) -> ModelInfo | None:
    """Look up model info by name or alias. Returns None for unknown models."""
    resolved = resolve_model_name(name_or_alias)
    return AVAILABLE_MODELS.get(resolved)


def list_models() -> list[ModelInfo]:
    """Return all available models."""
    return list(AVAILABLE_MODELS.values())
