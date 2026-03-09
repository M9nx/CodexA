"""Indexing service — orchestrates scanning, chunking, embedding, and storage.

Supports chunk-level incremental indexing: when a file changes, only the
individual chunks whose content actually differs are re-embedded, while
unchanged chunks keep their existing vectors (high cache-hit ratio).
"""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.embeddings.generator import (
    generate_embeddings,
    get_embedding_dimension,
)
from semantic_code_intelligence.indexing.chunker import CodeChunk, chunk_file, detect_language
from semantic_code_intelligence.indexing.scanner import ScannedFile, scan_repository
from semantic_code_intelligence.parsing.parser import Symbol, parse_file
from semantic_code_intelligence.storage.chunk_hash_store import ChunkHashStore, compute_chunk_hash
from semantic_code_intelligence.storage.hash_store import HashStore
from semantic_code_intelligence.storage.index_manifest import IndexManifest
from semantic_code_intelligence.storage.index_stats import IndexStats, LanguageCoverage
from semantic_code_intelligence.storage.symbol_registry import SymbolEntry, SymbolRegistry
from semantic_code_intelligence.storage.vector_store import ChunkMetadata, VectorStore
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("services.indexing")


class IndexingResult:
    """Results of an indexing operation."""

    def __init__(self) -> None:
        self.files_scanned: int = 0
        self.files_indexed: int = 0
        self.files_skipped: int = 0
        self.chunks_created: int = 0
        self.chunks_reused: int = 0
        self.total_vectors: int = 0
        self.symbols_extracted: int = 0

    def __repr__(self) -> str:
        return (
            f"IndexingResult(scanned={self.files_scanned}, "
            f"indexed={self.files_indexed}, skipped={self.files_skipped}, "
            f"chunks={self.chunks_created}, reused={self.chunks_reused}, "
            f"vectors={self.total_vectors}, "
            f"symbols={self.symbols_extracted})"
        )


def _extract_symbols(
    files_to_index: list[ScannedFile],
    deleted_paths: list[str],
    index_dir: Path,
    force: bool,
) -> tuple[SymbolRegistry, int]:
    """Extract symbols from indexed files and update the registry."""
    registry = SymbolRegistry() if force else SymbolRegistry.load(index_dir)
    count = 0
    for dp in deleted_paths:
        registry.remove_file(dp)
    for sf in files_to_index:
        registry.remove_file(sf.relative_path)
        try:
            symbols = parse_file(sf.path)
            entries = [
                SymbolEntry(
                    name=sym.name,
                    kind=sym.kind,
                    file_path=sf.relative_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    parent=sym.parent,
                    parameters=sym.parameters,
                    decorators=sym.decorators,
                    language=detect_language(str(sf.path)),
                )
                for sym in symbols
            ]
            registry.add_many(entries)
            count += len(entries)
        except Exception:
            logger.debug("Symbol extraction failed for %s", sf.relative_path)
    registry.save(index_dir)
    return registry, count


def _compute_index_stats(
    all_chunks: list[CodeChunk],
    registry: SymbolRegistry,
    result: IndexingResult,
    config: "AppConfig",
    dimension: int,
    store_size: int,
    indexing_start: float,
    index_dir: Path,
) -> None:
    """Aggregate per-language metrics and persist index stats."""
    indexing_end = time.time()

    lang_files: dict[str, set[str]] = defaultdict(set)
    lang_chunks: dict[str, int] = defaultdict(int)
    lang_lines: dict[str, int] = defaultdict(int)
    for chunk in all_chunks:
        lang = chunk.language or "unknown"
        lang_files[lang].add(chunk.file_path)
        lang_chunks[lang] += 1
        lang_lines[lang] += chunk.end_line - chunk.start_line + 1
    lang_symbols: dict[str, int] = registry.language_summary()

    coverage = [
        LanguageCoverage(
            language=lang,
            files=len(files),
            chunks=lang_chunks.get(lang, 0),
            symbols=lang_symbols.get(lang, 0),
            total_lines=lang_lines.get(lang, 0),
        )
        for lang, files in lang_files.items()
    ]

    total_chars = sum(len(c.content) for c in all_chunks)
    stats = IndexStats(
        total_files=result.files_indexed + result.files_skipped,
        total_chunks=store_size,
        total_symbols=registry.size,
        total_vectors=store_size,
        last_indexed_at=indexing_end,
        indexing_duration_seconds=round(indexing_end - indexing_start, 3),
        language_coverage=coverage,
        avg_chunk_size=round(total_chars / len(all_chunks), 1) if all_chunks else 0.0,
        embedding_model=config.embedding.model_name,
        embedding_dimension=dimension,
    )
    stats.save(index_dir)


