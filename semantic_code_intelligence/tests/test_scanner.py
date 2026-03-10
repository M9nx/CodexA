"""Tests for the repository scanner."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantic_code_intelligence.indexing.scanner import (
    ScannedFile,
    compute_file_hash,
    scan_repository,
    should_ignore,
)
from semantic_code_intelligence.config.settings import IndexConfig


class TestComputeFileHash:
    """Tests for file hashing."""

    def test_hash_returns_hex_string(self, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("hello world", encoding="utf-8")
        h = compute_file_hash(f)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_same_content_same_hash(self, tmp_path: Path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("same content", encoding="utf-8")
        f2.write_text("same content", encoding="utf-8")
        assert compute_file_hash(f1) == compute_file_hash(f2)

    def test_different_content_different_hash(self, tmp_path: Path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("content A", encoding="utf-8")
        f2.write_text("content B", encoding="utf-8")
        assert compute_file_hash(f1) != compute_file_hash(f2)


class TestShouldIgnore:
    """Tests for directory ignore logic."""

    def test_ignore_git_dir(self, tmp_path: Path):
        p = tmp_path / ".git" / "config"
        assert should_ignore(p, tmp_path, {".git"}) is True

    def test_ignore_node_modules(self, tmp_path: Path):
        p = tmp_path / "node_modules" / "pkg" / "index.js"
        assert should_ignore(p, tmp_path, {"node_modules"}) is True

    def test_allow_normal_file(self, tmp_path: Path):
        p = tmp_path / "src" / "main.py"
        assert should_ignore(p, tmp_path, {".git"}) is False

    def test_nested_ignored_dir(self, tmp_path: Path):
        p = tmp_path / "src" / "__pycache__" / "mod.cpython-312.pyc"
        assert should_ignore(p, tmp_path, {"__pycache__"}) is True


class TestScanRepository:
    """Tests for repository scanning."""

    def test_empty_directory(self, tmp_path: Path):
        result = scan_repository(tmp_path)
        assert result == []

    def test_finds_python_files(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
        (tmp_path / "utils.py").write_text("x = 1", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert len(result) == 2

    def test_ignores_non_code_files(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("x = 1", encoding="utf-8")
        (tmp_path / "readme.md").write_text("# Readme", encoding="utf-8")
        (tmp_path / "data.csv").write_text("a,b,c", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert len(result) == 1
        assert result[0].extension == ".py"

    def test_ignores_excluded_dirs(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("x = 1", encoding="utf-8")
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "lib.py").write_text("y = 2", encoding="utf-8")
        result = scan_repository(tmp_path)
        assert len(result) == 1

    def test_scanned_file_metadata(self, tmp_path: Path):
        content = "def hello(): pass"
        (tmp_path / "test.py").write_text(content, encoding="utf-8")
        result = scan_repository(tmp_path)
        assert len(result) == 1
        sf = result[0]
        assert sf.extension == ".py"
        assert sf.relative_path == "test.py"
        assert sf.size_bytes > 0
        assert len(sf.content_hash) == 64

    def test_finds_multiple_languages(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("x = 1", encoding="utf-8")
        (tmp_path / "app.js").write_text("let x = 1;", encoding="utf-8")
        (tmp_path / "Main.java").write_text("class Main {}", encoding="utf-8")
        result = scan_repository(tmp_path)
        extensions = {sf.extension for sf in result}
        assert extensions == {".py", ".js", ".java"}

    def test_custom_config(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("x = 1", encoding="utf-8")
        (tmp_path / "app.js").write_text("let x = 1;", encoding="utf-8")
        config = IndexConfig(extensions={".py"}, ignore_dirs=set())
        result = scan_repository(tmp_path, config)
        assert len(result) == 1
        assert result[0].extension == ".py"

    def test_exclude_files_patterns(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("x = 1", encoding="utf-8")
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "token.py").write_text("SECRET = 'x'", encoding="utf-8")
        config = IndexConfig(ignore_dirs=set(), exclude_files={"secrets/*"})
        result = scan_repository(tmp_path, config)
        paths = [scanned.relative_path for scanned in result]
        assert paths == ["main.py"]

    def test_results_sorted(self, tmp_path: Path):
        (tmp_path / "z.py").write_text("z", encoding="utf-8")
        (tmp_path / "a.py").write_text("a", encoding="utf-8")
        (tmp_path / "m.py").write_text("m", encoding="utf-8")
        result = scan_repository(tmp_path)
        names = [sf.relative_path for sf in result]
        assert names == sorted(names)
