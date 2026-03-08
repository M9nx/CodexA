"""Context engine — builds rich code context from parsed symbols.

Provides:
- ContextBuilder: assembles context windows around symbols
- CallGraph: lightweight call/reference graph
- DependencyMap: file-level dependency tracking from imports
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.parsing.parser import (
    Symbol,
    extract_imports,
    parse_file,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("context")


# ---------------------------------------------------------------------------
# Context Builder
# ---------------------------------------------------------------------------

@dataclass
class ContextWindow:
    """A context window consisting of a focal symbol and surrounding context."""

    focal_symbol: Symbol
    related_symbols: list[Symbol] = field(default_factory=list)
    imports: list[Symbol] = field(default_factory=list)
    file_content: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the context window to a plain dictionary."""
        return {
            "focal_symbol": self.focal_symbol.to_dict(),
            "related_symbols": [s.to_dict() for s in self.related_symbols],
            "imports": [s.to_dict() for s in self.imports],
        }

    def render(self, max_lines: int = 50) -> str:
        """Render a human-readable context summary."""
        lines: list[str] = []
        lines.append(f"=== {self.focal_symbol.kind}: {self.focal_symbol.name} ===")
        lines.append(f"File: {self.focal_symbol.file_path}")
        lines.append(f"Lines: {self.focal_symbol.start_line}-{self.focal_symbol.end_line}")
        lines.append("")

        if self.imports:
            lines.append("-- Imports --")
            for imp in self.imports[:5]:
                lines.append(f"  {imp.body.strip()}")
            lines.append("")

        lines.append("-- Source --")
        body_lines = self.focal_symbol.body.split("\n")
        for line in body_lines[:max_lines]:
            lines.append(f"  {line}")
        if len(body_lines) > max_lines:
            lines.append(f"  ... ({len(body_lines) - max_lines} more lines)")

        if self.related_symbols:
            lines.append("")
            lines.append("-- Related symbols --")
            for sym in self.related_symbols[:10]:
                lines.append(f"  {sym.kind} {sym.name} (L{sym.start_line})")

        return "\n".join(lines)


class ContextBuilder:
    """Builds context windows for symbols within a repository."""

    def __init__(self) -> None:
        self._file_symbols: dict[str, list[Symbol]] = {}
        self._file_contents: dict[str, str] = {}

    def index_file(self, file_path: str, content: str | None = None) -> list[Symbol]:
        """Parse and index a file, returning its symbols."""
        if content is None:
            try:
                content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                return []

        symbols = parse_file(file_path, content)
        self._file_symbols[file_path] = symbols
        self._file_contents[file_path] = content
        return symbols

    def get_symbols(self, file_path: str) -> list[Symbol]:
        """Get cached symbols for a file."""
        return self._file_symbols.get(file_path, [])

    def get_all_symbols(self) -> list[Symbol]:
        """Get all indexed symbols across all files."""
        result: list[Symbol] = []
        for symbols in self._file_symbols.values():
            result.extend(symbols)
        return result

    def find_symbol(self, name: str, kind: str | None = None) -> list[Symbol]:
        """Find symbols by name, optionally filtered by kind."""
        results: list[Symbol] = []
        for symbols in self._file_symbols.values():
            for s in symbols:
                if s.name == name:
                    if kind is None or s.kind == kind:
                        results.append(s)
        return results

    def build_context(self, symbol: Symbol) -> ContextWindow:
        """Build a context window around a specific symbol."""
        file_path = symbol.file_path
        symbols = self._file_symbols.get(file_path, [])
        content = self._file_contents.get(file_path, "")

        # Gather imports from the same file
        imports = [s for s in symbols if s.kind == "import"]

        # Gather related symbols (same file, excluding the focal one)
        related = [
            s for s in symbols
            if s is not symbol and s.kind != "import"
        ]

        return ContextWindow(
            focal_symbol=symbol,
            related_symbols=related,
            imports=imports,
            file_content=content,
        )

    def build_context_for_name(self, name: str) -> list[ContextWindow]:
        """Build context windows for all symbols matching a name."""
        symbols = self.find_symbol(name)
        return [self.build_context(s) for s in symbols]


# ---------------------------------------------------------------------------
# Call Graph (lightweight reference-based)
# ---------------------------------------------------------------------------

