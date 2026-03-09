"""Comprehensive end-to-end tests — simulates a real end user working with CodexA.

Tests the entire user journey:
  codex --version → codex init → codex index → codex search (all modes/flags)
  → codex models (list/info/switch) → TUI helpers → VS Code extension
  → config lifecycle → vector store → formatter → build script → doctor
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from semantic_code_intelligence import __version__
from semantic_code_intelligence.cli.main import cli


def _extract_json(text: str) -> dict | list:
    """Extract the first valid JSON object/array from mixed CLI output.

    Rich console logging can contaminate stdout, so we scan for the first
    '{' or '[' that successfully parses.
    """
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return json.loads(text[i:])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON found in output: {text[:200]!r}")


# ── Reusable project root for tmp_path fixtures ──────────────────────────
SAMPLE_PY = textwrap.dedent("""\
    \"\"\"Sample module for end-to-end testing.\"\"\"

    def greet(name: str) -> str:
        \"\"\"Return a greeting string.\"\"\"
        return f"Hello, {name}!"

    def add(a: int, b: int) -> int:
        \"\"\"Add two numbers.\"\"\"
        return a + b

    class Calculator:
        \"\"\"A simple calculator.\"\"\"

        def multiply(self, x: int, y: int) -> int:
            return x * y

        def divide(self, x: float, y: float) -> float:
            if y == 0:
                raise ZeroDivisionError("Cannot divide by zero")
            return x / y
""")

SAMPLE_JS = textwrap.dedent("""\
    // sample.js — small JS file for testing
    function fibonacci(n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
    }

    module.exports = { fibonacci };
""")


@pytest.fixture()
def project(tmp_path: Path):
    """Create a minimal project directory with sample source files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "sample.py").write_text(SAMPLE_PY, encoding="utf-8")
    (src / "math_utils.py").write_text(
        textwrap.dedent("""\
            \"\"\"Math utilities.\"\"\"

            import math

            def circle_area(radius: float) -> float:
                return math.pi * radius ** 2

            def factorial(n: int) -> int:
                if n <= 1:
                    return 1
                return n * factorial(n - 1)
        """),
        encoding="utf-8",
    )
    (src / "app.js").write_text(SAMPLE_JS, encoding="utf-8")
    return tmp_path


# =========================================================================
# 1. Version & basic CLI
# =========================================================================

