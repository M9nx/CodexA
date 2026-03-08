"""Parallel indexing utilities — concurrent file I/O and chunking.

Speeds up the scanning and chunking phases by processing files in
parallel using a thread pool, while embedding generation is batched
through the model (which already uses efficient GPU/CPU batching).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from semantic_code_intelligence.indexing.chunker import CodeChunk, chunk_file
from semantic_code_intelligence.indexing.scanner import ScannedFile, compute_file_hash
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("indexing.parallel")

# Sensible default: don't overwhelm disk or CPU
DEFAULT_WORKERS = 4


def parallel_chunk_files(
    files: list[ScannedFile],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    max_workers: int = DEFAULT_WORKERS,
) -> list[tuple[ScannedFile, list[CodeChunk]]]:
    """Chunk multiple files in parallel using a thread pool.

    Args:
        files: List of scanned files to chunk.
        chunk_size: Max characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.
        max_workers: Number of threads.

    Returns:
        List of (ScannedFile, chunks) tuples in original order.
    """
    if not files:
        return []

    results: dict[int, tuple[ScannedFile, list[CodeChunk]]] = {}

    def _chunk_one(idx: int, sf: ScannedFile) -> tuple[int, ScannedFile, list[CodeChunk]]:
        chunks = chunk_file(sf.path, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        return idx, sf, chunks

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_chunk_one, i, sf): i
            for i, sf in enumerate(files)
        }
        for future in as_completed(futures):
            idx, sf, chunks = future.result()
            results[idx] = (sf, chunks)

    return [results[i] for i in range(len(files))]


def parallel_scan_hashes(
    file_paths: list[Path],
    max_workers: int = DEFAULT_WORKERS,
) -> dict[Path, str]:
    """Compute file hashes in parallel.

    Args:
        file_paths: Files to hash.
        max_workers: Number of threads.

    Returns:
        Mapping of path → SHA-256 hex digest.
    """
    result: dict[Path, str] = {}

    def _hash_one(p: Path) -> tuple[Path, str]:
        return p, compute_file_hash(p)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_hash_one, p) for p in file_paths]
        for future in as_completed(futures):
            p, h = future.result()
            result[p] = h

    return result
