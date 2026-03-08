"""Multi-repository workspace — manage, index, and search across multiple repos.

A *workspace* is a collection of repositories stored in a lightweight JSON
manifest at ``<root>/.codex/workspace.json``.  Each repository has its own
vector index under ``.codex/repos/<repo_name>/``, enabling incremental
per-repo indexing while supporting merged cross-repo search.

Typical usage::

    ws = Workspace.load_or_create(Path("/my/workspace"))
    ws.add_repo("backend", Path("/my/workspace/backend"))
    ws.add_repo("frontend", Path("/my/workspace/frontend"))
    ws.save()

    ws.index_all()                       # index every repo
    results = ws.search("authentication")  # merged results
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.config.settings import (
    AppConfig,
    IndexConfig,
    load_config,
)
from semantic_code_intelligence.indexing.scanner import scan_repository
from semantic_code_intelligence.services.indexing_service import IndexingResult, run_indexing
from semantic_code_intelligence.services.search_service import SearchMode, SearchResult
from semantic_code_intelligence.storage.vector_store import VectorStore
from semantic_code_intelligence.embeddings.generator import generate_embeddings
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("workspace")

WORKSPACE_FILE = "workspace.json"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RepoEntry:
    """A single repository registered in a workspace."""

    name: str
    path: str  # absolute path
    last_indexed: float = 0.0  # epoch timestamp
    file_count: int = 0
    vector_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise the repo entry to a plain dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "last_indexed": self.last_indexed,
            "file_count": self.file_count,
            "vector_count": self.vector_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoEntry":
        """Construct a :class:`RepoEntry` from a dictionary."""
        return cls(
            name=data["name"],
            path=data["path"],
            last_indexed=data.get("last_indexed", 0.0),
            file_count=data.get("file_count", 0),
            vector_count=data.get("vector_count", 0),
        )


@dataclass
class WorkspaceManifest:
    """Serialisable workspace manifest."""

    version: str = "1.0.0"
    repos: list[RepoEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the manifest to a plain dictionary."""
        return {
            "version": self.version,
            "repos": [r.to_dict() for r in self.repos],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkspaceManifest":
        """Construct a :class:`WorkspaceManifest` from a dictionary."""
        return cls(
            version=data.get("version", "1.0.0"),
            repos=[RepoEntry.from_dict(r) for r in data.get("repos", [])],
        )


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

class Workspace:
    """Multi-repository workspace manager.

    Keeps a manifest of registered repos, provides per-repo indexing,
    and supports cross-repo merged search.
    """

    def __init__(self, root: Path, manifest: WorkspaceManifest | None = None) -> None:
        self._root = root.resolve()
        self._manifest = manifest or WorkspaceManifest()

    # --- persistence -------------------------------------------------------

    @property
    def root(self) -> Path:
        """Absolute path to the workspace root directory."""
        return self._root

    @property
    def config_dir(self) -> Path:
        """Path to the ``.codex`` configuration directory."""
        return self._root / ".codex"

    @property
    def repos_dir(self) -> Path:
        """Path to the per-repo index storage directory."""
        return self.config_dir / "repos"

    @property
    def manifest_path(self) -> Path:
        """Path to the workspace manifest JSON file."""
        return self.config_dir / WORKSPACE_FILE

    @property
    def repos(self) -> list[RepoEntry]:
        """Snapshot of all registered repositories."""
        return list(self._manifest.repos)

    def save(self) -> Path:
        """Persist the workspace manifest to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self._manifest.to_dict(), indent=2)
        self.manifest_path.write_text(text, encoding="utf-8")
        return self.manifest_path

    @classmethod
    def load(cls, root: Path) -> "Workspace":
        """Load an existing workspace. Raises FileNotFoundError if not found."""
        root = root.resolve()
        path = root / ".codex" / WORKSPACE_FILE
        if not path.exists():
            raise FileNotFoundError(f"No workspace found at {root}")
        data = json.loads(path.read_text(encoding="utf-8"))
        manifest = WorkspaceManifest.from_dict(data)
        return cls(root, manifest)

    @classmethod
    def load_or_create(cls, root: Path) -> "Workspace":
        """Load an existing workspace or create a new one."""
        try:
            return cls.load(root)
        except FileNotFoundError:
            ws = cls(root)
            ws.save()
            return ws

    # --- repo management ---------------------------------------------------

    def get_repo(self, name: str) -> RepoEntry | None:
        """Look up a repository by name, or return ``None``."""
        for r in self._manifest.repos:
            if r.name == name:
                return r
        return None

    def add_repo(self, name: str, path: Path) -> RepoEntry:
        """Register a repository in the workspace.

        Raises ValueError if *name* is already registered.
        """
        if self.get_repo(name) is not None:
            raise ValueError(f"Repository '{name}' already registered")

        resolved = path.resolve()
        if not resolved.is_dir():
            raise FileNotFoundError(f"Directory not found: {resolved}")

        entry = RepoEntry(name=name, path=str(resolved))
        self._manifest.repos.append(entry)
        return entry

    def remove_repo(self, name: str) -> bool:
        """Unregister a repository. Returns True if found and removed."""
        for i, r in enumerate(self._manifest.repos):
            if r.name == name:
                self._manifest.repos.pop(i)
                return True
        return False

    def repo_index_dir(self, name: str) -> Path:
        """Return the per-repo index directory."""
        return self.repos_dir / name

    # --- indexing -----------------------------------------------------------

    def index_repo(self, name: str, force: bool = False) -> IndexingResult:
        """Index a single repository."""
        entry = self.get_repo(name)
        if entry is None:
            raise KeyError(f"Repository '{name}' not registered")

        repo_root = Path(entry.path)
        index_dir = self.repo_index_dir(name)
        index_dir.mkdir(parents=True, exist_ok=True)

        config = load_config(repo_root)

        # Run the indexing pipeline but store in workspace-local index dir
        result = _index_repo_into(repo_root, index_dir, config, force=force)

        entry.last_indexed = time.time()
        entry.file_count = result.files_indexed
        entry.vector_count = result.total_vectors
        return result

    def index_all(self, force: bool = False) -> dict[str, IndexingResult]:
        """Index all registered repositories."""
        results: dict[str, IndexingResult] = {}
        for entry in self._manifest.repos:
            results[entry.name] = self.index_repo(entry.name, force=force)
        self.save()
        return results

    # --- search -------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.3,
        repos: list[str] | None = None,
        mode: SearchMode = "semantic",
        case_insensitive: bool = True,
    ) -> list[dict[str, Any]]:
        """Search across repositories and return merged results.

        Args:
            query: Natural language search query, keywords, or regex.
            top_k: Number of top results per repo.
            threshold: Minimum similarity score (semantic/hybrid modes).
            repos: Restrict search to these repo names. None = all.
            mode: Search mode — ``"semantic"``, ``"keyword"``,
                  ``"regex"``, or ``"hybrid"``.
            case_insensitive: For regex mode, whether to ignore case.

        Returns:
            List of result dicts sorted by score (descending), each with
            an extra ``repo`` key identifying the source repository.
        """
        targets = repos or [r.name for r in self._manifest.repos]
        all_results: list[dict[str, Any]] = []

        config = load_config(self._root)
        model_name = config.embedding.model_name

        # Pre-compute query embedding for semantic/hybrid modes
        query_embedding = None
        if mode in ("semantic", "hybrid"):
            query_embedding = generate_embeddings([query], model_name=model_name)[0]

        for repo_name in targets:
            idx_dir = self.repo_index_dir(repo_name)
            try:
                store = VectorStore.load(idx_dir)
            except FileNotFoundError:
                logger.debug("No index for repo %s, skipping.", repo_name)
                continue

            raw: list[tuple[Any, float]] = []

            if mode == "keyword":
                from semantic_code_intelligence.search.keyword_search import keyword_search
                hits = keyword_search(query, store, idx_dir, top_k=top_k)
                raw = [(h, h.score) for h in hits]
            elif mode == "regex":
                from semantic_code_intelligence.search.keyword_search import regex_search
                hits = regex_search(query, store, top_k=top_k, case_insensitive=case_insensitive)
                raw = [(h, h.score) for h in hits]
            elif mode == "hybrid":
                from semantic_code_intelligence.search.hybrid_search import hybrid_search
                hits = hybrid_search(query, store, idx_dir, model_name=model_name, top_k=top_k)
                raw = [(h, h.score) for h in hits]
            else:
                # semantic (default)
                assert query_embedding is not None
                raw_store = store.search(query_embedding, top_k=top_k)
                raw = [(meta, score) for meta, score in raw_store]

            for item, score in raw:
                if mode in ("semantic", "hybrid") and score < threshold:
                    continue
                # Normalise to dict — item may be ChunkMetadata or a hit dataclass
                file_path = getattr(item, "file_path", "")
                all_results.append({
                    "repo": repo_name,
                    "file_path": file_path,
                    "start_line": getattr(item, "start_line", 0),
                    "end_line": getattr(item, "end_line", 0),
                    "language": getattr(item, "language", ""),
                    "content": getattr(item, "content", ""),
                    "score": round(float(score), 4),
                    "chunk_index": getattr(item, "chunk_index", 0),
                })

        all_results.sort(key=lambda r: r["score"], reverse=True)
        return all_results[:top_k]

    # --- info ---------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a summary dict of the workspace."""
        return {
            "root": str(self._root),
            "repo_count": len(self._manifest.repos),
            "repos": [r.to_dict() for r in self._manifest.repos],
            "version": self._manifest.version,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _index_repo_into(
    repo_root: Path,
    index_dir: Path,
    config: AppConfig,
    force: bool = False,
) -> IndexingResult:
    """Run the indexing pipeline, storing artefacts into *index_dir*."""
    from semantic_code_intelligence.indexing.chunker import chunk_file
    from semantic_code_intelligence.storage.hash_store import HashStore

    result = IndexingResult()
    scanned = scan_repository(repo_root, config.index)
    result.files_scanned = len(scanned)

    if not scanned:
        return result

    hash_store = HashStore.load(index_dir)
    to_index = []

    if force:
        to_index = scanned
    else:
        for sf in scanned:
            if hash_store.has_changed(sf.relative_path, sf.content_hash):
                to_index.append(sf)
            else:
                result.files_skipped += 1

    all_chunks = []
    chunk_hashes: list[str] = []

    for sf in to_index:
        chunks = chunk_file(
            sf.path,
            chunk_size=config.embedding.chunk_size,
            chunk_overlap=config.embedding.chunk_overlap,
        )
        for c in chunks:
            all_chunks.append(c)
            chunk_hashes.append(sf.content_hash)
        result.files_indexed += 1

    result.chunks_created = len(all_chunks)

    if not all_chunks:
        for sf in to_index:
            hash_store.set(sf.relative_path, sf.content_hash)
        hash_store.save(index_dir)
        return result

    texts = [c.content for c in all_chunks]
    embeddings = generate_embeddings(texts, model_name=config.embedding.model_name)
    dimension = embeddings.shape[1]

    if force:
        store = VectorStore(dimension)
    else:
        try:
            store = VectorStore.load(index_dir)
        except FileNotFoundError:
            store = VectorStore(dimension)

    from semantic_code_intelligence.storage.vector_store import ChunkMetadata

    meta_list = [
        ChunkMetadata(
            file_path=c.file_path,
            start_line=c.start_line,
            end_line=c.end_line,
            chunk_index=c.chunk_index,
            language=c.language,
            content=c.content,
            content_hash=chunk_hashes[i],
        )
        for i, c in enumerate(all_chunks)
    ]

    store.add(embeddings, meta_list)
    store.save(index_dir)

    for sf in to_index:
        hash_store.set(sf.relative_path, sf.content_hash)
    hash_store.save(index_dir)

    result.total_vectors = store.size
    return result
