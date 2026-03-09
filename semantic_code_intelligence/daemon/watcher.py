"""Background intelligence subsystem — file watching and async indexing.

Provides:
- FileWatcher: monitors filesystem for changes using polling
- IndexingDaemon: runs incremental indexing in background
- AsyncIndexer: queue-based async indexing pipeline
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.indexing.scanner import compute_file_hash, scan_repository
from semantic_code_intelligence.storage.hash_store import HashStore
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("daemon")


# ---------------------------------------------------------------------------
# File Change Events
# ---------------------------------------------------------------------------

@dataclass
class FileChangeEvent:
    """Represents a detected file change."""

    path: Path
    relative_path: str
    change_type: str  # "created", "modified", "deleted"
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the file change event to a plain dictionary."""
        return {
            "path": str(self.path),
            "relative_path": self.relative_path,
            "change_type": self.change_type,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# File Watcher (polling-based, no external deps)
# ---------------------------------------------------------------------------

class FileWatcher:
    """Polls the filesystem for changes using hash-based detection.

    Uses the existing HashStore infrastructure rather than OS-specific
    watchers, making it portable and consistent with the indexing pipeline.
    """

    def __init__(
        self,
        project_root: Path,
        poll_interval: float = 2.0,
        debounce: float = 0.5,
    ) -> None:
        self._root = project_root.resolve()
        self._poll_interval = poll_interval
        self._debounce = debounce
        self._config = load_config(self._root)
        self._hash_store = HashStore()
        self._running = False
        self._thread: threading.Thread | None = None
        self._callbacks: list[Callable[[list[FileChangeEvent]], None]] = []
        self._lock = threading.Lock()
        self._last_scan_hashes: dict[str, str] = {}

    @property
    def is_running(self) -> bool:
        """Whether the file watcher is currently polling."""
        return self._running

    def on_change(self, callback: Callable[[list[FileChangeEvent]], None]) -> None:
        """Register a callback for file change events.

        The callback receives a list of FileChangeEvent objects.
        """
        self._callbacks.append(callback)

    def _initial_scan(self) -> None:
        """Perform initial scan to populate baseline hashes."""
        scanned = scan_repository(self._root, self._config.index)
        with self._lock:
            for sf in scanned:
                self._last_scan_hashes[sf.relative_path] = sf.content_hash

    def _detect_changes(self) -> list[FileChangeEvent]:
        """Scan repository and detect changes since last poll."""
        scanned = scan_repository(self._root, self._config.index)
        current_hashes: dict[str, str] = {}
        events: list[FileChangeEvent] = []
        now = time.time()

        for sf in scanned:
            current_hashes[sf.relative_path] = sf.content_hash

        with self._lock:
            # Check for new or modified files
            for rel_path, new_hash in current_hashes.items():
                old_hash = self._last_scan_hashes.get(rel_path)
                if old_hash is None:
                    events.append(FileChangeEvent(
                        path=self._root / rel_path,
                        relative_path=rel_path,
                        change_type="created",
                        timestamp=now,
                    ))
                elif old_hash != new_hash:
                    events.append(FileChangeEvent(
                        path=self._root / rel_path,
                        relative_path=rel_path,
                        change_type="modified",
                        timestamp=now,
                    ))

            # Check for deleted files
            for rel_path in self._last_scan_hashes:
                if rel_path not in current_hashes:
                    events.append(FileChangeEvent(
                        path=self._root / rel_path,
                        relative_path=rel_path,
                        change_type="deleted",
                        timestamp=now,
                    ))

            self._last_scan_hashes = current_hashes

        return events

    def _poll_loop(self) -> None:
        """Main polling loop (runs in background thread)."""
        self._initial_scan()
        logger.info("File watcher started for %s (poll=%.1fs)", self._root, self._poll_interval)

        while self._running:
            time.sleep(self._poll_interval)
            if not self._running:
                break

            try:
                events = self._detect_changes()
                if events:
                    # Debounce: wait a bit for rapid successive changes
                    time.sleep(self._debounce)
                    if not self._running:
                        break
                    # Re-check to merge rapid changes
                    more_events = self._detect_changes()
                    events.extend(more_events)

                    logger.info("Detected %d file change(s)", len(events))
                    for cb in self._callbacks:
                        try:
                            cb(events)
                        except Exception:
                            logger.exception("Error in file watcher callback")
            except Exception:
                logger.exception("Error in file watcher poll loop")

    def start(self) -> None:
        """Start watching in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="codex-watcher")
        self._thread.start()

    def stop(self) -> None:
        """Stop the watcher and wait for the thread to exit."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval * 2)
            self._thread = None
        logger.info("File watcher stopped.")

    def scan_once(self) -> list[FileChangeEvent]:
        """Perform a single scan without starting continuous watching.

        Useful for manual/CLI-driven change detection.
        """
        if not self._last_scan_hashes:
            self._initial_scan()
            return []  # First scan is the baseline
        return self._detect_changes()


# ---------------------------------------------------------------------------
# Async Indexing Queue
# ---------------------------------------------------------------------------

@dataclass
class IndexingTask:
    """A queued indexing task."""

    file_paths: list[str]
    deleted_paths: list[str] = field(default_factory=list)
    force: bool = False
    timestamp: float = 0.0


class AsyncIndexer:
    """Queue-based asynchronous indexing processor.

    Accepts indexing tasks and processes them in a background thread.
    Provides callbacks for task completion and error handling.
    """

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()
        self._queue: list[IndexingTask] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_complete: Callable[[int], None] | None = None
        self._on_error: Callable[[Exception], None] | None = None
        self._tasks_processed: int = 0

    @property
    def pending_count(self) -> int:
        """Number of indexing tasks waiting in the queue."""
        with self._lock:
            return len(self._queue)

    @property
    def tasks_processed(self) -> int:
        """Total number of indexing tasks completed so far."""
        return self._tasks_processed

    def set_callbacks(
        self,
        on_complete: Callable[[int], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Set completion and error callbacks."""
        self._on_complete = on_complete
        self._on_error = on_error

    def enqueue(
        self,
        file_paths: list[str],
        deleted_paths: list[str] | None = None,
        force: bool = False,
    ) -> None:
        """Add an indexing task to the queue."""
        task = IndexingTask(
            file_paths=file_paths,
            deleted_paths=deleted_paths or [],
            force=force,
            timestamp=time.time(),
        )
        with self._lock:
            self._queue.append(task)
        logger.debug("Enqueued indexing task for %d files (%d deleted)",
                     len(file_paths), len(task.deleted_paths))

    def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            task: IndexingTask | None = None
            with self._lock:
                if self._queue:
                    task = self._queue.pop(0)

            if task is None:
                time.sleep(0.1)
                continue

            try:
                if task.force or not task.file_paths:
                    # Full re-index when forced or no specific files
                    from semantic_code_intelligence.services.indexing_service import run_indexing
                    result = run_indexing(self._root, force=task.force)
                else:
                    # Per-file incremental indexing (Phase 27)
                    from semantic_code_intelligence.services.indexing_service import run_incremental_indexing
                    result = run_incremental_indexing(
                        self._root,
                        changed_files=task.file_paths,
                        deleted_files=task.deleted_paths,
                    )
                self._tasks_processed += 1
                logger.info("Async indexing complete: %s", result)
                if self._on_complete:
                    self._on_complete(result.files_indexed)
            except Exception as e:
                logger.exception("Error processing indexing task")
                if self._on_error:
                    self._on_error(e)

    def start(self) -> None:
        """Start the async indexing processor."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._process_loop, daemon=True, name="codex-indexer"
        )
        self._thread.start()
        logger.info("Async indexer started.")

    def stop(self) -> None:
        """Stop the async indexer."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Async indexer stopped.")


# ---------------------------------------------------------------------------
# Indexing Daemon (combines watcher + async indexer)
# ---------------------------------------------------------------------------

class IndexingDaemon:
    """High-level daemon that watches for file changes and triggers indexing.

    Combines FileWatcher + AsyncIndexer into a single start/stop API.
    """

    def __init__(
        self,
        project_root: Path,
        poll_interval: float = 2.0,
        debounce: float = 0.5,
    ) -> None:
        self._root = project_root.resolve()
        self._watcher = FileWatcher(project_root, poll_interval, debounce)
        self._indexer = AsyncIndexer(project_root)
        self._watcher.on_change(self._on_file_changes)
        self._event_log: list[FileChangeEvent] = []
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """Whether the daemon (watcher + indexer) is active."""
        return self._watcher.is_running

    @property
    def event_log(self) -> list[FileChangeEvent]:
        """Return a snapshot of recent file-change events."""
        with self._lock:
            return list(self._event_log)

    def _on_file_changes(self, events: list[FileChangeEvent]) -> None:
        """Handle detected file changes."""
        with self._lock:
            self._event_log.extend(events)
            # Keep only last 1000 events
            if len(self._event_log) > 1000:
                self._event_log = self._event_log[-1000:]

        changed_paths = [str(e.path) for e in events if e.change_type != "deleted"]
        deleted_paths = [str(e.path) for e in events if e.change_type == "deleted"]
        if changed_paths or deleted_paths:
            self._indexer.enqueue(changed_paths, deleted_paths=deleted_paths)

    def start(self) -> None:
        """Start the daemon (watcher + indexer)."""
        logger.info("Starting indexing daemon for %s", self._root)
        self._indexer.start()
        self._watcher.start()

    def stop(self) -> None:
        """Stop the daemon."""
        self._watcher.stop()
        self._indexer.stop()
        logger.info("Indexing daemon stopped.")

    def get_status(self) -> dict[str, Any]:
        """Get daemon status."""
        return {
            "running": self.is_running,
            "project_root": str(self._root),
            "events_recorded": len(self._event_log),
            "pending_tasks": self._indexer.pending_count,
            "tasks_completed": self._indexer.tasks_processed,
        }