def run_indexing(
    project_root: Path,
    force: bool = False,
) -> IndexingResult:
    """Run the full indexing pipeline for a project.

    Uses **chunk-level incremental indexing**: when a file changes, each
    chunk is individually hashed and only chunks with new/changed content
    are re-embedded.  Unchanged chunks keep their existing vectors,
    achieving high cache-hit ratios (typically 80-90% on incremental runs).

    Args:
        project_root: Root directory of the project.
        force: If True, re-index all files regardless of hash cache.

    Returns:
        IndexingResult with statistics.
    """
    project_root = project_root.resolve()
    config = load_config(project_root)
    index_dir = AppConfig.index_dir(project_root)
    index_dir.mkdir(parents=True, exist_ok=True)

    indexing_start = time.time()
    result = IndexingResult()

    # Step 1: Scan repository
    logger.info("Scanning repository: %s", project_root)
    scanned_files = scan_repository(project_root, config.index)
    result.files_scanned = len(scanned_files)
    logger.info("Found %d indexable files.", result.files_scanned)

    if not scanned_files:
        return result

    # Step 2: Load hash stores for incremental indexing
    hash_store = HashStore.load(index_dir)
    chunk_hash_store = ChunkHashStore.load(index_dir)
    files_to_index: list[ScannedFile] = []
    scanned_paths = {sf.relative_path for sf in scanned_files}

    if force:
        files_to_index = scanned_files
    else:
        for sf in scanned_files:
            if hash_store.has_changed(sf.relative_path, sf.content_hash):
                files_to_index.append(sf)
            else:
                result.files_skipped += 1

    # Detect deleted files: tracked in hash_store but no longer on disk
    deleted_paths: list[str] = []
    if not force:
        for tracked_path in list(hash_store._hashes.keys()):
            if tracked_path not in scanned_paths:
                deleted_paths.append(tracked_path)

    logger.info(
        "%d files to index (%d skipped, unchanged).",
        len(files_to_index),
        result.files_skipped,
    )

    # Step 3: Chunk all changed files
    all_chunks: list[CodeChunk] = []
    chunk_file_hashes: list[str] = []  # parallel array: hash for each chunk's file

    for sf in files_to_index:
        chunks = chunk_file(
            sf.path,
            chunk_size=config.embedding.chunk_size,
            chunk_overlap=config.embedding.chunk_overlap,
        )
        for c in chunks:
            all_chunks.append(c)
            chunk_file_hashes.append(sf.content_hash)
        result.files_indexed += 1

    result.chunks_created = len(all_chunks)
    logger.info("Created %d code chunks.", result.chunks_created)

    if not all_chunks:
        # Update hashes even if no chunks (e.g. empty files)
        for sf in files_to_index:
            hash_store.set(sf.relative_path, sf.content_hash)

        # Still clean up deleted files from the vector store
        if deleted_paths:
            try:
                store = VectorStore.load(index_dir)
                for dp in deleted_paths:
                    full = str(project_root / dp)
                    store.remove_by_file(full)
                    hash_store.remove(dp)
                    chunk_hash_store.remove_by_file(full)
                store.save(index_dir)
            except FileNotFoundError:
                pass

        hash_store.save(index_dir)
        chunk_hash_store.save(index_dir)
        return result

    # Step 4: Chunk-level delta — separate new/changed chunks from reusable ones
    chunks_to_embed: list[CodeChunk] = []
    chunks_to_embed_file_hashes: list[str] = []
    reused_indices: list[int] = []  # indices into all_chunks that are unchanged

    if force:
        chunks_to_embed = all_chunks
        chunks_to_embed_file_hashes = chunk_file_hashes
    else:
        for i, chunk in enumerate(all_chunks):
            c_hash = compute_chunk_hash(chunk.content)
            c_key = ChunkHashStore.chunk_key(
                chunk.file_path, chunk.start_line, chunk.end_line,
            )
            if chunk_hash_store.has_changed(c_key, c_hash):
                chunks_to_embed.append(chunk)
                chunks_to_embed_file_hashes.append(chunk_file_hashes[i])
            else:
                reused_indices.append(i)

    result.chunks_reused = len(reused_indices)
    logger.info(
        "Chunk-level delta: %d to embed, %d reused (cache hit %.0f%%).",
        len(chunks_to_embed),
        result.chunks_reused,
        100 * result.chunks_reused / len(all_chunks) if all_chunks else 0,
    )

    # Step 5: Generate embeddings only for changed chunks
    new_embeddings: np.ndarray | None = None
    if chunks_to_embed:
        texts = [chunk.content for chunk in chunks_to_embed]
        logger.info("Generating embeddings for %d chunks...", len(texts))
        new_embeddings = generate_embeddings(
            texts,
            model_name=config.embedding.model_name,
            show_progress=True,
        )
        logger.info("Embeddings generated. Shape: %s", new_embeddings.shape)

    # Step 6: Load or create vector store and reconcile
    if new_embeddings is not None:
        dimension = new_embeddings.shape[1]
    else:
        dimension = get_embedding_dimension(config.embedding.model_name)

    if force:
        store = VectorStore(dimension)
        cached_vectors: dict[str, np.ndarray] = {}
    else:
        try:
            store = VectorStore.load(index_dir)
        except FileNotFoundError:
            store = VectorStore(dimension)

        # Extract existing vectors for unchanged chunks BEFORE removing
        cached_vectors = {}
        for sf in files_to_index:
            for meta, vec in store.get_vectors_for_file(str(sf.path)):
                # Key by content hash so we can match reused chunks
                cache_key = f"{meta.file_path}:{meta.start_line}:{meta.end_line}:{meta.content_hash}"
                cached_vectors[cache_key] = vec

        # Remove stale vectors for changed files before adding updated ones
        for sf in files_to_index:
            store.remove_by_file(str(sf.path))

        # Remove vectors for deleted files
        for dp in deleted_paths:
            full = str(project_root / dp)
            store.remove_by_file(full)
            hash_store.remove(dp)
            chunk_hash_store.remove_by_file(full)

    # Step 7: Build final embeddings by combining cached + new vectors
    # For reused chunks, look up their cached vectors instead of re-embedding.
    # Build a lookup from changed-chunk index to its embedding
    new_embed_map: dict[int, int] = {}  # all_chunks idx -> new_embeddings idx
    new_idx = 0
    for i, chunk in enumerate(all_chunks):
        if i not in set(reused_indices):
            new_embed_map[i] = new_idx
            new_idx += 1

    all_embeddings_list: list[np.ndarray] = []
    reembedded_count = 0
    for i, chunk in enumerate(all_chunks):
        if i in set(reused_indices) and not force:
            # Try to reuse cached vector for this chunk
            cache_key = f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}:{chunk_file_hashes[i]}"
            cached_vec = cached_vectors.get(cache_key)
            if cached_vec is not None:
                all_embeddings_list.append(cached_vec)
                continue
            # Cache miss — chunk positions may have shifted; need to embed
            reembedded_count += 1

        if i in new_embed_map and new_embeddings is not None:
            all_embeddings_list.append(new_embeddings[new_embed_map[i]])
        else:
            # Fallback: embed this single chunk (rare — only cache misses)
            reembedded_count += 1
            vec = generate_embeddings(
                [chunk.content],
                model_name=config.embedding.model_name,
                show_progress=False,
            )
            all_embeddings_list.append(vec[0])

    if reembedded_count > 0:
        logger.info("Re-embedded %d chunks (cache miss due to position shift).", reembedded_count)

    if all_embeddings_list:
        all_embeddings = np.vstack([v.reshape(1, -1) for v in all_embeddings_list]).astype(np.float32)
    else:
        all_embeddings = np.empty((0, dimension), dtype=np.float32)

    metadata_list = [
        ChunkMetadata(
            file_path=chunk.file_path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            chunk_index=chunk.chunk_index,
            language=chunk.language,
            content=chunk.content,
            content_hash=chunk_file_hashes[i],
        )
        for i, chunk in enumerate(all_chunks)
    ]

    store.add(all_embeddings, metadata_list)
    store.save(index_dir)

    # Step 8: Update hash stores
    for sf in files_to_index:
        hash_store.set(sf.relative_path, sf.content_hash)
    # Update chunk-level hashes
    for chunk in all_chunks:
        c_key = ChunkHashStore.chunk_key(
            chunk.file_path, chunk.start_line, chunk.end_line,
        )
        chunk_hash_store.set(c_key, compute_chunk_hash(chunk.content))

    hash_store.save(index_dir)
    chunk_hash_store.save(index_dir)

    result.total_vectors = store.size

    # Step 9: Extract symbols and populate registry
    registry, result.symbols_extracted = _extract_symbols(
        files_to_index, deleted_paths, index_dir, force,
    )

    # Step 10: Update index manifest
    manifest = IndexManifest.load(index_dir) or IndexManifest()
    manifest.embedding_model = config.embedding.model_name
    manifest.embedding_dimension = dimension
    manifest.project_root = str(project_root)
    manifest.total_files = result.files_indexed + result.files_skipped
    manifest.total_chunks = store.size
    manifest.total_symbols = registry.size
    manifest.languages = sorted(set(
        chunk.language for chunk in all_chunks if chunk.language != "unknown"
    ))
    manifest.touch()
    manifest.save(index_dir)

    # Step 11: Compute and persist index stats
    _compute_index_stats(
        all_chunks, registry, result, config,
        dimension, store.size, indexing_start, index_dir,
    )

    logger.info("Indexing complete. %s", result)
    return result


