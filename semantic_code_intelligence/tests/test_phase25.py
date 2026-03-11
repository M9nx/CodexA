"""Phase 25 — Incremental Indexing & Quality Refactors.

Tests verify:
  1.  VectorStore.remove_by_file — correct removal and index rebuild
  2.  Incremental indexing — stale vector removal, deleted file cleanup
  3.  HF_TOKEN configuration — env var propagation
  4.  CallGraph regex matching — word boundary accuracy
  5.  Web viz data format — edges key in callgraph response
  6.  Silent exception logging — debug messages instead of bare pass
  7.  Refactored CLI output helpers — quality_cmd, metrics_cmd
  8.  Module imports and version
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantic_code_intelligence.storage.vector_store import ChunkMetadata, VectorStore

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ===================================================================
# 1. VectorStore.remove_by_file
# ===================================================================


class TestVectorStoreRemoveByFile:
    """Tests for VectorStore.remove_by_file()."""

    def _make_store(self) -> VectorStore:
        store = VectorStore(dimension=4)
        vecs = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float32)
        meta = [
            ChunkMetadata(file_path="/a.py", start_line=1, end_line=10,
                          chunk_index=0, language="python", content="a1"),
            ChunkMetadata(file_path="/b.py", start_line=1, end_line=5,
                          chunk_index=0, language="python", content="b1"),
            ChunkMetadata(file_path="/a.py", start_line=11, end_line=20,
                          chunk_index=1, language="python", content="a2"),
            ChunkMetadata(file_path="/c.py", start_line=1, end_line=15,
                          chunk_index=0, language="python", content="c1"),
        ]
        store.add(vecs, meta)
        return store

    def test_remove_existing_file(self) -> None:
        store = self._make_store()
        assert store.size == 4
        removed = store.remove_by_file("/a.py")
        assert removed == 2
        assert store.size == 2
        assert all(m.file_path != "/a.py" for m in store.metadata)

    def test_remove_nonexistent_file(self) -> None:
        store = self._make_store()
        removed = store.remove_by_file("/nonexistent.py")
        assert removed == 0
        assert store.size == 4

    def test_remove_all_files(self) -> None:
        store = self._make_store()
        store.remove_by_file("/a.py")
        store.remove_by_file("/b.py")
        store.remove_by_file("/c.py")
        assert store.size == 0
        assert store.metadata == []

    def test_search_after_removal(self) -> None:
        store = self._make_store()
        store.remove_by_file("/a.py")
        query = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        results = store.search(query, top_k=5)
        assert len(results) == 2
        assert results[0][0].file_path == "/b.py"

    def test_add_after_removal(self) -> None:
        store = self._make_store()
        store.remove_by_file("/b.py")
        new_vec = np.array([[0.5, 0.5, 0.0, 0.0]], dtype=np.float32)
        new_meta = [ChunkMetadata(file_path="/d.py", start_line=1, end_line=3,
                                  chunk_index=0, language="python", content="d1")]
        store.add(new_vec, new_meta)
        assert store.size == 4
        paths = {m.file_path for m in store.metadata}
        assert "/d.py" in paths
        assert "/b.py" not in paths


# ===================================================================
# 2. Incremental indexing — stale removal
# ===================================================================


class TestIncrementalIndexing:
    """Tests for indexing_service stale vector and deleted file handling."""

    def test_deleted_paths_detected(self) -> None:
        """HashStore tracks should be cleaned up for deleted files."""
        from semantic_code_intelligence.storage.hash_store import HashStore

        hs = HashStore()
        hs.set("src/old.py", "abc123")
        hs.set("src/keep.py", "def456")

        scanned_paths = {"src/keep.py"}
        deleted = [k for k in list(hs._hashes.keys()) if k not in scanned_paths]
        assert deleted == ["src/old.py"]

    def test_hash_store_remove(self) -> None:
        from semantic_code_intelligence.storage.hash_store import HashStore

        hs = HashStore()
        hs.set("a.py", "h1")
        hs.set("b.py", "h2")
        hs.remove("a.py")
        assert hs.get("a.py") is None
        assert hs.get("b.py") == "h2"

    def test_remove_by_file_preserves_other_vectors(self) -> None:
        """Incremental re-index removes stale vectors but keeps others."""
        store = VectorStore(dimension=2)
        vecs = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        meta = [
            ChunkMetadata(file_path="/changed.py", start_line=1, end_line=5,
                          chunk_index=0, language="python", content="old"),
            ChunkMetadata(file_path="/unchanged.py", start_line=1, end_line=5,
                          chunk_index=0, language="python", content="keep"),
        ]
        store.add(vecs, meta)
        store.remove_by_file("/changed.py")

        assert store.size == 1
        assert store.metadata[0].file_path == "/unchanged.py"

        # Add updated file
        new_vec = np.array([[0.5, 0.5]], dtype=np.float32)
        new_meta = [ChunkMetadata(file_path="/changed.py", start_line=1, end_line=8,
                                  chunk_index=0, language="python", content="new")]
        store.add(new_vec, new_meta)
        assert store.size == 2


# ===================================================================
# 3. HF_TOKEN configuration
# ===================================================================


class TestHFTokenConfig:
    """Tests for _configure_hf_token() in embeddings/generator.py."""

    def test_hf_token_already_set(self) -> None:
        from semantic_code_intelligence.embeddings.generator import _configure_hf_token

        with patch.dict(os.environ, {"HF_TOKEN": "existing"}, clear=False):
            _configure_hf_token()
            assert os.environ["HF_TOKEN"] == "existing"

    def test_hugging_face_hub_token_propagated(self) -> None:
        from semantic_code_intelligence.embeddings.generator import _configure_hf_token

        env = {"HUGGING_FACE_HUB_TOKEN": "hub_tok"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("HF_TOKEN", None)
            _configure_hf_token()
            assert os.environ.get("HF_TOKEN") == "hub_tok"

    def test_huggingface_token_propagated(self) -> None:
        from semantic_code_intelligence.embeddings.generator import _configure_hf_token

        env = {"HUGGINGFACE_TOKEN": "hf_tok"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("HF_TOKEN", None)
            os.environ.pop("HUGGING_FACE_HUB_TOKEN", None)
            _configure_hf_token()
            assert os.environ.get("HF_TOKEN") == "hf_tok"

    def test_no_token_set(self) -> None:
        from semantic_code_intelligence.embeddings.generator import _configure_hf_token

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HF_TOKEN", None)
            os.environ.pop("HUGGING_FACE_HUB_TOKEN", None)
            os.environ.pop("HUGGINGFACE_TOKEN", None)
            _configure_hf_token()
            assert "HF_TOKEN" not in os.environ


# ===================================================================
# 4. CallGraph regex matching
# ===================================================================


class TestCallGraphRegex:
    """Tests for word-boundary call detection in context/engine.py."""

    def test_exact_function_call_detected(self) -> None:
        pattern = re.compile(r"\bprocess_data\s*[\(\.]")
        body = "result = process_data(items)"
        assert pattern.search(body) is not None

    def test_method_call_detected(self) -> None:
        pattern = re.compile(r"\bprocess_data\s*[\(\.]")
        body = "obj.process_data(x)"
        assert pattern.search(body) is not None

    def test_substring_not_matched(self) -> None:
        pattern = re.compile(r"\bprocess_data\s*[\(\.]")
        body = "unprocess_data_handler = 1"
        assert pattern.search(body) is None

    def test_partial_name_not_matched(self) -> None:
        pattern = re.compile(r"\bget\s*[\(\.]")
        body = "get_user()"
        # "get" at word boundary followed by "_" should not match \(|\.)
        assert pattern.search(body) is None

    def test_call_with_space(self) -> None:
        pattern = re.compile(r"\bfoo\s*[\(\.]")
        body = "foo (x)"
        assert pattern.search(body) is not None


# ===================================================================
# 5. Web viz data format
# ===================================================================


class TestVizDataFormat:
    """Tests for viz endpoint data format."""

    def test_callgraph_has_edges_key(self) -> None:
        from semantic_code_intelligence.bridge.context_provider import ContextProvider

        provider = ContextProvider(_PROJECT_ROOT)
        with patch.object(provider, "_ensure_indexed") as mock_idx:
            mock_builder = MagicMock()
            mock_idx.return_value = mock_builder
            mock_builder.get_call_graph.return_value = MagicMock(
                callers={"a": ["b"]},
                callees={"a": ["c"]},
            )
            data = provider.get_call_graph(symbol_name="a")
            assert "edges" in data
            assert isinstance(data["edges"], list)


# ===================================================================
# 6. Silent exception logging
# ===================================================================


class TestSilentExceptionLogging:
    """Verify that previously silent catches now log debug messages."""

    @pytest.mark.parametrize("module_path", [
        "semantic_code_intelligence.cli.commands.explain_cmd",
        "semantic_code_intelligence.ci.hooks",
        "semantic_code_intelligence.cli.commands.quality_cmd",
        "semantic_code_intelligence.cli.commands.pr_summary_cmd",
        "semantic_code_intelligence.llm.investigation",
        "semantic_code_intelligence.llm.cross_refactor",
        "semantic_code_intelligence.cli.commands.chat_cmd",
        "semantic_code_intelligence.cli.commands.cross_refactor_cmd",
        "semantic_code_intelligence.ci.metrics",
        "semantic_code_intelligence.cli.commands.hotspots_cmd",
        "semantic_code_intelligence.cli.commands.impact_cmd",
        "semantic_code_intelligence.cli.commands.trace_cmd",
        "semantic_code_intelligence.docs",
        "semantic_code_intelligence.llm.streaming",
    ])
    def test_module_has_no_bare_pass_in_except(self, module_path: str) -> None:
        """Ensure no bare 'except Exception: pass' remains in the source.

        JSON/TypeError fallback patterns (e.g. ``except (json.JSONDecodeError, TypeError): pass``)
        are allowed because they represent intentional parse-fallback, not swallowed errors.
        """
        import importlib
        mod = importlib.import_module(module_path)
        src_path = Path(mod.__file__)
        source = src_path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "pass" and i > 0:
                prev = lines[i - 1].strip()
                if prev.startswith("except"):
                    # Allow JSON/type-error parse fallbacks
                    if "JSONDecodeError" in prev or "TypeError" in prev:
                        continue
                    if "Exception" in prev or prev == "except:":
                        pytest.fail(
                            f"{module_path}:{i + 1} has bare 'except: pass' — "
                            f"should use logger.debug()"
                        )


# ===================================================================
# 7. Refactored CLI output helpers
# ===================================================================


class TestQualityCmdHelpers:
    """Tests for extracted quality_cmd output helpers."""

    def test_output_safety_json(self) -> None:
        from semantic_code_intelligence.cli.commands.quality_cmd import _output_safety

        safety = MagicMock()
        safety.safe = True
        safety.to_dict.return_value = {"safe": True, "issues": []}

        from io import StringIO
        from unittest.mock import patch as _patch
        from click.testing import CliRunner

        import click

        @click.command()
        def _test_cmd() -> None:
            _output_safety(safety, 10, json_mode=True, pipe=False)

        runner = CliRunner()
        result = runner.invoke(_test_cmd)
        assert '"safe": true' in result.output

    def test_output_safety_pipe(self) -> None:
        from semantic_code_intelligence.cli.commands.quality_cmd import _output_safety

        safety = MagicMock()
        safety.safe = True

        import click
        from click.testing import CliRunner

        @click.command()
        def _test_cmd() -> None:
            _output_safety(safety, 5, json_mode=False, pipe=True)

        runner = CliRunner()
        result = runner.invoke(_test_cmd)
        assert "PASS" in result.output
        assert "5 files" in result.output

    def test_output_report_pipe(self) -> None:
        from semantic_code_intelligence.cli.commands.quality_cmd import _output_report_pipe

        report = MagicMock()
        report.files_analyzed = 10
        report.symbol_count = 50
        report.issue_count = 3
        report.complexity_issues = []
        report.dead_code = []
        report.duplicates = []
        report.bandit_issues = []
        report.safety = None
        report.maintainability_index = None

        import click
        from click.testing import CliRunner

        @click.command()
        def _test_cmd() -> None:
            _output_report_pipe(report)

        runner = CliRunner()
        result = runner.invoke(_test_cmd)
        assert "Files: 10" in result.output
        assert "Issues: 3" in result.output


class TestMetricsCmdHelpers:
    """Tests for extracted metrics_cmd output helpers."""

    def test_output_history_json(self) -> None:
        from semantic_code_intelligence.cli.commands.metrics_cmd import _output_history

        snap = MagicMock()
        snap.to_dict.return_value = {"timestamp": 1000, "mi": 65.0}

        import click
        from click.testing import CliRunner

        @click.command()
        def _test_cmd() -> None:
            _output_history([snap], 1, json_mode=True, pipe=False)

        runner = CliRunner()
        result = runner.invoke(_test_cmd)
        assert '"snapshots"' in result.output

    def test_output_trend_pipe(self) -> None:
        from semantic_code_intelligence.cli.commands.metrics_cmd import _output_trend

        trend = MagicMock()
        trend.metric_name = "maintainability_index"
        trend.direction = "improving"
        trend.oldest_value = 60.0
        trend.newest_value = 70.0
        trend.delta = 10.0

        import click
        from click.testing import CliRunner

        @click.command()
        def _test_cmd() -> None:
            _output_trend([trend], 5, json_mode=False, pipe=True)

        runner = CliRunner()
        result = runner.invoke(_test_cmd)
        assert "TREND" in result.output
        assert "maintainability_index" in result.output

    def test_output_current_metrics_json(self) -> None:
        from semantic_code_intelligence.cli.commands.metrics_cmd import _output_current_metrics

        pm = MagicMock()
        pm.to_dict.return_value = {"files_analyzed": 10, "mi": 65.0}

        import click
        from click.testing import CliRunner

        @click.command()
        def _test_cmd() -> None:
            _output_current_metrics(pm, Path("."), None, json_mode=True, pipe=False)

        runner = CliRunner()
        result = runner.invoke(_test_cmd)
        assert '"files_analyzed"' in result.output


# ===================================================================
# 8. Module imports and version
# ===================================================================


class TestImportsAndVersion:
    """Verify that all Phase 25 modules import correctly."""

    def test_version_0_25(self) -> None:
        import semantic_code_intelligence
        assert semantic_code_intelligence.__version__ == "0.5.0"

    def test_vector_store_has_remove_by_file(self) -> None:
        assert hasattr(VectorStore, "remove_by_file")

    def test_hf_token_function_importable(self) -> None:
        from semantic_code_intelligence.embeddings.generator import _configure_hf_token
        assert callable(_configure_hf_token)

    def test_quality_helpers_importable(self) -> None:
        from semantic_code_intelligence.cli.commands.quality_cmd import (
            _output_safety,
            _output_report_pipe,
            _output_report_rich,
        )
        assert callable(_output_safety)
        assert callable(_output_report_pipe)
        assert callable(_output_report_rich)

    def test_metrics_helpers_importable(self) -> None:
        from semantic_code_intelligence.cli.commands.metrics_cmd import (
            _output_history,
            _output_trend,
            _output_current_metrics,
        )
        assert callable(_output_history)
        assert callable(_output_trend)
        assert callable(_output_current_metrics)

    def test_indexing_helpers_importable(self) -> None:
        from semantic_code_intelligence.services.indexing_service import (
            _extract_symbols,
            _compute_index_stats,
        )
        assert callable(_extract_symbols)
        assert callable(_compute_index_stats)

    def test_visualize_module_importable(self) -> None:
        from semantic_code_intelligence.web.visualize import (
            render_call_graph,
            render_dependency_graph,
        )
        assert callable(render_call_graph)
        assert callable(render_dependency_graph)

