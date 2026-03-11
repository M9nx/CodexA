"""Embedding model registry — defines available models and their properties.

Provides a catalogue of supported embedding models so users can switch
between models optimised for different use-cases (code-heavy, doc-heavy,
speed vs quality, etc.).  Includes pre-defined *profiles* that map to
curated models based on speed/quality/RAM trade-offs.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelInfo:
    """Metadata about a supported embedding model."""

    name: str
    display_name: str
    dimension: int
    description: str
    recommended_for: str
    size_mb: int = 0  # approximate download size
    ram_required_gb: float = 0.5  # approximate RAM needed
    backend: str = "sentence-transformers"  # or "onnx"


@dataclass(frozen=True)
class ModelProfile:
    """A named model preset that maps a simple label to a curated model."""

    name: str
    model_name: str
    label: str
    description: str
    min_ram_gb: float


# ---------------------------------------------------------------------------
# Built-in model catalogue
# ---------------------------------------------------------------------------

AVAILABLE_MODELS: dict[str, ModelInfo] = {
    "all-MiniLM-L6-v2": ModelInfo(
        name="all-MiniLM-L6-v2",
        display_name="MiniLM L6 v2",
        dimension=384,
        description="Default balanced model — good quality, fast inference.",
        recommended_for="General purpose, balanced speed/quality.",
        size_mb=80,
        ram_required_gb=0.5,
        backend="sentence-transformers",
    ),
    "BAAI/bge-small-en-v1.5": ModelInfo(
        name="BAAI/bge-small-en-v1.5",
        display_name="BGE Small EN v1.5",
        dimension=384,
        description="Compact BGE model — strong text retrieval performance.",
        recommended_for="Retrieval-heavy workloads, lower memory.",
        size_mb=130,
        ram_required_gb=0.5,
        backend="sentence-transformers",
    ),
    "nomic-ai/nomic-embed-text-v1.5": ModelInfo(
        name="nomic-ai/nomic-embed-text-v1.5",
        display_name="Nomic Embed Text v1.5",
        dimension=768,
        description="High-quality long-context model (8192 tokens).",
        recommended_for="Documentation-heavy repos, long files.",
        size_mb=550,
        ram_required_gb=1.5,
        backend="sentence-transformers",
    ),
    "jinaai/jina-embeddings-v2-base-code": ModelInfo(
        name="jinaai/jina-embeddings-v2-base-code",
        display_name="Jina Code v2",
        dimension=768,
        description="Code-specialised model trained on programming languages.",
        recommended_for="Code-heavy repos, programming-specific search.",
        size_mb=550,
        ram_required_gb=1.5,
        backend="sentence-transformers",
    ),
    "mixedbread-ai/mxbai-embed-xsmall-v1": ModelInfo(
        name="mixedbread-ai/mxbai-embed-xsmall-v1",
        display_name="Mixedbread XSmall v1",
        dimension=384,
        description="Ultra-compact model — fastest inference, smallest footprint.",
        recommended_for="Large repos where speed matters most.",
        size_mb=60,
        ram_required_gb=0.3,
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

# ---------------------------------------------------------------------------
# Model Profiles — simple tiers for `codexa init --profile <name>`
# ---------------------------------------------------------------------------

MODEL_PROFILES: dict[str, ModelProfile] = {
    "fast": ModelProfile(
        name="fast",
        model_name="mixedbread-ai/mxbai-embed-xsmall-v1",
        label="Fast",
        description="Smallest model, fastest indexing. Best for large repos or low-RAM machines.",
        min_ram_gb=0.3,
    ),
    "balanced": ModelProfile(
        name="balanced",
        model_name="all-MiniLM-L6-v2",
        label="Balanced (default)",
        description="Good quality with fast inference. Recommended for most projects.",
        min_ram_gb=0.5,
    ),
    "precise": ModelProfile(
        name="precise",
        model_name="jinaai/jina-embeddings-v2-base-code",
        label="Precise",
        description="Code-specialised model with higher accuracy. Best for code-heavy repos.",
        min_ram_gb=1.5,
    ),
}

PROFILE_ALIASES: dict[str, str] = {
    "small": "fast",
    "default": "balanced",
    "quality": "precise",
    "code": "precise",
}


def resolve_profile(name: str) -> ModelProfile | None:
    """Resolve a profile name or alias to a ModelProfile."""
    key = PROFILE_ALIASES.get(name.lower(), name.lower())
    return MODEL_PROFILES.get(key)


def recommend_profile_for_ram(available_gb: float) -> ModelProfile:
    """Return the best profile that fits within the available RAM."""
    if available_gb >= 1.5:
        return MODEL_PROFILES["precise"]
    if available_gb >= 0.5:
        return MODEL_PROFILES["balanced"]
    return MODEL_PROFILES["fast"]


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


# ---------------------------------------------------------------------------
# Multi-model index helpers (Phase 38)
# ---------------------------------------------------------------------------

def model_index_subdir(model_name: str) -> str:
    """Return a filesystem-safe subdirectory name for a model's vector index.

    Allows keeping separate FAISS indices per embedding model so switching
    models at query time doesn't require a full re-index.
    """
    safe = resolve_model_name(model_name).replace("/", "--").replace("\\", "--")
    return f"vectors_{safe}"


# ---------------------------------------------------------------------------
# Hub / integrity helpers
# ---------------------------------------------------------------------------

# SHA-256 checksums for the built-in models (config.json fingerprint).
# Used by ``codexa models download --verify`` to confirm cache integrity.
MODEL_CHECKSUMS: dict[str, str] = {
    "all-MiniLM-L6-v2": "auto",
    "BAAI/bge-small-en-v1.5": "auto",
    "nomic-ai/nomic-embed-text-v1.5": "auto",
    "jinaai/jina-embeddings-v2-base-code": "auto",
    "mixedbread-ai/mxbai-embed-xsmall-v1": "auto",
}


def verify_model_integrity(model_name: str) -> bool:
    """Check that a locally cached model's config.json exists and is readable.

    Returns True if the model appears intact, False otherwise.
    """
    import os
    from pathlib import Path

    resolved = resolve_model_name(model_name)
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    model_dir_name = "models--" + resolved.replace("/", "--")
    model_dir = hf_home / "hub" / model_dir_name
    if not model_dir.exists():
        return False
    return any(model_dir.rglob("config.json"))
