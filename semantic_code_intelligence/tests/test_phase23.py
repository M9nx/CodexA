"""Phase 23 — Persistent Intelligence Index.

Tests verify:
  1. IndexManifest — serialisation, persistence, compatibility checking
  2. SymbolRegistry — add/remove/find/search, persistence, summaries
  3. IndexStats — coverage tracking, staleness, persistence
  4. QueryHistory — record/recent/popular, FIFO eviction, persistence
  5. Indexing integration — manifest/registry/stats populated after indexing
  6. Search integration — query history recorded after search
  7. Module imports and version
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from semantic_code_intelligence.storage.index_manifest import (
    MANIFEST_FILE,
    SCHEMA_VERSION,
    IndexManifest,
)
from semantic_code_intelligence.storage.index_stats import (
    STATS_FILE,
    IndexStats,
    LanguageCoverage,
)
from semantic_code_intelligence.storage.query_history import (
    HISTORY_FILE,
    MAX_HISTORY,
    QueryHistory,
    QueryRecord,
)
from semantic_code_intelligence.storage.symbol_registry import (
    REGISTRY_FILE,
    SymbolEntry,
    SymbolRegistry,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC = _PROJECT_ROOT / "semantic_code_intelligence"


# ═══════════════════════════════════════════════════════════════════════════
# 1 — IndexManifest
# ═══════════════════════════════════════════════════════════════════════════


class TestIndexManifest:
    """Tests for IndexManifest dataclass."""

    def test_defaults(self):
        m = IndexManifest()
        assert m.schema_version == SCHEMA_VERSION
        assert m.embedding_model == "all-MiniLM-L6-v2"
        assert m.embedding_dimension == 384
        assert m.created_at == 0.0
        assert m.updated_at == 0.0
        assert m.total_files == 0
        assert m.total_chunks == 0
        assert m.total_symbols == 0
        assert m.languages == []
        assert m.project_root == ""

    def test_to_dict_and_from_dict(self):
        m = IndexManifest(
            total_files=10,
            total_chunks=50,
            total_symbols=30,
            languages=["python", "javascript"],
            project_root="/repo",
        )
        d = m.to_dict()
        m2 = IndexManifest.from_dict(d)
        assert m2.total_files == 10
        assert m2.total_chunks == 50
        assert m2.languages == ["python", "javascript"]
        assert m2.project_root == "/repo"

    def test_from_dict_ignores_unknown_keys(self):
        d = {"total_files": 3, "unknown_field": "ignored"}
        m = IndexManifest.from_dict(d)
        assert m.total_files == 3

    def test_touch_sets_timestamps(self):
        m = IndexManifest()
        assert m.created_at == 0.0
        m.touch()
        assert m.created_at > 0.0
        assert m.updated_at > 0.0
        first_created = m.created_at
        time.sleep(0.01)
        m.touch()
        assert m.created_at == first_created  # created_at unchanged
        assert m.updated_at > first_created

    def test_is_compatible(self):
        m = IndexManifest(embedding_model="all-MiniLM-L6-v2", embedding_dimension=384)
        assert m.is_compatible("all-MiniLM-L6-v2", 384) is True
        assert m.is_compatible("other-model", 384) is False
        assert m.is_compatible("all-MiniLM-L6-v2", 768) is False

    def test_save_and_load(self, tmp_path: Path):
        m = IndexManifest(total_files=5, total_chunks=20, project_root="/repo")
        m.touch()
        m.save(tmp_path)

        assert (tmp_path / MANIFEST_FILE).exists()

        loaded = IndexManifest.load(tmp_path)
        assert loaded is not None
        assert loaded.total_files == 5
        assert loaded.total_chunks == 20
        assert loaded.project_root == "/repo"
        assert loaded.created_at > 0.0

    def test_load_returns_none_when_missing(self, tmp_path: Path):
        assert IndexManifest.load(tmp_path) is None

    def test_load_returns_none_on_corrupt_json(self, tmp_path: Path):
        (tmp_path / MANIFEST_FILE).write_text("not json", encoding="utf-8")
        assert IndexManifest.load(tmp_path) is None

    def test_save_creates_directory(self, tmp_path: Path):
        deep = tmp_path / "a" / "b" / "c"
        IndexManifest().save(deep)
        assert (deep / MANIFEST_FILE).exists()


# ═══════════════════════════════════════════════════════════════════════════
# 2 — SymbolRegistry
# ═══════════════════════════════════════════════════════════════════════════


def _make_entry(**kwargs) -> SymbolEntry:
    defaults = dict(
        name="foo",
        kind="function",
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        language="python",
    )
    defaults.update(kwargs)
    return SymbolEntry(**defaults)


class TestSymbolEntry:
    """Tests for SymbolEntry dataclass."""

    def test_qualified_name_no_parent(self):
        e = _make_entry(name="bar", parent=None)
        assert e.qualified_name == "bar"

    def test_qualified_name_with_parent(self):
        e = _make_entry(name="method", parent="MyClass")
        assert e.qualified_name == "MyClass.method"

    def test_to_dict_and_from_dict(self):
        e = _make_entry(name="hello", parameters=["a", "b"], decorators=["@staticmethod"])
        d = e.to_dict()
        e2 = SymbolEntry.from_dict(d)
        assert e2.name == "hello"
        assert e2.parameters == ["a", "b"]
        assert e2.decorators == ["@staticmethod"]

    def test_from_dict_ignores_unknown_keys(self):
        d = {"name": "x", "kind": "class", "file_path": "a.py", "start_line": 1, "end_line": 2, "extra": True}
        e = SymbolEntry.from_dict(d)
        assert e.name == "x"


class TestSymbolRegistry:
    """Tests for SymbolRegistry."""

    def test_add_and_size(self):
        reg = SymbolRegistry()
        assert reg.size == 0
        reg.add(_make_entry(name="a"))
        reg.add(_make_entry(name="b"))
        assert reg.size == 2

    def test_add_many(self):
        reg = SymbolRegistry()
        reg.add_many([_make_entry(name="x"), _make_entry(name="y"), _make_entry(name="z")])
        assert reg.size == 3

    def test_remove_file(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(name="a", file_path="f1.py"))
        reg.add(_make_entry(name="b", file_path="f1.py"))
        reg.add(_make_entry(name="c", file_path="f2.py"))
        removed = reg.remove_file("f1.py")
        assert removed == 2
        assert reg.size == 1
        assert reg.find_by_file("f1.py") == []

    def test_remove_file_nonexistent(self):
        reg = SymbolRegistry()
        assert reg.remove_file("no.py") == 0

    def test_clear(self):
        reg = SymbolRegistry()
        reg.add_many([_make_entry(), _make_entry()])
        reg.clear()
        assert reg.size == 0

    def test_files(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(file_path="a.py"))
        reg.add(_make_entry(file_path="b.py"))
        assert sorted(reg.files) == ["a.py", "b.py"]

    def test_find_by_name(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(name="foo"))
        reg.add(_make_entry(name="bar"))
        reg.add(_make_entry(name="foo", file_path="other.py"))
        assert len(reg.find_by_name("foo")) == 2
        assert len(reg.find_by_name("bar")) == 1
        assert len(reg.find_by_name("baz")) == 0

    def test_find_by_kind(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(kind="function"))
        reg.add(_make_entry(kind="class"))
        reg.add(_make_entry(kind="function"))
        assert len(reg.find_by_kind("function")) == 2
        assert len(reg.find_by_kind("class")) == 1

    def test_find_by_file(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(file_path="a.py"))
        reg.add(_make_entry(file_path="b.py"))
        reg.add(_make_entry(file_path="a.py"))
        assert len(reg.find_by_file("a.py")) == 2

    def test_find_multi_criteria(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(name="f", kind="function", language="python"))
        reg.add(_make_entry(name="f", kind="method", language="python"))
        reg.add(_make_entry(name="g", kind="function", language="javascript"))
        # name + kind
        assert len(reg.find(name="f", kind="function")) == 1
        # language only
        assert len(reg.find(language="python")) == 2
        # no criteria → all
        assert len(reg.find()) == 3

    def test_find_with_parent(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(name="method1", parent="ClassA"))
        reg.add(_make_entry(name="method2", parent="ClassB"))
        assert len(reg.find(parent="ClassA")) == 1

    def test_search_name(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(name="calculate_total"))
        reg.add(_make_entry(name="get_customer"))
        reg.add(_make_entry(name="recalculate"))
        results = reg.search_name("calc")
        assert len(results) == 2  # calculate_total and recalculate

    def test_search_name_case_insensitive(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(name="MyClass"))
        results = reg.search_name("myclass")
        assert len(results) == 1

    def test_language_summary(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(language="python"))
        reg.add(_make_entry(language="python"))
        reg.add(_make_entry(language="javascript"))
        summary = reg.language_summary()
        assert summary["python"] == 2
        assert summary["javascript"] == 1

    def test_kind_summary(self):
        reg = SymbolRegistry()
        reg.add(_make_entry(kind="function"))
        reg.add(_make_entry(kind="class"))
        reg.add(_make_entry(kind="function"))
        summary = reg.kind_summary()
        assert summary["function"] == 2
        assert summary["class"] == 1

    def test_save_and_load(self, tmp_path: Path):
        reg = SymbolRegistry()
        reg.add(_make_entry(name="func1", kind="function", language="python"))
        reg.add(_make_entry(name="Cls1", kind="class", language="python"))
        reg.save(tmp_path)

        assert (tmp_path / REGISTRY_FILE).exists()

        loaded = SymbolRegistry.load(tmp_path)
        assert loaded.size == 2
        assert len(loaded.find_by_name("func1")) == 1
        assert loaded.find_by_name("Cls1")[0].kind == "class"

    def test_load_returns_empty_when_missing(self, tmp_path: Path):
        reg = SymbolRegistry.load(tmp_path)
        assert reg.size == 0

    def test_load_handles_corrupt_json(self, tmp_path: Path):
        (tmp_path / REGISTRY_FILE).write_text("not json", encoding="utf-8")
        reg = SymbolRegistry.load(tmp_path)
        assert reg.size == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3 — IndexStats
# ═══════════════════════════════════════════════════════════════════════════


class TestLanguageCoverage:
    """Tests for LanguageCoverage dataclass."""

    def test_defaults(self):
        lc = LanguageCoverage()
        assert lc.language == ""
        assert lc.files == 0
        assert lc.chunks == 0
        assert lc.symbols == 0
        assert lc.total_lines == 0

    def test_to_dict_and_from_dict(self):
        lc = LanguageCoverage(language="python", files=5, chunks=20, symbols=15, total_lines=300)
        d = lc.to_dict()
        lc2 = LanguageCoverage.from_dict(d)
        assert lc2.language == "python"
        assert lc2.files == 5
        assert lc2.total_lines == 300


class TestIndexStats:
    """Tests for IndexStats."""

    def test_defaults(self):
        s = IndexStats()
        assert s.total_files == 0
        assert s.total_chunks == 0
        assert s.total_symbols == 0
        assert s.total_vectors == 0
        assert s.language_coverage == []

    def test_staleness_seconds_zero_when_not_indexed(self):
        s = IndexStats()
        assert s.staleness_seconds == 0.0

    def test_staleness_seconds_positive(self):
        s = IndexStats(last_indexed_at=time.time() - 100)
        assert s.staleness_seconds >= 99.0

    def test_languages_property(self):
        s = IndexStats(language_coverage=[
            LanguageCoverage(language="python"),
            LanguageCoverage(language="javascript"),
        ])
        assert s.languages == ["python", "javascript"]

    def test_get_language(self):
        s = IndexStats(language_coverage=[
            LanguageCoverage(language="python", files=3),
        ])
        assert s.get_language("python") is not None
        assert s.get_language("python").files == 3
        assert s.get_language("rust") is None

    def test_set_language_add_new(self):
        s = IndexStats()
        s.set_language(LanguageCoverage(language="go", files=2))
        assert len(s.language_coverage) == 1
        assert s.get_language("go").files == 2

    def test_set_language_replace_existing(self):
        s = IndexStats(language_coverage=[LanguageCoverage(language="go", files=1)])
        s.set_language(LanguageCoverage(language="go", files=5))
        assert len(s.language_coverage) == 1
        assert s.get_language("go").files == 5

    def test_to_dict_and_from_dict(self):
        s = IndexStats(
            total_files=10,
            total_chunks=50,
            total_symbols=30,
            embedding_model="test-model",
            language_coverage=[
                LanguageCoverage(language="python", files=7, chunks=35),
            ],
        )
        d = s.to_dict()
        s2 = IndexStats.from_dict(d)
        assert s2.total_files == 10
        assert s2.embedding_model == "test-model"
        assert len(s2.language_coverage) == 1
        assert s2.language_coverage[0].language == "python"

    def test_save_and_load(self, tmp_path: Path):
        s = IndexStats(
            total_files=8,
            total_chunks=40,
            last_indexed_at=time.time(),
            language_coverage=[LanguageCoverage(language="python", files=8, chunks=40)],
        )
        s.save(tmp_path)
        assert (tmp_path / STATS_FILE).exists()

        loaded = IndexStats.load(tmp_path)
        assert loaded is not None
        assert loaded.total_files == 8
        assert len(loaded.language_coverage) == 1

    def test_load_returns_none_when_missing(self, tmp_path: Path):
        assert IndexStats.load(tmp_path) is None

    def test_load_returns_none_on_corrupt_json(self, tmp_path: Path):
        (tmp_path / STATS_FILE).write_text("broken", encoding="utf-8")
        assert IndexStats.load(tmp_path) is None


# ═══════════════════════════════════════════════════════════════════════════
# 4 — QueryHistory
# ═══════════════════════════════════════════════════════════════════════════


class TestQueryRecord:
    """Tests for QueryRecord dataclass."""

    def test_defaults(self):
        r = QueryRecord(query="test")
        assert r.query == "test"
        assert r.timestamp == 0.0
        assert r.result_count == 0
        assert r.languages == []
        assert r.top_files == []

    def test_to_dict_and_from_dict(self):
        r = QueryRecord(query="hello", result_count=5, top_score=0.95, languages=["python"])
        d = r.to_dict()
        r2 = QueryRecord.from_dict(d)
        assert r2.query == "hello"
        assert r2.result_count == 5
        assert r2.top_score == 0.95


class TestQueryHistory:
    """Tests for QueryHistory."""

    def test_record_and_size(self):
        h = QueryHistory()
        assert h.size == 0
        h.record("query1", result_count=3)
        h.record("query2", result_count=5)
        assert h.size == 2

    def test_record_returns_query_record(self):
        h = QueryHistory()
        r = h.record("test", result_count=2, top_score=0.8, languages=["python"])
        assert isinstance(r, QueryRecord)
        assert r.query == "test"
        assert r.result_count == 2
        assert r.timestamp > 0

    def test_recent(self):
        h = QueryHistory()
        for i in range(20):
            h.record(f"q{i}")
        recent = h.recent(5)
        assert len(recent) == 5
        assert recent[-1].query == "q19"
        assert recent[0].query == "q15"

    def test_popular_queries(self):
        h = QueryHistory()
        h.record("foo")
        h.record("bar")
        h.record("foo")
        h.record("foo")
        h.record("bar")
        popular = h.popular_queries(2)
        assert popular[0] == ("foo", 3)
        assert popular[1] == ("bar", 2)

    def test_popular_files(self):
        h = QueryHistory()
        h.record("q1", top_files=["a.py", "b.py"])
        h.record("q2", top_files=["a.py", "c.py"])
        h.record("q3", top_files=["a.py"])
        popular = h.popular_files(2)
        assert popular[0] == ("a.py", 3)

    def test_avg_result_count(self):
        h = QueryHistory()
        h.record("q1", result_count=10)
        h.record("q2", result_count=20)
        assert h.avg_result_count() == 15.0

    def test_avg_result_count_empty(self):
        h = QueryHistory()
        assert h.avg_result_count() == 0.0

    def test_fifo_eviction(self):
        h = QueryHistory(max_entries=3)
        h.record("a")
        h.record("b")
        h.record("c")
        h.record("d")  # evicts "a"
        assert h.size == 3
        queries = [r.query for r in h.records]
        assert "a" not in queries
        assert "d" in queries

    def test_clear(self):
        h = QueryHistory()
        h.record("x")
        h.record("y")
        h.clear()
        assert h.size == 0

    def test_save_and_load(self, tmp_path: Path):
        h = QueryHistory()
        h.record("search1", result_count=3, top_score=0.9, languages=["python"])
        h.record("search2", result_count=5, top_files=["main.py"])
        h.save(tmp_path)

        assert (tmp_path / HISTORY_FILE).exists()

        loaded = QueryHistory.load(tmp_path)
        assert loaded.size == 2
        assert loaded.records[0].query == "search1"
        assert loaded.records[1].top_files == ["main.py"]

    def test_load_returns_empty_when_missing(self, tmp_path: Path):
        h = QueryHistory.load(tmp_path)
        assert h.size == 0

    def test_load_handles_corrupt_json(self, tmp_path: Path):
        (tmp_path / HISTORY_FILE).write_text("not json", encoding="utf-8")
        h = QueryHistory.load(tmp_path)
        assert h.size == 0


# ═══════════════════════════════════════════════════════════════════════════
# 5 — Indexing integration (manifest, registry, stats populated)
# ═══════════════════════════════════════════════════════════════════════════


class TestIndexingIntegration:
    """Verify that run_indexing populates manifest, registry, and stats."""

    @pytest.fixture()
    def project(self, tmp_path: Path):
        """Create a minimal Python project for indexing."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.py").write_text(
            'def greet(name):\n    return f"Hello, {name}!"\n\nclass Greeter:\n    def say_hi(self):\n        pass\n',
            encoding="utf-8",
        )
        (src / "utils.py").write_text(
            "def add(a, b):\n    return a + b\n",
            encoding="utf-8",
        )
        # Config file
        (tmp_path / ".codexa.yaml").write_text(
            "index:\n  ignore_dirs: []\n  extensions: ['.py']\n",
            encoding="utf-8",
        )
        return tmp_path

    @patch("semantic_code_intelligence.services.indexing_service.generate_embeddings")
    @patch("semantic_code_intelligence.services.indexing_service.scan_repository")
    def test_indexing_populates_manifest(self, mock_scan, mock_embed, project, tmp_path):
        from semantic_code_intelligence.indexing.scanner import ScannedFile
        from semantic_code_intelligence.services.indexing_service import run_indexing

        mock_scan.return_value = [
            ScannedFile(
                path=project / "src" / "hello.py",
                relative_path="src/hello.py",
                extension=".py",
                size_bytes=80,
                content_hash="abc123",
            ),
        ]
        mock_embed.return_value = np.random.rand(1, 384).astype(np.float32)

        result = run_indexing(project)
        index_dir = project / ".codexa" / "index"
        manifest = IndexManifest.load(index_dir)

        assert manifest is not None
        assert manifest.total_files >= 1
        assert manifest.total_chunks >= 1
        assert manifest.created_at > 0.0
        assert manifest.updated_at > 0.0

    @patch("semantic_code_intelligence.services.indexing_service.generate_embeddings")
    @patch("semantic_code_intelligence.services.indexing_service.scan_repository")
    def test_indexing_populates_symbol_registry(self, mock_scan, mock_embed, project):
        from semantic_code_intelligence.indexing.scanner import ScannedFile
        from semantic_code_intelligence.services.indexing_service import run_indexing

        mock_scan.return_value = [
            ScannedFile(
                path=project / "src" / "hello.py",
                relative_path="src/hello.py",
                extension=".py",
                size_bytes=80,
                content_hash="abc123",
            ),
        ]
        mock_embed.return_value = np.random.rand(1, 384).astype(np.float32)

        result = run_indexing(project)
        index_dir = project / ".codexa" / "index"
        reg = SymbolRegistry.load(index_dir)

        assert reg.size > 0
        assert result.symbols_extracted > 0

    @patch("semantic_code_intelligence.services.indexing_service.generate_embeddings")
    @patch("semantic_code_intelligence.services.indexing_service.scan_repository")
    def test_indexing_populates_stats(self, mock_scan, mock_embed, project):
        from semantic_code_intelligence.indexing.scanner import ScannedFile
        from semantic_code_intelligence.services.indexing_service import run_indexing

        mock_scan.return_value = [
            ScannedFile(
                path=project / "src" / "hello.py",
                relative_path="src/hello.py",
                extension=".py",
                size_bytes=80,
                content_hash="abc123",
            ),
        ]
        mock_embed.return_value = np.random.rand(1, 384).astype(np.float32)

        result = run_indexing(project)
        index_dir = project / ".codexa" / "index"
        stats = IndexStats.load(index_dir)

        assert stats is not None
        assert stats.total_files >= 1
        assert stats.total_chunks >= 1
        assert stats.last_indexed_at > 0.0
        assert stats.indexing_duration_seconds >= 0.0
        assert stats.embedding_model != ""

    @patch("semantic_code_intelligence.services.indexing_service.generate_embeddings")
    @patch("semantic_code_intelligence.services.indexing_service.scan_repository")
    def test_indexing_result_includes_symbols(self, mock_scan, mock_embed, project):
        from semantic_code_intelligence.indexing.scanner import ScannedFile
        from semantic_code_intelligence.services.indexing_service import run_indexing

        mock_scan.return_value = [
            ScannedFile(
                path=project / "src" / "hello.py",
                relative_path="src/hello.py",
                extension=".py",
                size_bytes=80,
                content_hash="abc123",
            ),
        ]
        mock_embed.return_value = np.random.rand(1, 384).astype(np.float32)

        result = run_indexing(project)
        assert result.symbols_extracted >= 0
        assert "symbols=" in repr(result)


