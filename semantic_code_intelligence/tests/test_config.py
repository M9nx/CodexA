"""Tests for config/settings module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from semantic_code_intelligence.config.settings import (
    AppConfig,
    DEFAULT_EXTENSIONS,
    DEFAULT_IGNORE_DIRS,
    EmbeddingConfig,
    IndexConfig,
    SearchConfig,
    init_project,
    load_config,
    save_config,
)


class TestDefaultConfigs:
    """Tests for default configuration values."""

    def test_embedding_config_defaults(self):
        cfg = EmbeddingConfig()
        assert cfg.model_name == "all-MiniLM-L6-v2"
        assert cfg.chunk_size == 512
        assert cfg.chunk_overlap == 64

    def test_search_config_defaults(self):
        cfg = SearchConfig()
        assert cfg.top_k == 10
        assert cfg.similarity_threshold == 0.3

    def test_index_config_defaults(self):
        cfg = IndexConfig()
        assert cfg.ignore_dirs == DEFAULT_IGNORE_DIRS
        assert cfg.extensions == DEFAULT_EXTENSIONS
        assert cfg.use_incremental is True

    def test_app_config_defaults(self):
        cfg = AppConfig()
        assert cfg.verbose is False
        assert isinstance(cfg.embedding, EmbeddingConfig)
        assert isinstance(cfg.search, SearchConfig)
        assert isinstance(cfg.index, IndexConfig)


class TestConfigPaths:
    """Tests for config path resolution."""

    def test_config_dir(self, tmp_path: Path):
        config_dir = AppConfig.config_dir(tmp_path)
        assert config_dir == tmp_path / ".codex"

    def test_config_path(self, tmp_path: Path):
        config_path = AppConfig.config_path(tmp_path)
        assert config_path == tmp_path / ".codex" / "config.json"

    def test_index_dir(self, tmp_path: Path):
        index_dir = AppConfig.index_dir(tmp_path)
        assert index_dir == tmp_path / ".codex" / "index"


class TestLoadConfig:
    """Tests for loading config from disk."""

    def test_load_config_no_file_returns_defaults(self, tmp_path: Path):
        cfg = load_config(tmp_path)
        assert cfg.project_root == str(tmp_path.resolve())
        assert cfg.embedding.model_name == "all-MiniLM-L6-v2"

    def test_load_config_from_file(self, tmp_path: Path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        config_data = {
            "project_root": str(tmp_path),
            "verbose": True,
            "embedding": {"model_name": "custom-model", "chunk_size": 256},
            "search": {"top_k": 5},
            "index": {"use_incremental": False},
        }
        (config_dir / "config.json").write_text(
            json.dumps(config_data), encoding="utf-8"
        )

        cfg = load_config(tmp_path)
        assert cfg.verbose is True
        assert cfg.embedding.model_name == "custom-model"
        assert cfg.embedding.chunk_size == 256
        assert cfg.search.top_k == 5
        assert cfg.index.use_incremental is False


class TestSaveConfig:
    """Tests for saving config to disk."""

    def test_save_config_creates_file(self, tmp_path: Path):
        cfg = AppConfig(project_root=str(tmp_path))
        config_path = save_config(cfg, tmp_path)

        assert config_path.exists()
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["project_root"] == str(tmp_path)

    def test_save_config_creates_directory(self, tmp_path: Path):
        cfg = AppConfig(project_root=str(tmp_path))
        save_config(cfg, tmp_path)

        assert (tmp_path / ".codex").is_dir()


class TestInitProject:
    """Tests for project initialization."""

    def test_init_creates_config_dir(self, tmp_path: Path):
        config, config_path = init_project(tmp_path)
        assert (tmp_path / ".codex").is_dir()

    def test_init_creates_index_dir(self, tmp_path: Path):
        config, config_path = init_project(tmp_path)
        assert (tmp_path / ".codex" / "index").is_dir()

    def test_init_creates_config_file(self, tmp_path: Path):
        config, config_path = init_project(tmp_path)
        assert config_path.exists()
        assert config_path.name == "config.json"

    def test_init_returns_valid_config(self, tmp_path: Path):
        config, _ = init_project(tmp_path)
        assert config.project_root == str(tmp_path.resolve())
        assert isinstance(config, AppConfig)

    def test_init_config_is_loadable(self, tmp_path: Path):
        init_project(tmp_path)
        loaded = load_config(tmp_path)
        assert loaded.project_root == str(tmp_path.resolve())


class TestDefaultIgnoreDirs:
    """Tests for default ignore directories."""

    def test_common_dirs_ignored(self):
        for dirname in [".git", "node_modules", "build", "dist", "venv", "__pycache__"]:
            assert dirname in DEFAULT_IGNORE_DIRS

    def test_default_extensions_include_python(self):
        assert ".py" in DEFAULT_EXTENSIONS

    def test_default_extensions_include_common_languages(self):
        for ext in [".js", ".ts", ".java", ".go", ".rs", ".cpp"]:
            assert ext in DEFAULT_EXTENSIONS