@dataclass
class CallEdge:
    """An edge in the call graph."""

    caller: str  # "file:name" or just "name"
    callee: str
    file_path: str
    line: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the call edge to a plain dictionary."""
        return {
            "caller": self.caller,
            "callee": self.callee,
            "file_path": self.file_path,
            "line": self.line,
        }


class CallGraph:
    """Lightweight call graph built from symbol name references.

    This uses a simple heuristic: if symbol A's body contains the name
    of symbol B, we record A -> B as a potential call edge. This is
    not a full static analysis but provides useful signal.
    """

    def __init__(self) -> None:
        self._edges: list[CallEdge] = []
        self._callers: dict[str, list[CallEdge]] = {}  # callee -> list of callers
        self._callees: dict[str, list[CallEdge]] = {}  # caller -> list of callees

    def build(self, symbols: list[Symbol]) -> None:
        """Build the call graph from a list of symbols."""
        self._edges.clear()
        self._callers.clear()
        self._callees.clear()

        # Only consider function/method/class definitions as potential callers
        callable_symbols = [
            s for s in symbols if s.kind in ("function", "method", "class")
        ]
        # All function/method names as potential callees
        callee_names = {s.name for s in callable_symbols}

        for sym in callable_symbols:
            body_text = sym.body
            caller_key = f"{sym.file_path}:{sym.name}"

            for callee_name in callee_names:
                if callee_name == sym.name:
                    continue  # skip self-references
                if callee_name in body_text:
                    edge = CallEdge(
                        caller=caller_key,
                        callee=callee_name,
                        file_path=sym.file_path,
                        line=sym.start_line,
                    )
                    self._edges.append(edge)
                    self._callers.setdefault(callee_name, []).append(edge)
                    self._callees.setdefault(caller_key, []).append(edge)

    @property
    def edges(self) -> list[CallEdge]:
        """Return a shallow copy of all call-graph edges."""
        return list(self._edges)

    def callers_of(self, name: str) -> list[CallEdge]:
        """Get all edges where `name` is the callee."""
        return self._callers.get(name, [])

    def callees_of(self, caller_key: str) -> list[CallEdge]:
        """Get all edges where `caller_key` is the caller."""
        return self._callees.get(caller_key, [])

    def to_dict(self) -> dict[str, Any]:
        """Serialize the call graph to a summary dictionary."""
        return {
            "edges": [e.to_dict() for e in self._edges],
            "node_count": len(
                {e.caller for e in self._edges} | {e.callee for e in self._edges}
            ),
            "edge_count": len(self._edges),
        }


# ---------------------------------------------------------------------------
# Dependency Map (file-level imports)
# ---------------------------------------------------------------------------

@dataclass
class FileDependency:
    """A file-level dependency."""

    source_file: str
    import_text: str
    line: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the file dependency to a plain dictionary."""
        return {
            "source_file": self.source_file,
            "import_text": self.import_text,
            "line": self.line,
        }


class DependencyMap:
    """Tracks file-level dependencies based on import statements."""

    def __init__(self) -> None:
        self._dependencies: dict[str, list[FileDependency]] = {}

    def add_file(self, file_path: str, content: str | None = None) -> list[FileDependency]:
        """Parse imports from a file and record as dependencies."""
        imports = extract_imports(file_path, content)
        deps: list[FileDependency] = []
        for imp in imports:
            dep = FileDependency(
                source_file=file_path,
                import_text=imp.body.strip(),
                line=imp.start_line,
            )
            deps.append(dep)
        self._dependencies[file_path] = deps
        return deps

    def get_dependencies(self, file_path: str) -> list[FileDependency]:
        """Get dependencies for a specific file."""
        return self._dependencies.get(file_path, [])

    def get_all_files(self) -> list[str]:
        """Get all tracked files."""
        return list(self._dependencies.keys())

    def get_dependents(self, module_name: str) -> list[FileDependency]:
        """Find all files that import a given module name."""
        results: list[FileDependency] = []
        for deps in self._dependencies.values():
            for dep in deps:
                if module_name in dep.import_text:
                    results.append(dep)
        return results

    def to_dict(self) -> dict[str, Any]:
        """Serialize all tracked file dependencies to a dictionary."""
        return {
            file: [d.to_dict() for d in deps]
            for file, deps in self._dependencies.items()
        }
