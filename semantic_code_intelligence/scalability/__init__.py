"""Scalability utilities — batch processing, memory management, performance.

Provides:
- BatchProcessor: processes items in configurable batches
- MemoryAwareEmbedder: generates embeddings with memory-safe batching
- ParallelScanner: concurrent file scanning
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar
from concurrent.futures import ThreadPoolExecutor, as_completed

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("scalability")

T = TypeVar("T")
R = TypeVar("R")


# ---------------------------------------------------------------------------
# Batch Processor
# ---------------------------------------------------------------------------

@dataclass
class BatchStats:
    """Statistics for a batch processing run."""

    total_items: int = 0
    batches_processed: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_items": self.total_items,
            "batches_processed": self.batches_processed,
            "items_succeeded": self.items_succeeded,
            "items_failed": self.items_failed,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "items_per_second": round(
                self.items_succeeded / self.elapsed_seconds, 2
            ) if self.elapsed_seconds > 0 else 0,
        }


class BatchProcessor:
    """Process items in configurable batches with progress tracking.

    Useful for chunking/embedding large sets of files without loading
    everything into memory at once.
    """

    def __init__(self, batch_size: int = 64) -> None:
        self._batch_size = max(1, batch_size)

    @property
    def batch_size(self) -> int:
        return self._batch_size

    def process(
        self,
        items: list[T],
        processor: Callable[[list[T]], list[R]],
        on_batch: Callable[[int, int], None] | None = None,
    ) -> tuple[list[R], BatchStats]:
        """Process items in batches.

        Args:
            items: Items to process.
            processor: Function that processes a batch of items.
            on_batch: Optional callback(batch_num, total_batches).

        Returns:
            Tuple of (all_results, stats).
        """
        stats = BatchStats(total_items=len(items))
        all_results: list[R] = []
        start = time.time()

        total_batches = (len(items) + self._batch_size - 1) // self._batch_size

        for batch_idx in range(total_batches):
            offset = batch_idx * self._batch_size
            batch = items[offset : offset + self._batch_size]

            if on_batch:
                on_batch(batch_idx + 1, total_batches)

            try:
                results = processor(batch)
                all_results.extend(results)
                stats.items_succeeded += len(batch)
            except Exception:
                logger.exception("Batch %d/%d failed", batch_idx + 1, total_batches)
                stats.items_failed += len(batch)

            stats.batches_processed += 1

        stats.elapsed_seconds = time.time() - start
        return all_results, stats


# ---------------------------------------------------------------------------
# Memory-aware Embedding Generator
# ---------------------------------------------------------------------------

class MemoryAwareEmbedder:
    """Generates embeddings in memory-safe batches.

    Wraps the base generator to handle large numbers of texts without
    exhausting GPU/CPU memory.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        batch_size: int = 64,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._processor = BatchProcessor(batch_size)

    def generate(
        self,
        texts: list[str],
        show_progress: bool = False,
    ) -> Any:
        """Generate embeddings in batches, concatenating results.

        Returns:
            numpy ndarray of shape (len(texts), dimension).
        """
        import numpy as np

        from semantic_code_intelligence.embeddings.generator import generate_embeddings

        def _embed_batch(batch: list[str]) -> list[Any]:
            emb = generate_embeddings(batch, model_name=self._model_name)
            return [emb]  # Return as single item to be concatenated

        def _on_batch(current: int, total: int) -> None:
            if show_progress:
                logger.info("Embedding batch %d/%d", current, total)

        raw_results, stats = self._processor.process(
            texts, _embed_batch, on_batch=_on_batch if show_progress else None
        )

        if not raw_results:
            return np.empty((0, 0))

        return np.vstack(raw_results)


# ---------------------------------------------------------------------------
# Parallel File Scanner
# ---------------------------------------------------------------------------

class ParallelScanner:
    """Scan and process files using thread-based parallelism.

    Useful for I/O-bound operations like reading/hashing multiple files.
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max(1, max_workers)

    def scan_and_process(
        self,
        file_paths: list[Path],
        processor: Callable[[Path], R],
    ) -> tuple[list[R], list[str]]:
        """Process files in parallel.

        Args:
            file_paths: Files to process.
            processor: Function to apply to each file.

        Returns:
            Tuple of (results, error_messages).
        """
        results: list[R] = []
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_path = {
                executor.submit(processor, fp): fp for fp in file_paths
            }

            for future in as_completed(future_to_path):
                fp = future_to_path[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append(f"{fp}: {e}")
                    logger.debug("Failed to process %s: %s", fp, e)

        return results, errors
