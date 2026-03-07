"""Tests for the daemon/watcher subsystem."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from semantic_code_intelligence.daemon.watcher import (
    AsyncIndexer,
    FileChangeEvent,
    FileWatcher,
    IndexingDaemon,
)


# ---------------------------------------------------------------------------
# FileChangeEvent
# ---------------------------------------------------------------------------

class TestFileChangeEvent:
    def test_creation(self):
        event = FileChangeEvent(
            path=Path("/tmp/test.py"),
            relative_path="test.py",
            change_type="created",
            timestamp=1000.0,
        )
        assert event.change_type == "created"
        assert event.relative_path == "test.py"

    def test_to_dict(self):
        event = FileChangeEvent(
            path=Path("/tmp/test.py"),
            relative_path="test.py",
            change_type="modified",
            timestamp=123.0,
        )
        d = event.to_dict()
        assert d["change_type"] == "modified"
        assert d["relative_path"] == "test.py"
        assert d["timestamp"] == 123.0


# ---------------------------------------------------------------------------
# FileWatcher
# ---------------------------------------------------------------------------

class TestFileWatcher:
    def test_init(self, tmp_path):
        # Create minimal codex config
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        assert not watcher.is_running

    def test_callback_registration(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        events_received = []
        watcher.on_change(lambda e: events_received.append(e))
        assert len(watcher._callbacks) == 1

    def test_scan_once_baseline(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")
        (tmp_path / "file.py").write_text("x = 1", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        # First scan is baseline
        events = watcher.scan_once()
        assert events == []

    def test_scan_once_detects_new_file(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")
        (tmp_path / "file.py").write_text("x = 1", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        watcher.scan_once()  # baseline

        # Add a new file
        (tmp_path / "file2.py").write_text("y = 2", encoding="utf-8")
        events = watcher.scan_once()
        assert any(e.change_type == "created" for e in events)

    def test_scan_once_detects_modification(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")
        f = tmp_path / "file.py"
        f.write_text("x = 1", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        watcher.scan_once()  # baseline

        f.write_text("x = 2", encoding="utf-8")
        events = watcher.scan_once()
        assert any(e.change_type == "modified" for e in events)

    def test_scan_once_detects_deletion(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")
        f = tmp_path / "file.py"
        f.write_text("x = 1", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        watcher.scan_once()  # baseline

        f.unlink()
        events = watcher.scan_once()
        assert any(e.change_type == "deleted" for e in events)

    def test_start_stop(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        watcher.start()
        assert watcher.is_running
        time.sleep(0.3)
        watcher.stop()
        assert not watcher.is_running


# ---------------------------------------------------------------------------
# AsyncIndexer
# ---------------------------------------------------------------------------

class TestAsyncIndexer:
    def test_init(self, tmp_path):
        indexer = AsyncIndexer(tmp_path)
        assert indexer.pending_count == 0
        assert indexer.tasks_processed == 0

    def test_enqueue(self, tmp_path):
        indexer = AsyncIndexer(tmp_path)
        indexer.enqueue(["file1.py", "file2.py"])
        assert indexer.pending_count == 1

    def test_enqueue_multiple(self, tmp_path):
        indexer = AsyncIndexer(tmp_path)
        indexer.enqueue(["f1.py"])
        indexer.enqueue(["f2.py"])
        assert indexer.pending_count == 2

    def test_callbacks(self, tmp_path):
        indexer = AsyncIndexer(tmp_path)
        completed = []
        errors = []
        indexer.set_callbacks(
            on_complete=lambda n: completed.append(n),
            on_error=lambda e: errors.append(e),
        )
        assert indexer._on_complete is not None
        assert indexer._on_error is not None


# ---------------------------------------------------------------------------
# IndexingDaemon
# ---------------------------------------------------------------------------

class TestIndexingDaemon:
    def test_init(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path)
        assert not daemon.is_running

    def test_get_status(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path)
        status = daemon.get_status()
        assert "running" in status
        assert status["running"] is False
        assert "events_recorded" in status

    def test_event_log(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path)
        assert daemon.event_log == []

    def test_start_stop(self, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path)
        daemon.start()
        assert daemon.is_running
        time.sleep(0.3)
        daemon.stop()
        assert not daemon.is_running
