"""Configuration settings for Semantic Code Intelligence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# Default directories to ignore during scanning
DEFAULT_IGNORE_DIRS: set[str] = {
    ".git",
    "node_modules",
    "build",
    "dist",
    "venv",
    ".venv",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "egg-info",
    ".eggs",
    ".idea",
    ".vscode",
    "target",
    "bin",
    "obj",
}

# Default file extensions to index
DEFAULT_EXTENSIONS: set[str] = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rb",
    ".php",
    ".cs",
    ".swift",
    ".kt",
    ".scala",
    ".sh",
    ".bash",
    ".sql",
    ".r",
    ".lua",
    ".dart",
    ".ex",
    ".exs",
}

CONFIG_DIR_NAME = ".codexa"
CONFIG_FILE_NAME = "config.json"
INDEX_DIR_NAME = "index"


class EmbeddingConfig(BaseModel):
    """Configuration for the embedding engine."""

    model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformers model name for embedding generation.",
    )
    chunk_size: int = Field(
        default=512,
        description="Maximum number of characters per code chunk.",
    )
    chunk_overlap: int = Field(
        default=64,
        description="Number of overlapping characters between consecutive chunks.",
    )


class SearchConfig(BaseModel):
    """Configuration for the search engine."""

    top_k: int = Field(
        default=10,
        description="Number of top results to return from similarity search.",
    )
    similarity_threshold: float = Field(
        default=0.3,
        description="Minimum similarity score threshold for results.",
    )


class IndexConfig(BaseModel):
    """Configuration for the indexing system."""

    ignore_dirs: set[str] = Field(default_factory=lambda: DEFAULT_IGNORE_DIRS.copy())
    extensions: set[str] = Field(default_factory=lambda: DEFAULT_EXTENSIONS.copy())
    exclude_files: set[str] = Field(
        default_factory=set,
        description="Glob patterns for files to exclude from indexing.",
    )
    use_incremental: bool = Field(
        default=True,
        description="Enable incremental indexing using file hashes.",
    )


class LLMConfig(BaseModel):
    """Configuration for LLM provider integration."""

    provider: str = Field(
        default="mock",
        description="LLM provider name: 'openai', 'ollama', or 'mock'.",
    )
    model: str = Field(
        default="gpt-3.5-turbo",
        description="Model name to use with the provider.",
    )
    api_key: str = Field(
        default="",
        description="API key for remote providers (e.g. OpenAI).",
    )
    base_url: str = Field(
        default="",
        description="Custom base URL for the LLM API endpoint.",
    )
    temperature: float = Field(
        default=0.2,
        description="Sampling temperature for LLM responses.",
    )
    max_tokens: int = Field(
        default=2048,
        description="Maximum tokens for LLM response generation.",
    )
    cache_enabled: bool = Field(
        default=True,
        description="Enable LLM response caching.",
    )
    cache_ttl_hours: int = Field(
        default=24,
        description="Time-to-live for cached LLM responses in hours.",
    )
    cache_max_entries: int = Field(
        default=1000,
        description="Maximum number of cached LLM responses.",
    )
    rate_limit_rpm: int = Field(
        default=0,
        description="Max requests per minute (0 = unlimited).",
    )
    rate_limit_tpm: int = Field(
        default=0,
        description="Max tokens per minute (0 = unlimited).",
    )


class QualityConfig(BaseModel):
    """Configuration for code quality metrics and gate enforcement."""

    complexity_threshold: int = Field(
        default=10,
        description="Minimum cyclomatic complexity to flag.",
    )
    min_maintainability: float = Field(
        default=40.0,
        description="Minimum maintainability index for quality gates.",
    )
    max_issues: int = Field(
        default=20,
        description="Maximum allowed quality issues for gates.",
    )
    snapshot_on_index: bool = Field(
        default=False,
        description="Automatically save a quality snapshot on indexing.",
    )
    history_limit: int = Field(
        default=50,
        description="Maximum number of snapshots to retain.",
    )


class AppConfig(BaseModel):
    """Top-level application configuration."""

    project_root: str = Field(
        default=".",
        description="Root path of the project being indexed.",
    )
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    verbose: bool = Field(default=False, description="Enable verbose output.")

    @classmethod
    def config_dir(cls, project_root: str | Path) -> Path:
        """Return the .codexa config directory for a given project root."""
        return Path(project_root).resolve() / CONFIG_DIR_NAME

    @classmethod
    def config_path(cls, project_root: str | Path) -> Path:
        """Return the path to the config.json file."""
        return cls.config_dir(project_root) / CONFIG_FILE_NAME

    @classmethod
    def index_dir(cls, project_root: str | Path) -> Path:
        """Return the path to the index storage directory."""
        return cls.config_dir(project_root) / INDEX_DIR_NAME


def load_config(project_root: str | Path = ".") -> AppConfig:
    """Load configuration from the project's .codexa/config.json.

    Falls back to default configuration if the file doesn't exist.
    """
    config_path = AppConfig.config_path(project_root)
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return AppConfig.model_validate(data)
    return AppConfig(project_root=str(Path(project_root).resolve()))


def save_config(config: AppConfig, project_root: Optional[str | Path] = None) -> Path:
    """Save configuration to the project's .codexa/config.json.

    Creates the config directory if it doesn't exist.
    Returns the path to the saved config file.
    """
    root = project_root or config.project_root
    config_dir = AppConfig.config_dir(root)
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = AppConfig.config_path(root)
    config_path.write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return config_path


def init_project(project_root: str | Path = ".") -> tuple[AppConfig, Path]:
    """Initialize a new project: create config dir, index dir, and default config.

    Returns the config object and the path to the config file.
    """
    root = Path(project_root).resolve()
    config = AppConfig(project_root=str(root))

    # Create directories
    config_dir = AppConfig.config_dir(root)
    config_dir.mkdir(parents=True, exist_ok=True)
    index_dir = AppConfig.index_dir(root)
    index_dir.mkdir(parents=True, exist_ok=True)

    # Save default config
    config_path = save_config(config, root)

    return config, config_path