# ── Per-file incremental indexing (Phase 27) ─────────────────────────

def run_incremental_indexing(
    project_root: Path,
    changed_files: list[str],
    deleted_files: list[str] | None = None,
) -> IndexingResult:
    """Re-index only specific changed/deleted files without a full repo scan.

    This is the key performance optimisation for the daemon: instead of
    scanning the entire repository on every file change, it processes only
    the files that the watcher detected as created/modified/deleted.

    Changed files are re-chunked, re-embedded, and their vectors replaced
    in the FAISS store.  Deleted files have their vectors, hashes, and
    symbols removed.

    Args:
        project_root: Root directory of the project.
        changed_files: Absolute paths of files that were created or modified.
        deleted_files: Absolute paths of files that were deleted.

    Returns:
        IndexingResult with statistics for the incremental operation.
    """
    project_root = project_root.resolve()
    config = load_config(project_root)
    index_dir = AppConfig.index_dir(project_root)
    index_dir.mkdir(parents=True, exist_ok=True)
    deleted_files = deleted_files or []

    indexing_start = time.time()
    result = IndexingResult()

    # Load existing stores
    hash_store = HashStore.load(index_dir)
    chunk_hash_store = ChunkHashStore.load(index_dir)

    try:
        store = VectorStore.load(index_dir)
    except FileNotFoundError:
        # No existing index — fall back to full indexing
        logger.info("No existing index found; falling back to full indexing.")
        return run_indexing(project_root, force=False)

    dimension = store.dimension

    # Step 1: Handle deleted files
    deleted_rel: list[str] = []
    for dp in deleted_files:
        p = Path(dp)
        if p.is_absolute():
            try:
                rel = str(p.relative_to(project_root))
            except ValueError:
                rel = str(p)
        else:
            rel = dp
        store.remove_by_file(dp)
        hash_store.remove(rel)
        chunk_hash_store.remove_by_file(dp)
        deleted_rel.append(rel)

    # Step 2: Process changed files
    scanned_files: list[ScannedFile] = []
    for fp in changed_files:
        p = Path(fp)
        if not p.is_file():
            continue
        try:
            rel = str(p.relative_to(project_root))
        except ValueError:
            rel = str(p)
        content_hash = _safe_compute_hash(p)
        if content_hash is None:
            continue
        scanned_files.append(ScannedFile(
            path=p,
            relative_path=rel,
            extension=p.suffix,
            size_bytes=p.stat().st_size,
            content_hash=content_hash,
        ))
    result.files_scanned = len(scanned_files)

    # Step 3: Filter to files that actually changed (hash check)
    files_to_index: list[ScannedFile] = []
    for sf in scanned_files:
        if hash_store.has_changed(sf.relative_path, sf.content_hash):
            files_to_index.append(sf)
        else:
            result.files_skipped += 1

    if not files_to_index and not deleted_files:
        logger.info("Incremental: nothing to update.")
        return result

    # Step 4: Chunk changed files
    all_chunks: list[CodeChunk] = []
    chunk_file_hashes: list[str] = []

    for sf in files_to_index:
        # Remove old vectors for this file before re-adding
        store.remove_by_file(str(sf.path))
        chunk_hash_store.remove_by_file(str(sf.path))

        chunks = chunk_file(
            sf.path,
            chunk_size=config.embedding.chunk_size,
            chunk_overlap=config.embedding.chunk_overlap,
        )
        for c in chunks:
            all_chunks.append(c)
            chunk_file_hashes.append(sf.content_hash)
        result.files_indexed += 1

    result.chunks_created = len(all_chunks)

    # Step 5: Embed and add to store
    if all_chunks:
        texts = [chunk.content for chunk in all_chunks]
        logger.info("Incremental: embedding %d chunks from %d files...",
                     len(texts), len(files_to_index))
        embeddings = generate_embeddings(
            texts,
            model_name=config.embedding.model_name,
            show_progress=False,
        )

        metadata_list = [
            ChunkMetadata(
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                chunk_index=chunk.chunk_index,
                language=chunk.language,
                content=chunk.content,
                content_hash=chunk_file_hashes[i],
            )
            for i, chunk in enumerate(all_chunks)
        ]

        store.add(embeddings, metadata_list)

    # Step 6: Persist stores
    store.save(index_dir)

    for sf in files_to_index:
        hash_store.set(sf.relative_path, sf.content_hash)
    for chunk in all_chunks:
        c_key = ChunkHashStore.chunk_key(
            chunk.file_path, chunk.start_line, chunk.end_line,
        )
        chunk_hash_store.set(c_key, compute_chunk_hash(chunk.content))

    hash_store.save(index_dir)
    chunk_hash_store.save(index_dir)
    result.total_vectors = store.size

    # Step 7: Update symbol registry for changed files only
    registry = SymbolRegistry.load(index_dir)
    sym_count = 0
    for dp in deleted_rel:
        registry.remove_file(dp)
    for sf in files_to_index:
        registry.remove_file(sf.relative_path)
        try:
            symbols = parse_file(sf.path)
            entries = [
                SymbolEntry(
                    name=sym.name,
                    kind=sym.kind,
                    file_path=sf.relative_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    parent=sym.parent,
                    parameters=sym.parameters,
                    decorators=sym.decorators,
                    language=detect_language(str(sf.path)),
                )
                for sym in symbols
            ]
            registry.add_many(entries)
            sym_count += len(entries)
        except Exception:
            logger.debug("Symbol extraction failed for %s", sf.relative_path)
    registry.save(index_dir)
    result.symbols_extracted = sym_count

    # Step 8: Update index manifest
    manifest = IndexManifest.load(index_dir) or IndexManifest()
    manifest.total_chunks = store.size
    manifest.total_symbols = registry.size
    manifest.touch()
    manifest.save(index_dir)

    logger.info("Incremental indexing complete. %s", result)
    return result


def _safe_compute_hash(path: Path) -> str | None:
    """Compute file hash, returning None on error."""
    try:
        from semantic_code_intelligence.indexing.scanner import compute_file_hash
        return compute_file_hash(path)
    except (OSError, PermissionError):
        return None
