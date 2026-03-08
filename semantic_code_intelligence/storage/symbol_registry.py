"""Symbol registry — persistent, queryable directory of code symbols.

Stores every function, class, and method extracted from the codebase,
enabling fast lookups by name, kind, file, or parent class without
re-parsing source files.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

REGISTRY_FILE = "symbol_registry.json"


@dataclass
class SymbolEntry:
    """A single symbol record in the registry."""

    name: str
    kind: str  # "function", "class", "method", "import"
    file_path: str
    start_line: int
    end_line: int
    parent: str | None = None
    parameters: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    language: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SymbolEntry:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @property
    def qualified_name(self) -> str:
        """Return ``Parent.name`` for methods, else just ``name``."""
        if self.parent:
            return f"{self.parent}.{self.name}"
        return self.name


class SymbolRegistry:
    """Persistent symbol directory backed by JSON.

    Supports incremental updates (clear symbols for a file, then re-add),
    multi-criteria lookups, and disk persistence.
    """

    def __init__(self) -> None:
        self._symbols: list[SymbolEntry] = []
        # Secondary index: file_path → list of indices into _symbols
        self._by_file: dict[str, list[int]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, entry: SymbolEntry) -> None:
        """Add a symbol entry to the registry."""
        idx = len(self._symbols)
        self._symbols.append(entry)
        self._by_file.setdefault(entry.file_path, []).append(idx)

    def add_many(self, entries: list[SymbolEntry]) -> None:
        """Bulk-add symbol entries."""
        for entry in entries:
            self.add(entry)

    def remove_file(self, file_path: str) -> int:
        """Remove all symbols belonging to *file_path*.

        Returns the number of entries removed.
        """
        indices = self._by_file.pop(file_path, [])
        if not indices:
            return 0
        removed = len(indices)
        keep = set(range(len(self._symbols))) - set(indices)
        self._symbols = [self._symbols[i] for i in sorted(keep)]
        self._rebuild_file_index()
        return removed

    def clear(self) -> None:
        """Remove all symbols."""
        self._symbols.clear()
        self._by_file.clear()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._symbols)

    @property
    def files(self) -> list[str]:
        """Return all tracked file paths."""
        return list(self._by_file.keys())

    def find_by_name(self, name: str) -> list[SymbolEntry]:
        """Find all symbols with the exact *name*."""
        return [s for s in self._symbols if s.name == name]

    def find_by_kind(self, kind: str) -> list[SymbolEntry]:
        """Find all symbols of a given *kind* (function, class, method, import)."""
        return [s for s in self._symbols if s.kind == kind]

    def find_by_file(self, file_path: str) -> list[SymbolEntry]:
        """Return all symbols in the given file."""
        indices = self._by_file.get(file_path, [])
        return [self._symbols[i] for i in indices]

    def find(
        self,
        name: str | None = None,
        kind: str | None = None,
        file_path: str | None = None,
        parent: str | None = None,
        language: str | None = None,
    ) -> list[SymbolEntry]:
        """Multi-criteria symbol lookup.  ``None`` fields are not filtered."""
        results: list[SymbolEntry] = []
        for sym in self._iter_candidates(file_path):
            if name is not None and sym.name != name:
                continue
            if kind is not None and sym.kind != kind:
                continue
            if parent is not None and sym.parent != parent:
                continue
            if language is not None and sym.language != language:
                continue
            results.append(sym)
        return results

    def search_name(self, substring: str) -> list[SymbolEntry]:
        """Return symbols whose name contains *substring* (case-insensitive)."""
        lower = substring.lower()
        return [s for s in self._symbols if lower in s.name.lower()]

    def language_summary(self) -> dict[str, int]:
        """Return a count of symbols per language."""
        counts: dict[str, int] = {}
        for s in self._symbols:
            lang = s.language or "unknown"
            counts[lang] = counts.get(lang, 0) + 1
        return counts

    def kind_summary(self) -> dict[str, int]:
        """Return a count of symbols per kind."""
        counts: dict[str, int] = {}
        for s in self._symbols:
            counts[s.kind] = counts.get(s.kind, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Write registry to disk as JSON."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        data = [s.to_dict() for s in self._symbols]
        (path / REGISTRY_FILE).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: str | Path) -> SymbolRegistry:
        """Load registry from disk.  Returns empty registry if absent."""
        registry = cls()
        path = Path(directory) / REGISTRY_FILE
        if not path.exists():
            return registry
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        registry.add(SymbolEntry.from_dict(item))
        except (json.JSONDecodeError, OSError):
            pass
        return registry

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild_file_index(self) -> None:
        self._by_file.clear()
        for i, sym in enumerate(self._symbols):
            self._by_file.setdefault(sym.file_path, []).append(i)

    def _iter_candidates(self, file_path: str | None) -> Iterator[SymbolEntry]:
        if file_path is not None:
            indices = self._by_file.get(file_path, [])
            for i in indices:
                yield self._symbols[i]
        else:
            yield from self._symbols
