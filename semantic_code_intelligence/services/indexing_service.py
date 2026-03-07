"""Indexing service — orchestrates scanning, chunking, embedding, and storage."""

from __future__ import annotations

from pathlib import Path

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.embeddings.generator import (
    generate_embeddings,
    get_embedding_dimension,
)
from semantic_code_intelligence.indexing.chunker import CodeChunk, chunk_file
from semantic_code_intelligence.indexing.scanner import ScannedFile, scan_repository
from semantic_code_intelligence.storage.hash_store import HashStore
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
        self.total_vectors: int = 0

    def __repr__(self) -> str:
        return (
            f"IndexingResult(scanned={self.files_scanned}, "
            f"indexed={self.files_indexed}, skipped={self.files_skipped}, "
            f"chunks={self.chunks_created}, vectors={self.total_vectors})"
        )


def run_indexing(
    project_root: Path,
    force: bool = False,
) -> IndexingResult:
    """Run the full indexing pipeline for a project.

    1. Scan the repository for indexable files
    2. Filter unchanged files (unless force=True)
    3. Chunk each file
    4. Generate embeddings
    5. Store in FAISS vector store

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

    result = IndexingResult()

    # Step 1: Scan repository
    logger.info("Scanning repository: %s", project_root)
    scanned_files = scan_repository(project_root, config.index)
    result.files_scanned = len(scanned_files)
    logger.info("Found %d indexable files.", result.files_scanned)

    if not scanned_files:
        return result

    # Step 2: Load hash store for incremental indexing
    hash_store = HashStore.load(index_dir)
    files_to_index: list[ScannedFile] = []

    if force:
        files_to_index = scanned_files
    else:
        for sf in scanned_files:
            if hash_store.has_changed(sf.relative_path, sf.content_hash):
                files_to_index.append(sf)
            else:
                result.files_skipped += 1

    logger.info(
        "%d files to index (%d skipped, unchanged).",
        len(files_to_index),
        result.files_skipped,
    )

    # Step 3: Chunk all files
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
        hash_store.save(index_dir)
        return result

    # Step 4: Generate embeddings
    texts = [chunk.content for chunk in all_chunks]
    logger.info("Generating embeddings for %d chunks...", len(texts))
    embeddings = generate_embeddings(
        texts,
        model_name=config.embedding.model_name,
        show_progress=True,
    )
    logger.info("Embeddings generated. Shape: %s", embeddings.shape)

    # Step 5: Build metadata list
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

    # Step 6: Store in vector store
    # For force mode or first run, create fresh store.
    # For incremental, load existing and append.
    dimension = embeddings.shape[1]

    if force:
        store = VectorStore(dimension)
    else:
        try:
            store = VectorStore.load(index_dir)
        except FileNotFoundError:
            store = VectorStore(dimension)

    store.add(embeddings, metadata_list)
    store.save(index_dir)

    # Step 7: Update hash store
    for sf in files_to_index:
        hash_store.set(sf.relative_path, sf.content_hash)
    hash_store.save(index_dir)

    result.total_vectors = store.size
    logger.info("Indexing complete. %s", result)
    return result
