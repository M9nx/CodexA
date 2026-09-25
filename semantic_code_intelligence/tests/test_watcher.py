"""Tests for the daemon/watcher subsystem."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from semantic_code_intelligence.daemon import watcher as watcher_module
from semantic_code_intelligence.daemon.watcher import (
    AsyncIndexer,
    FileChangeEvent,
    FileWatcher,
    IndexingDaemon,
    NativeFileWatcher,
)


# Threads the watcher subsystem is allowed to run. A clean stop() must leave
# none of them behind; a leaked daemon thread keeps a filesystem watch (and its
# file descriptors) alive for the rest of the process.
WATCHER_THREAD_NAMES = (
    "codexa-watcher",
    "codexa-native-watcher",
    "codexa-indexer",
)


def _live_watcher_threads() -> list[str]:
    return sorted(
        t.name for t in threading.enumerate() if t.name in WATCHER_THREAD_NAMES
    )


def _wait_until_gone(names: tuple[str, ...], timeout: float = 5.0) -> list[str]:
    """Poll until no watcher thread of the given names is alive.

    stop() joins with a timeout, so a thread can briefly outlive the call. This
    replaces a fixed sleep with a condition and fails loudly if it never clears.
    """
    deadline = time.monotonic() + timeout
    live = _live_watcher_threads()
    while live and time.monotonic() < deadline:
        time.sleep(0.02)
        live = _live_watcher_threads()
    return [n for n in names if n in live]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal initialised project root."""
    config_dir = tmp_path / ".codexa"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{}", encoding="utf-8")
    return tmp_path


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
        # Create minimal codexa config
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        assert not watcher.is_running

    def test_callback_registration(self, tmp_path):
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        events_received = []
        watcher.on_change(lambda e: events_received.append(e))
        assert len(watcher._callbacks) == 1

    def test_scan_once_baseline(self, tmp_path):
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")
        (tmp_path / "file.py").write_text("x = 1", encoding="utf-8")

        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        # First scan is baseline
        events = watcher.scan_once()
        assert events == []

    def test_scan_once_detects_new_file(self, tmp_path):
        config_dir = tmp_path / ".codexa"
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
        config_dir = tmp_path / ".codexa"
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
        config_dir = tmp_path / ".codexa"
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
        watcher = FileWatcher(tmp_path, poll_interval=0.1)
        watcher.start()
        try:
            assert watcher.is_running
        finally:
            watcher.stop()
        assert not watcher.is_running
        assert _wait_until_gone(("codexa-watcher",)) == []

    def test_repeated_start_stop_leaks_no_threads(self, tmp_path):
        """A clean stop must not accumulate watcher threads."""
        for _ in range(3):
            watcher = FileWatcher(tmp_path, poll_interval=0.1)
            watcher.start()
            watcher.stop()
        assert _wait_until_gone(("codexa-watcher",)) == []


# ---------------------------------------------------------------------------
# AsyncIndexer
# ---------------------------------------------------------------------------

class TestAsyncIndexer:
    @pytest.mark.integration
    def test_init(self, tmp_path):
        indexer = AsyncIndexer(tmp_path)
        assert indexer.pending_count == 0
        assert indexer.tasks_processed == 0

    @pytest.mark.integration
    def test_enqueue(self, tmp_path):
        indexer = AsyncIndexer(tmp_path)
        indexer.enqueue(["file1.py", "file2.py"])
        assert indexer.pending_count == 1

    @pytest.mark.integration
    def test_enqueue_multiple(self, tmp_path):
        indexer = AsyncIndexer(tmp_path)
        indexer.enqueue(["f1.py"])
        indexer.enqueue(["f2.py"])
        assert indexer.pending_count == 2

    @pytest.mark.integration
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
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path)
        assert not daemon.is_running

    def test_get_status(self, tmp_path):
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path)
        status = daemon.get_status()
        assert "running" in status
        assert status["running"] is False
        assert "events_recorded" in status

    def test_event_log(self, tmp_path):
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path)
        assert daemon.event_log == []

    def test_start_stop(self, tmp_path):
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path)
        daemon.start()
        try:
            assert daemon.is_running
        finally:
            daemon.stop()
        assert not daemon.is_running
        assert _wait_until_gone(WATCHER_THREAD_NAMES) == []

    def test_native_watcher_thread_actually_stops(self, tmp_path):
        """Regression: the native watch thread must not outlive stop().

        stop() used to join with a timeout and then drop the thread reference
        while the thread was still watching the filesystem, so is_running
        reported False while the watch was live.
        """
        pytest.importorskip("watchfiles")
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        watcher = NativeFileWatcher(tmp_path, debounce=0.05)
        watcher.start()
        try:
            assert watcher.is_running
        finally:
            watcher.stop()
        assert not watcher.is_running
        assert _wait_until_gone(("codexa-native-watcher",)) == []

    def test_daemon_falls_back_to_polling_without_watchfiles(
        self, tmp_path, monkeypatch
    ):
        """The polling fallback is the path used when watchfiles is absent."""
        monkeypatch.setattr(watcher_module, "_HAS_WATCHFILES", False)
        config_dir = tmp_path / ".codexa"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")

        daemon = IndexingDaemon(tmp_path, poll_interval=0.1)
        assert isinstance(daemon._watcher, FileWatcher)

        daemon.start()
        try:
            assert daemon.is_running
        finally:
            daemon.stop()
        assert not daemon.is_running
        assert _wait_until_gone(("codexa-watcher", "codexa-indexer")) == []