class TestCLIBasics:
    """Test basic CLI behaviour that every user hits first."""

    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "codex" in result.output.lower()

    def test_command_count(self):
        assert len(cli.commands) == 35

    def test_all_35_commands_registered(self):
        expected = {
            "init", "index", "search", "explain", "summary", "watch",
            "deps", "ask", "review", "refactor", "suggest", "serve",
            "context", "workspace", "docs", "doctor", "plugin", "web",
            "viz", "quality", "pr-summary", "ci-gen", "chat",
            "investigate", "cross-refactor", "metrics", "gate",
            "hotspots", "impact", "trace", "tool", "evolve", "tui",
            "mcp", "models",
        }
        assert set(cli.commands.keys()) == expected

    def test_every_command_has_help(self):
        """Every registered command must produce valid --help output."""
        runner = CliRunner()
        for name in cli.commands:
            result = runner.invoke(cli, [name, "--help"])
            assert result.exit_code == 0, f"{name} --help failed: {result.output}"

    def test_verbose_flag_accepted(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_pipe_flag_accepted(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--pipe", "--help"])
        assert result.exit_code == 0


# =========================================================================
# 2. Project init lifecycle
# =========================================================================

class TestInitLifecycle:
    """Test codex init — the first thing an end user does."""

    def test_init_creates_codex_dir(self, project: Path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(project)])
        assert result.exit_code == 0
        assert (project / ".codex").is_dir()

    def test_init_creates_config_json(self, project: Path):
        runner = CliRunner()
        runner.invoke(cli, ["init", str(project)])
        cfg = project / ".codex" / "config.json"
        assert cfg.exists()
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert "embedding" in data
        assert "search" in data

    def test_init_creates_index_dir(self, project: Path):
        runner = CliRunner()
        runner.invoke(cli, ["init", str(project)])
        assert (project / ".codex" / "index").is_dir()

    def test_init_idempotent(self, project: Path):
        """Running init twice should not error."""
        runner = CliRunner()
        runner.invoke(cli, ["init", str(project)])
        result = runner.invoke(cli, ["init", str(project)])
        assert result.exit_code == 0
        assert "already initialized" in result.output.lower()

    def test_init_config_roundtrip(self, project: Path):
        """init → load_config → save_config → reload — data must survive."""
        from semantic_code_intelligence.config.settings import (
            init_project, load_config, save_config,
        )
        config, _ = init_project(project)
        loaded = load_config(project)
        assert loaded.embedding.model_name == config.embedding.model_name

        loaded.embedding.model_name = "custom-model"
        save_config(loaded, project)
        reloaded = load_config(project)
        assert reloaded.embedding.model_name == "custom-model"


# =========================================================================
# 3. Indexing
# =========================================================================

class TestIndexing:
    """Test codex index — second step in the user journey."""

    def test_index_requires_init(self, project: Path):
        """index on an un-initialized dir should fail cleanly."""
        runner = CliRunner()
        result = runner.invoke(cli, ["index", str(project)])
        # Should tell the user to run init first
        assert "init" in result.output.lower()

    def test_index_after_init(self, project: Path):
        runner = CliRunner()
        runner.invoke(cli, ["init", str(project)])
        result = runner.invoke(cli, ["index", str(project)])
        assert result.exit_code == 0
        # Should report some files indexed
        assert "indexed" in result.output.lower() or "no indexable" in result.output.lower()

    def test_index_force_flag(self, project: Path):
        runner = CliRunner()
        runner.invoke(cli, ["init", str(project)])
        runner.invoke(cli, ["index", str(project)])
        result = runner.invoke(cli, ["index", "--force", str(project)])
        assert result.exit_code == 0

    def test_index_creates_vectors(self, project: Path):
        runner = CliRunner()
        runner.invoke(cli, ["init", str(project)])
        runner.invoke(cli, ["index", str(project)])
        index_dir = project / ".codex" / "index"
        # Either vectors.faiss exists or no indexable files were found
        faiss_file = index_dir / "vectors.faiss"
        metadata_file = index_dir / "metadata.json"
        if faiss_file.exists():
            assert metadata_file.exists()


# =========================================================================
# 4. Search — all modes
# =========================================================================

class TestSearchModes:
    """Test codex search across all four modes on an indexed project."""

    @pytest.fixture(autouse=True)
    def _indexed_project(self, project: Path):
        self.project = project
        self.runner = CliRunner()
        self.runner.invoke(cli, ["init", str(project)])
        self.runner.invoke(cli, ["index", str(project)])

    def test_search_semantic(self):
        result = self.runner.invoke(cli, [
            "search", "greeting function", "-p", str(self.project),
            "--mode", "semantic", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_search_keyword(self):
        result = self.runner.invoke(cli, [
            "search", "greet", "-p", str(self.project),
            "--mode", "keyword", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_search_regex(self):
        result = self.runner.invoke(cli, [
            "search", r"def\s+greet", "-p", str(self.project),
            "--mode", "regex", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_search_hybrid(self):
        result = self.runner.invoke(cli, [
            "search", "calculator", "-p", str(self.project),
            "--mode", "hybrid", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_search_no_init_fails(self, tmp_path: Path):
        result = self.runner.invoke(cli, [
            "search", "anything", "-p", str(tmp_path),
        ])
        assert "init" in result.output.lower()


# =========================================================================
# 5. Search — JSON / JSONL output
# =========================================================================

class TestSearchOutputFormats:
    """Test structured output modes (--json, --jsonl)."""

    @pytest.fixture(autouse=True)
    def _indexed(self, project: Path):
        self.project = project
        self.runner = CliRunner()
        self.runner.invoke(cli, ["init", str(project)])
        self.runner.invoke(cli, ["index", str(project)])

    def test_json_output_valid(self):
        result = self.runner.invoke(cli, [
            "search", "greet", "-p", str(self.project),
            "--json", "--no-auto-index",
        ])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert "query" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_json_result_structure(self):
        result = self.runner.invoke(cli, [
            "search", "greet", "-p", str(self.project),
            "--json", "--no-auto-index",
        ])
        data = _extract_json(result.output)
        if data["results"]:
            r = data["results"][0]
            assert "file_path" in r
            assert "start_line" in r
            assert "end_line" in r
            assert "language" in r
            assert "content" in r
            assert "score" in r

    def test_jsonl_output(self):
        result = self.runner.invoke(cli, [
            "search", "add", "-p", str(self.project),
            "--jsonl", "--no-auto-index",
        ])
        assert result.exit_code == 0
        # Each non-empty line starting with '{' must be valid JSONL
        for line in result.output.strip().splitlines():
            line = line.strip()
            if line and line.startswith("{"):
                obj = json.loads(line)
                assert "file_path" in obj

    def test_json_empty_query(self):
        result = self.runner.invoke(cli, [
            "search", "xyznonexistent_zzz", "-p", str(self.project),
            "--json", "--no-auto-index",
        ])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert data["result_count"] == 0 or isinstance(data["results"], list)

    def test_top_k_flag(self):
        result = self.runner.invoke(cli, [
            "search", "def", "-p", str(self.project),
            "--json", "-k", "2", "--no-auto-index",
        ])
        data = _extract_json(result.output)
        assert len(data["results"]) <= 2


# =========================================================================
# 6. Search — grep flags (-l, -L, -n, -C, -s)
# =========================================================================

class TestSearchGrepFlags:
    """Test grep-style flags on the search command."""

    @pytest.fixture(autouse=True)
    def _indexed(self, project: Path):
        self.project = project
        self.runner = CliRunner()
        self.runner.invoke(cli, ["init", str(project)])
        self.runner.invoke(cli, ["index", str(project)])

    def test_files_only_flag(self):
        result = self.runner.invoke(cli, [
            "search", "greet", "-p", str(self.project),
            "-l", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_files_without_match_flag(self):
        result = self.runner.invoke(cli, [
            "search", "greet", "-p", str(self.project),
            "-L", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_line_numbers_flag(self):
        result = self.runner.invoke(cli, [
            "search", "greet", "-p", str(self.project),
            "-n", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_context_lines_flag(self):
        result = self.runner.invoke(cli, [
            "search", "greet", "-p", str(self.project),
            "-C", "3", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_case_sensitive_flag(self):
        result = self.runner.invoke(cli, [
            "search", "Greet", "-p", str(self.project),
            "--mode", "regex", "-s", "--no-auto-index",
        ])
        assert result.exit_code == 0

    def test_search_help_shows_all_grep_flags(self):
        result = self.runner.invoke(cli, ["search", "--help"])
        for flag in ["--files-only", "--files-without-match", "--line-numbers",
                      "--context-lines", "--case-sensitive", "--jsonl"]:
            assert flag in result.output, f"Missing {flag} in search --help"


# =========================================================================
# 7. Models CLI — the end user manages embedding models
# =========================================================================

class TestModelsCLI:
    """Test the full models subcommand group."""

    def test_models_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "info" in result.output
        assert "switch" in result.output
        assert "download" in result.output

    def test_models_list(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "list"])
        assert result.exit_code == 0
        assert "MiniLM" in result.output

    def test_models_list_json_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "list", "--json"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert isinstance(data, list)
        assert len(data) >= 5
        # Each model has the expected keys
        for m in data:
            assert {"name", "dimension", "description", "is_default"} <= set(m.keys())

    def test_models_list_json_has_default(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "list", "--json"])
        data = _extract_json(result.output)
        defaults = [m for m in data if m["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["name"] == "all-MiniLM-L6-v2"

    def test_models_info_valid(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "info", "minilm"])
        assert result.exit_code == 0
        assert "384" in result.output  # dimension

    def test_models_info_alias(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "info", "bge-small"])
        assert result.exit_code == 0
        assert "BGE" in result.output

    def test_models_info_unknown_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "info", "no-such-model"])
        assert result.exit_code != 0

    def test_models_switch_requires_init(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "switch", "minilm", "-p", str(tmp_path)])
        assert result.exit_code != 0
        assert "init" in result.output.lower()

    def test_models_switch_updates_config(self, project: Path):
        runner = CliRunner()
        runner.invoke(cli, ["init", str(project)])
        result = runner.invoke(cli, ["models", "switch", "bge-small", "-p", str(project)])
        assert result.exit_code == 0
        # Verify config was actually updated
        from semantic_code_intelligence.config.settings import load_config
        config = load_config(project)
        assert config.embedding.model_name == "BAAI/bge-small-en-v1.5"


# =========================================================================
# 8. Model registry (direct API)
# =========================================================================

class TestModelRegistryAPI:
    """Test the model_registry module as a library user would."""

    def test_resolve_known_aliases(self):
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        assert resolve_model_name("minilm") == "all-MiniLM-L6-v2"
        assert resolve_model_name("bge-small") == "BAAI/bge-small-en-v1.5"
        assert resolve_model_name("nomic") == "nomic-ai/nomic-embed-text-v1.5"
        assert resolve_model_name("jina-code") == "jinaai/jina-embeddings-v2-base-code"
        assert resolve_model_name("mxbai-xsmall") == "mixedbread-ai/mxbai-embed-xsmall-v1"

    def test_resolve_full_name_passthrough(self):
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        assert resolve_model_name("all-MiniLM-L6-v2") == "all-MiniLM-L6-v2"

    def test_resolve_custom_model_passthrough(self):
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        assert resolve_model_name("my-org/my-model") == "my-org/my-model"

    def test_list_models_count(self):
        from semantic_code_intelligence.embeddings.model_registry import list_models
        assert len(list_models()) == 5

    def test_model_info_dimensions(self):
        from semantic_code_intelligence.embeddings.model_registry import get_model_info
        assert get_model_info("minilm").dimension == 384
        assert get_model_info("nomic").dimension == 768
        assert get_model_info("jina-code").dimension == 768
        assert get_model_info("mxbai-xsmall").dimension == 384

    def test_model_info_none_for_unknown(self):
        from semantic_code_intelligence.embeddings.model_registry import get_model_info
        assert get_model_info("nonexistent-xxx") is None

    def test_default_model_constant(self):
        from semantic_code_intelligence.embeddings.model_registry import DEFAULT_MODEL
        assert DEFAULT_MODEL == "all-MiniLM-L6-v2"


# =========================================================================
# 9. Config settings (API level)
# =========================================================================

class TestConfigAPI:
    """Test config machinery as a library consumer."""

    def test_appconfig_defaults(self):
        from semantic_code_intelligence.config.settings import AppConfig
        c = AppConfig()
        assert c.embedding.model_name == "all-MiniLM-L6-v2"
        assert c.search.top_k == 10
        assert c.llm.provider == "mock"

    def test_config_dir_paths(self, tmp_path: Path):
        from semantic_code_intelligence.config.settings import AppConfig
        assert AppConfig.config_dir(tmp_path) == tmp_path / ".codex"
        assert AppConfig.config_path(tmp_path) == tmp_path / ".codex" / "config.json"
        assert AppConfig.index_dir(tmp_path) == tmp_path / ".codex" / "index"

    def test_load_config_default_when_missing(self, tmp_path: Path):
        from semantic_code_intelligence.config.settings import load_config
        cfg = load_config(tmp_path)
        assert cfg.embedding.model_name == "all-MiniLM-L6-v2"

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        from semantic_code_intelligence.config.settings import (
            AppConfig, save_config, load_config,
        )
        cfg = AppConfig(project_root=str(tmp_path))
        cfg.search.top_k = 42
        cfg.embedding.chunk_size = 256
        save_config(cfg, tmp_path)

        loaded = load_config(tmp_path)
        assert loaded.search.top_k == 42
        assert loaded.embedding.chunk_size == 256

    def test_init_project_creates_everything(self, tmp_path: Path):
        from semantic_code_intelligence.config.settings import init_project, AppConfig
        config, config_path = init_project(tmp_path)
        assert config_path.exists()
        assert AppConfig.config_dir(tmp_path).is_dir()
        assert AppConfig.index_dir(tmp_path).is_dir()
        assert isinstance(config, AppConfig)


# =========================================================================
# 10. Vector store — the core data engine
# =========================================================================

class TestVectorStoreE2E:
    """End-to-end vector store operations."""

    def _make_vectors(self, n: int, dim: int):
        vecs = np.random.randn(n, dim).astype(np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

    def _make_metadata(self, n: int):
        from semantic_code_intelligence.storage.vector_store import ChunkMetadata
        return [
            ChunkMetadata(
                file_path=f"file_{i}.py",
                start_line=i * 10 + 1,
                end_line=i * 10 + 10,
                chunk_index=i,
                language="python",
                content=f"content chunk {i}",
                content_hash=f"hash{i}",
            )
            for i in range(n)
        ]

    def test_add_and_search(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(64)
        vecs = self._make_vectors(20, 64)
        meta = self._make_metadata(20)
        store.add(vecs, meta)
        assert store.size == 20

        results = store.search(vecs[0], top_k=5)
        assert len(results) == 5
        # First result should be the query vector itself (highest similarity)
        assert results[0][0].chunk_index == 0
        assert results[0][1] > 0.9  # near-perfect cosine sim

    def test_save_and_load(self, tmp_path: Path):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(32)
        vecs = self._make_vectors(10, 32)
        meta = self._make_metadata(10)
        store.add(vecs, meta)

        store.save(tmp_path / "vs")
        assert (tmp_path / "vs" / "vectors.faiss").exists()
        assert (tmp_path / "vs" / "metadata.json").exists()

        loaded = VectorStore.load(tmp_path / "vs")
        assert loaded.size == 10
        assert loaded.metadata[0].file_path == "file_0.py"

    def test_remove_by_file(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(16)
        vecs = self._make_vectors(10, 16)
        meta = self._make_metadata(10)
        store.add(vecs, meta)

        removed = store.remove_by_file("file_3.py")
        assert removed == 1
        assert store.size == 9
        assert all(m.file_path != "file_3.py" for m in store.metadata)

    def test_remove_nonexistent_file(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(16)
        vecs = self._make_vectors(5, 16)
        meta = self._make_metadata(5)
        store.add(vecs, meta)
        assert store.remove_by_file("no_such_file.py") == 0
        assert store.size == 5

    def test_clear(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(16)
        vecs = self._make_vectors(5, 16)
        meta = self._make_metadata(5)
        store.add(vecs, meta)
        store.clear()
        assert store.size == 0
        assert len(store.metadata) == 0

    def test_add_empty_noop(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(16)
        store.add(np.empty((0, 16), dtype=np.float32), [])
        assert store.size == 0

    def test_add_mismatched_raises(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore, ChunkMetadata
        store = VectorStore(16)
        vecs = self._make_vectors(3, 16)
        meta = self._make_metadata(2)
        with pytest.raises(ValueError, match="metadata count"):
            store.add(vecs, meta)

    def test_search_empty_store(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(16)
        results = store.search(np.zeros(16, dtype=np.float32), top_k=5)
        assert results == []

    def test_ivf_constructor(self):
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(64, use_ivf=True)
        assert store._use_ivf is True

    def test_ivf_fallback_small_batch(self):
        """IVF mode falls back to flat when the batch is too small to train."""
        from semantic_code_intelligence.storage.vector_store import VectorStore
        store = VectorStore(8, use_ivf=True)
        vecs = self._make_vectors(10, 8)
        meta = self._make_metadata(10)
        store.add(vecs, meta)
        assert store.size == 10
        # Should have silently fallen back to flat
        assert store._use_ivf is False

    def test_ivf_constants(self):
        from semantic_code_intelligence.storage.vector_store import (
            IVF_THRESHOLD, IVF_NLIST, IVF_NPROBE,
        )
        assert IVF_THRESHOLD == 50_000
        assert IVF_NLIST == 100
        assert IVF_NPROBE == 10


# =========================================================================
# 11. Formatter — JSON / JSONL / Rich / Context expansion
# =========================================================================

class TestFormatterAPI:
    """Test the search formatter as a library consumer."""

    def _make_results(self, n: int = 3):
        from semantic_code_intelligence.services.search_service import SearchResult
        return [
            SearchResult(
                file_path=f"file_{i}.py",
                start_line=i * 10 + 1,
                end_line=i * 10 + 10,
                language="python",
                content=f"def func_{i}():\n    pass\n",
                score=0.9 - i * 0.1,
                chunk_index=i,
            )
            for i in range(n)
        ]

    def test_format_json(self):
        from semantic_code_intelligence.search.formatter import format_results_json
        results = self._make_results(2)
        output = format_results_json("test query", results, 10)
        data = json.loads(output)
        assert data["query"] == "test query"
        assert data["top_k"] == 10
        assert data["result_count"] == 2
        assert len(data["results"]) == 2

    def test_format_json_empty(self):
        from semantic_code_intelligence.search.formatter import format_results_json
        output = format_results_json("empty", [], 5)
        data = json.loads(output)
        assert data["result_count"] == 0
        assert data["results"] == []

    def test_format_jsonl(self):
        from semantic_code_intelligence.search.formatter import format_results_jsonl
        results = self._make_results(3)
        output = format_results_jsonl(results)
        lines = output.strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            obj = json.loads(line)
            assert "file_path" in obj
            assert "score" in obj

    def test_format_jsonl_empty(self):
        from semantic_code_intelligence.search.formatter import format_results_jsonl
        assert format_results_jsonl([]) == ""

    def test_expand_context_missing_file(self):
        from semantic_code_intelligence.search.formatter import _expand_context
        from semantic_code_intelligence.services.search_service import SearchResult
        r = SearchResult("nonexistent.py", 5, 10, "python", "hello", 0.5, 0)
        content, start = _expand_context(r, 3)
        assert content == "hello"
        assert start == 5

    def test_expand_context_real_file(self, tmp_path: Path):
        from semantic_code_intelligence.search.formatter import _expand_context
        from semantic_code_intelligence.services.search_service import SearchResult
        src = tmp_path / "test.py"
        lines = [f"line {i}\n" for i in range(1, 21)]
        src.write_text("".join(lines), encoding="utf-8")

        r = SearchResult(str(src), 10, 12, "python", "line 10\n", 0.8, 0)
        content, start = _expand_context(r, 2)
        assert start == 8  # 10 - 2
        assert "line 8" in content
        assert "line 14" in content


# =========================================================================
# 12. TUI helpers (fallback REPL utilities)
# =========================================================================

class TestTUIHelpers:
    """Test TUI utility functions without launching the full TUI."""

    def test_textual_available_returns_bool(self):
        from semantic_code_intelligence.tui import _textual_available
        assert isinstance(_textual_available(), bool)

    def test_format_result_line(self):
        from semantic_code_intelligence.tui import _format_result_line
        from semantic_code_intelligence.services.search_service import SearchResult
        r = SearchResult("src/main.py", 10, 20, "python", "code", 0.85, 0)
        line = _format_result_line(1, r)
        assert "main.py" in line
        assert "0.850" in line
        assert "L10-20" in line

    def test_print_results_no_results(self, capsys):
        from semantic_code_intelligence.tui import _print_results
        _print_results([], "test query")
        captured = capsys.readouterr()
        assert "no results" in captured.out.lower()

    def test_print_results_with_results(self, capsys):
        from semantic_code_intelligence.tui import _print_results
        from semantic_code_intelligence.services.search_service import SearchResult
        results = [
            SearchResult("a.py", 1, 5, "python", "code", 0.9, 0),
            SearchResult("b.py", 10, 20, "python", "more", 0.8, 1),
        ]
        _print_results(results, "test")
        captured = capsys.readouterr()
        assert "2 results" in captured.out
        assert "a.py" in captured.out

    def test_show_detail_valid_index(self, capsys):
        from semantic_code_intelligence.tui import _show_detail
        from semantic_code_intelligence.services.search_service import SearchResult
        results = [
            SearchResult("a.py", 1, 3, "python", "line1\nline2\nline3", 0.9, 0),
        ]
        _show_detail(results, 1)
        captured = capsys.readouterr()
        assert "a.py" in captured.out
        assert "line1" in captured.out

    def test_show_detail_invalid_index(self, capsys):
        from semantic_code_intelligence.tui import _show_detail
        _show_detail([], 5)
        captured = capsys.readouterr()
        assert "invalid" in captured.out.lower()

    def test_run_tui_function_exists(self):
        from semantic_code_intelligence.tui import run_tui
        assert callable(run_tui)


# =========================================================================
# 13. VS Code extension — validate all artifacts
# =========================================================================

class TestVSCodeExtension:
    """Validate the VS Code extension from an end-user/developer perspective."""

    VSCODE_DIR = Path(__file__).resolve().parents[2] / "vscode-extension"

    def test_extension_directory_exists(self):
        assert self.VSCODE_DIR.is_dir()

    # --- package.json ---

    def test_package_json_exists(self):
        assert (self.VSCODE_DIR / "package.json").exists()

    def test_package_json_valid_json(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        assert isinstance(data, dict)

    def test_package_json_name(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        assert data["name"] == "codexa"

    def test_package_json_version(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        assert "version" in data

    def test_package_json_engine(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        assert data["engines"]["vscode"].startswith("^")

    def test_package_json_main_entry(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        assert data["main"] == "./out/extension.js"

    def test_package_json_4_commands(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        commands = data["contributes"]["commands"]
        assert len(commands) == 4
        command_ids = {c["command"] for c in commands}
        assert command_ids == {
            "codexa.search", "codexa.askCodexA",
            "codexa.callGraph", "codexa.models",
        }

    def test_package_json_activation_events(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        events = data["activationEvents"]
        assert "onCommand:codexa.search" in events
        assert "onView:codexaSearchView" in events

    def test_package_json_sidebar_webview(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        views = data["contributes"]["views"]
        assert "codexa" in views
        view_ids = [v["id"] for v in views["codexa"]]
        assert "codexaSearchView" in view_ids

    def test_package_json_keybinding(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        keybindings = data["contributes"]["keybindings"]
        assert len(keybindings) >= 1
        kb = keybindings[0]
        assert kb["command"] == "codexa.search"
        assert "ctrl+shift+f5" in kb.get("key", "")

    def test_package_json_activity_bar(self):
        data = json.loads((self.VSCODE_DIR / "package.json").read_text("utf-8"))
        containers = data["contributes"]["viewsContainers"]["activitybar"]
        assert any(c["id"] == "codexa" for c in containers)

    # --- extension.ts ---

    def test_extension_ts_exists(self):
        assert (self.VSCODE_DIR / "src" / "extension.ts").exists()

    def test_extension_ts_exports_activate(self):
        src = (self.VSCODE_DIR / "src" / "extension.ts").read_text("utf-8")
        assert "export function activate" in src

    def test_extension_ts_exports_deactivate(self):
        src = (self.VSCODE_DIR / "src" / "extension.ts").read_text("utf-8")
        assert "export function deactivate" in src

    def test_extension_ts_search_view_provider(self):
        src = (self.VSCODE_DIR / "src" / "extension.ts").read_text("utf-8")
        assert "class SearchViewProvider" in src

    def test_extension_ts_codex_bin_helper(self):
        src = (self.VSCODE_DIR / "src" / "extension.ts").read_text("utf-8")
        assert "function codexBin" in src

    def test_extension_ts_run_codex_helper(self):
        src = (self.VSCODE_DIR / "src" / "extension.ts").read_text("utf-8")
        assert "async function runCodex" in src

    def test_extension_ts_registers_4_commands(self):
        src = (self.VSCODE_DIR / "src" / "extension.ts").read_text("utf-8")
        for cmd in ["codexa.search", "codexa.askCodexA", "codexa.callGraph", "codexa.models"]:
            assert cmd in src, f"Command {cmd} not registered in extension.ts"

    def test_extension_ts_webview_html(self):
        src = (self.VSCODE_DIR / "src" / "extension.ts").read_text("utf-8")
        assert "<!DOCTYPE html>" in src
        assert "acquireVsCodeApi" in src

    def test_extension_ts_escape_html(self):
        """Extension must escape HTML in search results to prevent XSS."""
        src = (self.VSCODE_DIR / "src" / "extension.ts").read_text("utf-8")
        assert "escapeHtml" in src

    # --- tsconfig.json ---

    def test_tsconfig_json_exists(self):
        assert (self.VSCODE_DIR / "tsconfig.json").exists()

    def test_tsconfig_json_valid(self):
        raw = (self.VSCODE_DIR / "tsconfig.json").read_text("utf-8")
        data = json.loads(raw)
        assert "compilerOptions" in data

    # --- README ---

    def test_readme_exists(self):
        assert (self.VSCODE_DIR / "README.md").exists()

    def test_readme_not_empty(self):
        content = (self.VSCODE_DIR / "README.md").read_text("utf-8")
        assert len(content) > 50


# =========================================================================
# 14. Build script (PyInstaller)
# =========================================================================

class TestBuildScript:
    """Verify the PyInstaller build script is usable."""

    BUILD_PY = Path(__file__).resolve().parents[2] / "build.py"

    def test_build_py_exists(self):
        assert self.BUILD_PY.exists()

    def test_build_py_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("build", str(self.BUILD_PY))
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        # Don't exec the module (it would try to build) — just check it
        assert mod is not None

    def test_build_py_has_build_function(self):
        src = self.BUILD_PY.read_text("utf-8")
        assert "def build" in src

    def test_build_py_supports_onefile(self):
        src = self.BUILD_PY.read_text("utf-8")
        assert "onefile" in src.lower()


# =========================================================================
# 15. Doctor command
# =========================================================================

class TestDoctorCommand:
    """Test the doctor subcommand — quick health check."""

    def test_doctor_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0

    def test_doctor_runs(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "python" in result.output.lower()


# =========================================================================
# 16. Full user journey — init → index → search → json → switch → re-search
# =========================================================================

class TestFullUserJourney:
    """Simulate a complete end-user workflow from start to finish."""

    def test_full_pipeline(self, project: Path):
        runner = CliRunner()

        # 1. Init
        r = runner.invoke(cli, ["init", str(project)])
        assert r.exit_code == 0
        assert (project / ".codex").is_dir()

        # 2. Index
        r = runner.invoke(cli, ["index", str(project)])
        assert r.exit_code == 0

        # 3. Semantic search → JSON
        r = runner.invoke(cli, [
            "search", "greeting", "-p", str(project),
            "--json", "--no-auto-index",
        ])
        assert r.exit_code == 0
        data = _extract_json(r.output)
        assert "results" in data

        # 4. Regex search → files-only
        r = runner.invoke(cli, [
            "search", r"def\s+\w+", "-p", str(project),
            "--mode", "regex", "-l", "--no-auto-index",
        ])
        assert r.exit_code == 0

        # 5. JSONL output
        r = runner.invoke(cli, [
            "search", "calculator", "-p", str(project),
            "--jsonl", "--no-auto-index",
        ])
        assert r.exit_code == 0

        # 6. Models list
        r = runner.invoke(cli, ["models", "list", "--json"])
        assert r.exit_code == 0
        models = _extract_json(r.output)
        assert len(models) >= 5

        # 7. Switch model
        r = runner.invoke(cli, ["models", "switch", "bge-small", "-p", str(project)])
        assert r.exit_code == 0

        # 8. Verify config changed
        from semantic_code_intelligence.config.settings import load_config
        cfg = load_config(project)
        assert cfg.embedding.model_name == "BAAI/bge-small-en-v1.5"

        # 9. Re-index with force (new model)
        r = runner.invoke(cli, ["index", "--force", str(project)])
        assert r.exit_code == 0

        # 10. Search again after model switch
        r = runner.invoke(cli, [
            "search", "fibonacci", "-p", str(project),
            "--json", "--no-auto-index",
        ])
        assert r.exit_code == 0
        data = _extract_json(r.output)
        assert "results" in data

    def test_doctor_in_initialized_project(self, project: Path):
        runner = CliRunner()
        runner.invoke(cli, ["init", str(project)])
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0

    def test_version_consistency(self):
        """The version in __init__ should match --version output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert __version__ in result.output


# =========================================================================
# 17. SearchResult.to_dict()
# =========================================================================

class TestSearchResultContract:
    """Verify the SearchResult dataclass contract."""

    def test_to_dict_keys(self):
        from semantic_code_intelligence.services.search_service import SearchResult
        r = SearchResult("a.py", 1, 10, "python", "code", 0.999, 0)
        d = r.to_dict()
        assert set(d.keys()) == {
            "file_path", "start_line", "end_line",
            "language", "content", "score", "chunk_index",
        }

    def test_to_dict_score_rounded(self):
        from semantic_code_intelligence.services.search_service import SearchResult
        r = SearchResult("a.py", 1, 10, "python", "code", 0.123456789, 0)
        assert r.to_dict()["score"] == 0.1235

    def test_to_dict_serializable(self):
        from semantic_code_intelligence.services.search_service import SearchResult
        r = SearchResult("a.py", 1, 10, "python", "code", 0.9, 0)
        # Should not raise
        json.dumps(r.to_dict())