# ═══════════════════════════════════════════════════════════════════════════
# 6 — Search integration (query history recorded)
# ═══════════════════════════════════════════════════════════════════════════


class TestSearchIntegration:
    """Verify that search_codebase records query history."""

    @patch("semantic_code_intelligence.services.search_service.generate_embeddings")
    @patch("semantic_code_intelligence.services.search_service.VectorStore.load")
    def test_search_records_query_history(self, mock_load, mock_embed, tmp_path):
        from semantic_code_intelligence.services.search_service import search_codebase

        # Set up mock vector store
        store = MagicMock()
        meta = MagicMock()
        meta.file_path = "src/main.py"
        meta.start_line = 1
        meta.end_line = 10
        meta.language = "python"
        meta.content = "def hello(): pass"
        meta.chunk_index = 0
        store.search.return_value = [(meta, 0.95)]
        store.size = 1
        mock_load.return_value = store

        mock_embed.return_value = np.random.rand(1, 384).astype(np.float32)

        # Create required config and index dir
        (tmp_path / ".codexa.yaml").write_text("", encoding="utf-8")
        index_dir = tmp_path / ".codexa" / "index"
        index_dir.mkdir(parents=True, exist_ok=True)

        results = search_codebase("hello world", tmp_path, top_k=5, threshold=0.1)

        # Verify history was recorded
        history = QueryHistory.load(index_dir)
        assert history.size == 1
        assert history.records[0].query == "hello world"
        assert history.records[0].result_count == 1

    @patch("semantic_code_intelligence.services.search_service.generate_embeddings")
    @patch("semantic_code_intelligence.services.search_service.VectorStore.load")
    def test_search_records_empty_results(self, mock_load, mock_embed, tmp_path):
        from semantic_code_intelligence.services.search_service import search_codebase

        store = MagicMock()
        store.search.return_value = []
        store.size = 1
        mock_load.return_value = store

        mock_embed.return_value = np.random.rand(1, 384).astype(np.float32)

        (tmp_path / ".codexa.yaml").write_text("", encoding="utf-8")
        index_dir = tmp_path / ".codexa" / "index"
        index_dir.mkdir(parents=True, exist_ok=True)

        results = search_codebase("nonexistent query", tmp_path, top_k=5, threshold=0.1)

        history = QueryHistory.load(index_dir)
        assert history.size == 1
        assert history.records[0].result_count == 0
        assert history.records[0].top_score == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 7 — Module imports and version
