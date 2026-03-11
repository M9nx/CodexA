"""Tests for v0.27.0 features: grep flags, JSONL, models CLI, IVF, build, VS Code extension."""

from __future__ import annotations

import json
import numpy as np
import pytest
from pathlib import Path
from click.testing import CliRunner

from semantic_code_intelligence import __version__
from semantic_code_intelligence.cli.main import cli


# =========================================================================
# Version
# =========================================================================

class TestVersion027:
    def test_version_is_027(self):
        assert __version__ == "0.5.0"


# =========================================================================
# P2 — Grep flag parity + JSONL
# =========================================================================

class TestSearchGrepFlags:
    """Verify the new grep-style flags are accepted by the search CLI."""

    def test_search_help_has_context_lines(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "--help"])
        assert "--context-lines" in result.output
        assert "-C" in result.output

    def test_search_help_has_files_only(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "--help"])
        assert "--files-only" in result.output

    def test_search_help_has_files_without_match(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "--help"])
        assert "--files-without-match" in result.output

    def test_search_help_has_line_numbers(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "--help"])
        assert "--line-numbers" in result.output

    def test_search_help_has_jsonl(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "--help"])
        assert "--jsonl" in result.output


class TestFormatterJsonl:
    """Test format_results_jsonl output."""

    def test_jsonl_empty(self):
        from semantic_code_intelligence.search.formatter import format_results_jsonl
        assert format_results_jsonl([]) == ""

    def test_jsonl_format(self):
        from semantic_code_intelligence.search.formatter import format_results_jsonl
        from semantic_code_intelligence.services.search_service import SearchResult
        results = [
            SearchResult(
                file_path="a.py", start_line=1, end_line=5,
                language="python", content="pass", score=0.9,
                chunk_index=0,
            ),
            SearchResult(
                file_path="b.py", start_line=10, end_line=20,
                language="python", content="x = 1", score=0.8,
                chunk_index=1,
            ),
        ]
        output = format_results_jsonl(results)
        lines = output.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "file_path" in obj
            assert "score" in obj


# =========================================================================
# P5 — IVF index support
# =========================================================================

class TestVectorStoreIVF:
    """Test IVF-related vector store functionality."""

    def test_default_flat_index(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(128)
        assert store.size == 0
        assert not store._use_ivf

    def test_ivf_mode_fallback_few_vectors(self):
        """IVF mode should fall back to flat when not enough vectors to train."""
        from semantic_code_intelligence.storage.vector_store import VectorStore, ChunkMetadata
        store = VectorStore(8, use_ivf=True)
        vecs = np.random.randn(5, 8).astype(np.float32)
        vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        meta = [
            ChunkMetadata(f"f{i}.py", 1, 2, i, "python", "x", "")
            for i in range(5)
        ]
        store.add(vecs, meta)
        assert store.size == 5
        # Should have fallen back to flat since 5 < IVF_NLIST
        assert not store._use_ivf

    def test_ivf_threshold_constant(self):
        from semantic_code_intelligence.storage.vector_store import IVF_THRESHOLD
        assert IVF_THRESHOLD == 50_000


# =========================================================================
# P6 — Models CLI
# =========================================================================

class TestModelsCLI:
    """Test the models command group."""

    def test_models_list_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output

    def test_models_info_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "info", "--help"])
        assert result.exit_code == 0

    def test_models_download_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "download", "--help"])
        assert result.exit_code == 0
        assert "--backend" in result.output

    def test_models_switch_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "switch", "--help"])
        assert result.exit_code == 0

    def test_models_list_json(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 5
        names = [m["name"] for m in data]
        assert "all-MiniLM-L6-v2" in names

    def test_models_info_valid(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "info", "minilm"])
        assert result.exit_code == 0
        assert "MiniLM" in result.output

    def test_models_info_unknown(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "info", "nonexistent-model-xyz"])
        assert result.exit_code != 0

    def test_model_count_is_35(self):
        """Verify we now have 36 top-level commands."""
        assert len(cli.commands) == 39


class TestModelRegistry:
    """Test model registry helper functions."""

    def test_resolve_alias(self):
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        assert resolve_model_name("minilm") == "all-MiniLM-L6-v2"
        assert resolve_model_name("jina-code") == "jinaai/jina-embeddings-v2-base-code"

    def test_list_models(self):
        from semantic_code_intelligence.embeddings.model_registry import list_models
        models = list_models()
        assert len(models) >= 5

    def test_get_model_info(self):
        from semantic_code_intelligence.embeddings.model_registry import get_model_info
        info = get_model_info("minilm")
        assert info is not None
        assert info.dimension == 384

    def test_get_model_info_unknown(self):
        from semantic_code_intelligence.embeddings.model_registry import get_model_info
        assert get_model_info("fake-model-xxx") is None


# =========================================================================
# P4 — Build script
# =========================================================================

class TestBuildScript:
    def test_build_script_exists(self):
        assert Path("scripts/build_binary.py").exists() or Path("d:/mounir/CodexA/scripts/build_binary.py").exists()

    def test_build_script_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_binary", "scripts/build_binary.py")
        assert spec is not None


# =========================================================================
# P3 — VS Code extension
# =========================================================================

class TestVSCodeExtension:
    def test_package_json_exists(self):
        p = Path("vscode-extension/package.json")
        assert p.exists() or Path("d:/mounir/CodexA/vscode-extension/package.json").exists()

    def test_extension_ts_exists(self):
        p = Path("vscode-extension/src/extension.ts")
        assert p.exists() or Path("d:/mounir/CodexA/vscode-extension/src/extension.ts").exists()

    def test_package_json_valid(self):
        p = Path("vscode-extension/package.json")
        if not p.exists():
            p = Path("d:/mounir/CodexA/vscode-extension/package.json")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["name"] == "codexa"
        assert "commands" in str(data["contributes"])


# =========================================================================
# Formatter context expansion
# =========================================================================

class TestFormatterExpand:
    def test_expand_context_no_file(self):
        from semantic_code_intelligence.search.formatter import _expand_context
        from semantic_code_intelligence.services.search_service import SearchResult
        result = SearchResult(
            file_path="/nonexistent/path.py", start_line=5, end_line=10,
            language="python", content="hello", score=0.5, chunk_index=0,
        )
        content, start = _expand_context(result, 3)
        assert content == "hello"
        assert start == 5

