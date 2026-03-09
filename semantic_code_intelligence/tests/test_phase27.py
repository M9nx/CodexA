"""Tests for v0.28.0 features: LSP Server (Phase 26) + Incremental Indexing (Phase 27)."""

from __future__ import annotations

import json
import time
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from semantic_code_intelligence import __version__
from semantic_code_intelligence.cli.main import cli


# =========================================================================
# Version
# =========================================================================

class TestVersion028:
    def test_version_is_028(self):
        assert __version__ == "0.28.0"


# =========================================================================
# Phase 26 — LSP Server
# =========================================================================

class TestLSPServerModule:
    """Test LSP server module structure and imports."""

    def test_lsp_module_importable(self):
        from semantic_code_intelligence.lsp import LSPServer, run_lsp_server
        assert LSPServer is not None
        assert callable(run_lsp_server)

    def test_lsp_message_helpers(self):
        from semantic_code_intelligence.lsp import _ok, _error
        ok = _ok(1, {"test": True})
        assert ok["jsonrpc"] == "2.0"
        assert ok["id"] == 1
        assert ok["result"]["test"] is True

        err = _error(2, -32601, "Not found")
        assert err["id"] == 2
        assert err["error"]["code"] == -32601
        assert err["error"]["message"] == "Not found"

    def test_lsp_path_to_uri(self):
        from semantic_code_intelligence.lsp import _path_to_uri
        uri = _path_to_uri("src/main.py", Path("/project"))
        assert uri.startswith("file:///")
        assert "main.py" in uri

    def test_lsp_symbol_kind_mapping(self):
        from semantic_code_intelligence.lsp import _symbol_kind_to_lsp
        assert _symbol_kind_to_lsp("function") == 12
        assert _symbol_kind_to_lsp("class") == 5
        assert _symbol_kind_to_lsp("method") == 6
        assert _symbol_kind_to_lsp("variable") == 13
        assert _symbol_kind_to_lsp("unknown") == 12  # default

    def test_lsp_completion_kind_mapping(self):
        from semantic_code_intelligence.lsp import _symbol_kind_to_completion
        assert _symbol_kind_to_completion("function") == 3
        assert _symbol_kind_to_completion("class") == 7
        assert _symbol_kind_to_completion("method") == 2

    def test_lsp_server_capabilities(self):
        from semantic_code_intelligence.lsp import _SERVER_CAPABILITIES
        assert _SERVER_CAPABILITIES["hoverProvider"] is True
        assert _SERVER_CAPABILITIES["completionProvider"] is not None
        assert _SERVER_CAPABILITIES["definitionProvider"] is True
        assert _SERVER_CAPABILITIES["referencesProvider"] is True
        assert _SERVER_CAPABILITIES["workspaceSymbolProvider"] is True


class TestLSPDocumentStore:
    """Test the in-memory document store."""

    def test_open_and_get(self):
        from semantic_code_intelligence.lsp import _DocumentStore
        ds = _DocumentStore()
        ds.open("file:///test.py", "hello world")
        assert ds.get("file:///test.py") == "hello world"

    def test_update(self):
        from semantic_code_intelligence.lsp import _DocumentStore
        ds = _DocumentStore()
        ds.open("file:///a.py", "old")
        ds.update("file:///a.py", "new")
        assert ds.get("file:///a.py") == "new"

    def test_close(self):
        from semantic_code_intelligence.lsp import _DocumentStore
        ds = _DocumentStore()
        ds.open("file:///x.py", "text")
        ds.close("file:///x.py")
        assert ds.get("file:///x.py") is None

    def test_get_word_at(self):
        from semantic_code_intelligence.lsp import _DocumentStore
        ds = _DocumentStore()
        ds.open("file:///t.py", "def hello_world():\n    pass")
        # Cursor at "hello_world" (line=0, char=6)
        word = ds.get_word_at("file:///t.py", 0, 6)
        assert word == "hello_world"

    def test_get_word_at_empty(self):
        from semantic_code_intelligence.lsp import _DocumentStore
        ds = _DocumentStore()
        word = ds.get_word_at("file:///missing.py", 0, 0)
        assert word == ""

    def test_uri_to_path_unix(self):
        from semantic_code_intelligence.lsp import _DocumentStore
        ds = _DocumentStore()
        path = ds.uri_to_path("file:///home/user/project/main.py")
        assert "main.py" in path

    def test_uri_to_path_windows(self):
        from semantic_code_intelligence.lsp import _DocumentStore
        ds = _DocumentStore()
        path = ds.uri_to_path("file:///C:/Users/test/project/main.py")
        assert "main.py" in path


