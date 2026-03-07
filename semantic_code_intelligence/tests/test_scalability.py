"""Tests for the scalability utilities."""

from __future__ import annotations

import pytest

from semantic_code_intelligence.scalability import (
    BatchProcessor,
    BatchStats,
    ParallelScanner,
)
from pathlib import Path


# ---------------------------------------------------------------------------
# BatchStats
# ---------------------------------------------------------------------------

class TestBatchStats:
    def test_defaults(self):
        stats = BatchStats()
        assert stats.total_items == 0
        assert stats.batches_processed == 0

    def test_to_dict(self):
        stats = BatchStats(
            total_items=100,
            batches_processed=10,
            items_succeeded=95,
            items_failed=5,
            elapsed_seconds=2.0,
        )
        d = stats.to_dict()
        assert d["total_items"] == 100
        assert d["items_per_second"] == 47.5

    def test_to_dict_zero_elapsed(self):
        stats = BatchStats(elapsed_seconds=0)
        d = stats.to_dict()
        assert d["items_per_second"] == 0


# ---------------------------------------------------------------------------
# BatchProcessor
# ---------------------------------------------------------------------------

class TestBatchProcessor:
    def test_empty_items(self):
        proc = BatchProcessor(batch_size=10)
        results, stats = proc.process([], lambda batch: batch)
        assert results == []
        assert stats.total_items == 0
        assert stats.batches_processed == 0

    def test_single_batch(self):
        proc = BatchProcessor(batch_size=10)
        items = list(range(5))
        results, stats = proc.process(items, lambda batch: [x * 2 for x in batch])
        assert results == [0, 2, 4, 6, 8]
        assert stats.total_items == 5
        assert stats.batches_processed == 1
        assert stats.items_succeeded == 5

    def test_multiple_batches(self):
        proc = BatchProcessor(batch_size=3)
        items = list(range(10))
        results, stats = proc.process(items, lambda batch: batch)
        assert results == list(range(10))
        assert stats.batches_processed == 4  # ceil(10/3)

    def test_batch_callback(self):
        proc = BatchProcessor(batch_size=2)
        calls = []
        items = list(range(6))
        proc.process(
            items,
            lambda batch: batch,
            on_batch=lambda cur, total: calls.append((cur, total)),
        )
        assert calls == [(1, 3), (2, 3), (3, 3)]

    def test_batch_size_minimum(self):
        proc = BatchProcessor(batch_size=0)
        assert proc.batch_size == 1

    def test_failing_batch(self):
        proc = BatchProcessor(batch_size=2)

        def bad_processor(batch):
            if batch[0] == 2:
                raise ValueError("fail")
            return batch

        items = list(range(6))
        results, stats = proc.process(items, bad_processor)
        assert stats.items_failed == 2
        assert stats.items_succeeded == 4


# ---------------------------------------------------------------------------
# ParallelScanner
# ---------------------------------------------------------------------------

class TestParallelScanner:
    def test_scan_empty(self):
        scanner = ParallelScanner(max_workers=2)
        results, errors = scanner.scan_and_process([], lambda p: p)
        assert results == []
        assert errors == []

    def test_scan_files(self, tmp_path):
        for i in range(5):
            (tmp_path / f"file{i}.txt").write_text(f"content {i}", encoding="utf-8")

        paths = list(tmp_path.glob("*.txt"))
        scanner = ParallelScanner(max_workers=2)
        results, errors = scanner.scan_and_process(
            paths,
            lambda p: p.read_text(encoding="utf-8"),
        )
        assert len(results) == 5
        assert len(errors) == 0

    def test_scan_with_errors(self, tmp_path):
        paths = [tmp_path / "exists.txt", tmp_path / "missing.txt"]
        paths[0].write_text("ok", encoding="utf-8")

        scanner = ParallelScanner(max_workers=2)
        results, errors = scanner.scan_and_process(
            paths,
            lambda p: p.read_text(encoding="utf-8"),
        )
        assert len(results) == 1
        assert len(errors) == 1

    def test_max_workers_minimum(self):
        scanner = ParallelScanner(max_workers=0)
        assert scanner._max_workers == 1