# ═══════════════════════════════════════════════════════════════════════════


class TestModuleImports:
    """Verify modules import cleanly."""

    def test_import_index_manifest(self):
        from semantic_code_intelligence.storage.index_manifest import MANIFEST_FILE, IndexManifest
        assert IndexManifest is not None
        assert MANIFEST_FILE == "index_manifest.json"

    def test_import_symbol_registry(self):
        from semantic_code_intelligence.storage.symbol_registry import SymbolEntry, SymbolRegistry
        assert SymbolEntry is not None
        assert SymbolRegistry is not None

    def test_import_index_stats(self):
        from semantic_code_intelligence.storage.index_stats import IndexStats, LanguageCoverage
        assert IndexStats is not None
        assert LanguageCoverage is not None

    def test_import_query_history(self):
        from semantic_code_intelligence.storage.query_history import QueryHistory, QueryRecord
        assert QueryHistory is not None
        assert QueryRecord is not None

    def test_version(self):
        from semantic_code_intelligence import __version__
        assert __version__ == "0.5.0"

    def test_indexing_result_has_symbols_field(self):
        from semantic_code_intelligence.services.indexing_service import IndexingResult
        r = IndexingResult()
        assert hasattr(r, "symbols_extracted")
        assert r.symbols_extracted == 0