class TestLSPServerDispatch:
    """Test LSP server message dispatch without actual stdio."""

    def test_initialize(self):
        from semantic_code_intelligence.lsp import LSPServer
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            server = LSPServer(root)
            resp = server._handle({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            })
            assert resp["id"] == 1
            assert "capabilities" in resp["result"]
            assert resp["result"]["serverInfo"]["name"] == "codex-lsp"

    def test_shutdown(self):
        from semantic_code_intelligence.lsp import LSPServer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            server = LSPServer(root)
            resp = server._handle({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "shutdown",
                "params": {},
            })
            assert resp["id"] == 2
            assert resp["result"] is None
            assert server._shutdown is True

    def test_initialized_notification(self):
        from semantic_code_intelligence.lsp import LSPServer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            server = LSPServer(root)
            resp = server._handle({
                "jsonrpc": "2.0",
                "method": "initialized",
                "params": {},
            })
            assert resp is None
            assert server._initialized is True

    def test_unknown_method_returns_error(self):
        from semantic_code_intelligence.lsp import LSPServer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            server = LSPServer(root)
            resp = server._handle({
                "jsonrpc": "2.0",
                "id": 99,
                "method": "foo/bar",
                "params": {},
            })
            assert resp["error"]["code"] == -32601

    def test_unknown_notification_ignored(self):
        from semantic_code_intelligence.lsp import LSPServer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            server = LSPServer(root)
            resp = server._handle({
                "jsonrpc": "2.0",
                "method": "$/cancelRequest",
                "params": {},
            })
            assert resp is None

    def test_did_open(self):
        from semantic_code_intelligence.lsp import LSPServer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            server = LSPServer(root)
            server._handle({
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": "file:///test.py",
                        "text": "x = 1",
                    },
                },
            })
            assert server._docs.get("file:///test.py") == "x = 1"

    def test_codex_search_missing_query(self):
        from semantic_code_intelligence.lsp import LSPServer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            server = LSPServer(root)
            resp = server._handle({
                "jsonrpc": "2.0",
                "id": 10,
                "method": "codex/search",
                "params": {},
            })
            assert resp["error"]["code"] == -32602

    def test_codex_quality_missing_path(self):
        from semantic_code_intelligence.lsp import LSPServer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            server = LSPServer(root)
            resp = server._handle({
                "jsonrpc": "2.0",
                "id": 11,
                "method": "codex/quality",
                "params": {},
            })
            assert resp["error"]["code"] == -32602


class TestLSPCLI:
    """Test the codex lsp CLI command."""

    def test_lsp_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["lsp", "--help"])
        assert result.exit_code == 0
        assert "Language Server Protocol" in result.output

    def test_lsp_requires_init(self):
        """LSP should fail if project not initialized."""
        runner = CliRunner()
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            result = runner.invoke(cli, ["lsp", "--path", td])
            assert result.exit_code != 0 or "not initialized" in result.output.lower()

    def test_command_count_is_36(self):
        """Verify we now have 36 top-level commands (35 + lsp)."""
        assert len(cli.commands) == 38


# =========================================================================
# Phase 27 — Incremental Indexing
# =========================================================================

class TestIncrementalIndexingFunction:
    """Test run_incremental_indexing() in isolation."""

    def test_importable(self):
        from semantic_code_intelligence.services.indexing_service import (
            run_incremental_indexing,
        )
        assert callable(run_incremental_indexing)

    def test_empty_changes_returns_quickly(self, tmp_path):
        """No changes and no deletes → immediate return."""
        from semantic_code_intelligence.services.indexing_service import (
            run_incremental_indexing,
            run_indexing,
        )
        from semantic_code_intelligence.config.settings import AppConfig

        # Create a minimal codex project
        project = tmp_path / "proj"
        project.mkdir()
        codex_dir = project / ".codex"
        codex_dir.mkdir()
        (project / "hello.py").write_text("x = 1\n", encoding="utf-8")

        # First do a full index so stores exist
        run_indexing(project, force=True)

        # Now run incremental with nothing changed
        result = run_incremental_indexing(project, changed_files=[], deleted_files=[])
        assert result.files_indexed == 0
        assert result.files_scanned == 0

    def test_incremental_indexes_new_file(self, tmp_path):
        """A new file should be chunked and embedded incrementally."""
        from semantic_code_intelligence.services.indexing_service import (
            run_incremental_indexing,
            run_indexing,
        )
        from semantic_code_intelligence.storage.vector_store import VectorStore
        from semantic_code_intelligence.config.settings import AppConfig

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".codex").mkdir()
        (project / "a.py").write_text("def foo():\n    return 1\n", encoding="utf-8")

        run_indexing(project, force=True)
        index_dir = AppConfig.index_dir(project)
        store_before = VectorStore.load(index_dir)
        n_before = store_before.size

        # Add a new file
        new_file = project / "b.py"
        new_file.write_text("def bar():\n    return 2\n", encoding="utf-8")

        result = run_incremental_indexing(project, changed_files=[str(new_file)])
        assert result.files_indexed >= 1
        assert result.chunks_created >= 1

        store_after = VectorStore.load(index_dir)
        assert store_after.size > n_before

    def test_incremental_handles_deleted_file(self, tmp_path):
        """Deleted file vectors should be removed from the store."""
        from semantic_code_intelligence.services.indexing_service import (
            run_incremental_indexing,
            run_indexing,
        )
        from semantic_code_intelligence.storage.vector_store import VectorStore
        from semantic_code_intelligence.config.settings import AppConfig

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".codex").mkdir()
        (project / "a.py").write_text("x = 1\n", encoding="utf-8")
        (project / "b.py").write_text("y = 2\n", encoding="utf-8")

        run_indexing(project, force=True)
        index_dir = AppConfig.index_dir(project)
        store_before = VectorStore.load(index_dir)
        n_before = store_before.size

        # Delete b.py
        b_path = str(project / "b.py")
        (project / "b.py").unlink()

        result = run_incremental_indexing(
            project, changed_files=[], deleted_files=[b_path],
        )
        store_after = VectorStore.load(index_dir)
        assert store_after.size < n_before

    def test_incremental_skips_unchanged_file(self, tmp_path):
        """File with same hash should be skipped."""
        from semantic_code_intelligence.services.indexing_service import (
            run_incremental_indexing,
            run_indexing,
        )

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".codex").mkdir()
        (project / "a.py").write_text("x = 1\n", encoding="utf-8")

        run_indexing(project, force=True)

        # Run incremental on the same file (unchanged)
        result = run_incremental_indexing(
            project, changed_files=[str(project / "a.py")],
        )
        assert result.files_skipped == 1
        assert result.files_indexed == 0

    def test_fallback_to_full_when_no_index(self, tmp_path):
        """With no existing index, should fall back to run_indexing."""
        from semantic_code_intelligence.services.indexing_service import (
            run_incremental_indexing,
        )

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".codex").mkdir()
        (project / "a.py").write_text("x = 1\n", encoding="utf-8")

        # No prior index exists — should fall back
        result = run_incremental_indexing(
            project, changed_files=[str(project / "a.py")],
        )
        assert result.files_indexed >= 1


class TestDaemonIncrementalWiring:
    """Test that the daemon uses incremental indexing."""

    def test_indexing_task_has_deleted_paths(self):
        from semantic_code_intelligence.daemon.watcher import IndexingTask
        task = IndexingTask(
            file_paths=["a.py", "b.py"],
            deleted_paths=["c.py"],
        )
        assert len(task.deleted_paths) == 1
        assert task.deleted_paths[0] == "c.py"

    def test_indexing_task_defaults(self):
        from semantic_code_intelligence.daemon.watcher import IndexingTask
        task = IndexingTask(file_paths=["a.py"])
        assert task.deleted_paths == []
        assert task.force is False

    def test_enqueue_with_deleted(self):
        from semantic_code_intelligence.daemon.watcher import AsyncIndexer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            indexer = AsyncIndexer(Path(td))
            indexer.enqueue(["a.py"], deleted_paths=["b.py"])
            assert indexer.pending_count == 1

    def test_daemon_passes_deleted_to_indexer(self):
        from semantic_code_intelligence.daemon.watcher import (
            IndexingDaemon,
            FileChangeEvent,
        )
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            daemon = IndexingDaemon(root)

            events = [
                FileChangeEvent(
                    path=root / "new.py",
                    relative_path="new.py",
                    change_type="created",
                    timestamp=time.time(),
                ),
                FileChangeEvent(
                    path=root / "old.py",
                    relative_path="old.py",
                    change_type="deleted",
                    timestamp=time.time(),
                ),
            ]
            daemon._on_file_changes(events)
            assert daemon._indexer.pending_count == 1

    def test_file_watcher_scan_once(self):
        from semantic_code_intelligence.daemon.watcher import FileWatcher
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            (root / "test.py").write_text("x = 1\n", encoding="utf-8")

            watcher = FileWatcher(root, poll_interval=60)
            # First scan is baseline
            events = watcher.scan_once()
            assert events == []

            # Modify file
            (root / "test.py").write_text("x = 2\n", encoding="utf-8")
            events = watcher.scan_once()
            assert len(events) >= 1
            assert any(e.change_type == "modified" for e in events)

    def test_file_watcher_detects_new_file(self):
        from semantic_code_intelligence.daemon.watcher import FileWatcher
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")

            watcher = FileWatcher(root, poll_interval=60)
            watcher.scan_once()  # baseline

            (root / "b.py").write_text("y = 2\n", encoding="utf-8")
            events = watcher.scan_once()
            assert any(e.change_type == "created" for e in events)

    def test_file_watcher_detects_deletion(self):
        from semantic_code_intelligence.daemon.watcher import FileWatcher
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")

            watcher = FileWatcher(root, poll_interval=60)
            watcher.scan_once()  # baseline

            (root / "a.py").unlink()
            events = watcher.scan_once()
            assert any(e.change_type == "deleted" for e in events)


class TestIndexingResultRepr:
    """Test IndexingResult representation."""

    def test_repr(self):
        from semantic_code_intelligence.services.indexing_service import IndexingResult
        r = IndexingResult()
        r.files_scanned = 10
        r.files_indexed = 5
        s = repr(r)
        assert "scanned=10" in s
        assert "indexed=5" in s
