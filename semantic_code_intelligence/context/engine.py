"""Context engine — builds rich code context from parsed symbols.

Provides:
- ContextBuilder: assembles context windows around symbols
- CallGraph: AST-based call/reference graph (tree-sitter powered)
- DependencyMap: file-level dependency tracking from imports
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter

from semantic_code_intelligence.parsing.parser import (
    Symbol,
    detect_language,
    extract_imports,
    get_language,
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
    """AST-based call graph built from tree-sitter function-call nodes.

    Walks the AST of each callable symbol's body to find ``call`` nodes
    (function/method invocations).  The callee name is resolved from the
    AST node (``identifier`` / ``attribute`` / ``field_expression``) and
    matched against indexed symbol names to produce precise edges.

    Falls back to the regex heuristic only when tree-sitter cannot parse
    the file (e.g. unsupported language).
    """

    # Node types that represent a function/method call across languages
    _CALL_NODE_TYPES: set[str] = {
        "call",                     # Python, Ruby, PHP
        "call_expression",          # JS, TS, Go, Rust, C#, C++, Java
        "method_invocation",        # Java
        "invocation_expression",    # C#
    }

    def __init__(self) -> None:
        self._edges: list[CallEdge] = []
        self._callers: dict[str, list[CallEdge]] = {}  # callee -> list of callers
        self._callees: dict[str, list[CallEdge]] = {}  # caller -> list of callees

    # ----- public API -----

    def build(self, symbols: list[Symbol]) -> None:
        """Build the call graph from a list of symbols using AST analysis."""
        self._edges.clear()
        self._callers.clear()
        self._callees.clear()

        callable_symbols = [
            s for s in symbols if s.kind in ("function", "method", "class")
        ]
        callee_names: set[str] = {s.name for s in callable_symbols}

        # Group symbols by file so we parse each file once
        file_symbols: dict[str, list[Symbol]] = {}
        for sym in callable_symbols:
            file_symbols.setdefault(sym.file_path, []).append(sym)

        for file_path, syms in file_symbols.items():
            lang_name = detect_language(file_path)
            language_obj = get_language(lang_name) if lang_name else None

            for sym in syms:
                caller_key = f"{sym.file_path}:{sym.name}"
                if language_obj is not None:
                    call_names = self._extract_calls_ast(
                        sym.body, language_obj, callee_names, sym.name,
                    )
                else:
                    # Fallback: regex heuristic for unsupported languages
                    call_names = self._extract_calls_regex(
                        sym.body, callee_names, sym.name,
                    )

                for callee_name in call_names:
                    edge = CallEdge(
                        caller=caller_key,
                        callee=callee_name,
                        file_path=sym.file_path,
                        line=sym.start_line,
                    )
                    self._edges.append(edge)
                    self._callers.setdefault(callee_name, []).append(edge)
                    self._callees.setdefault(caller_key, []).append(edge)

    # ----- AST-based extraction -----

    def _extract_calls_ast(
        self,
        body: str,
        language: tree_sitter.Language,
        known_names: set[str],
        self_name: str,
    ) -> set[str]:
        """Extract function/method call names from *body* via tree-sitter AST.

        Returns the set of *known* callee names that appear as call
        targets in the AST (excluding self-references).
        """
        source = body.encode("utf-8")
        parser = tree_sitter.Parser(language)
        tree = parser.parse(source)

        found: set[str] = set()
        self._walk_calls(tree.root_node, source, known_names, self_name, found)
        return found

    def _walk_calls(
        self,
        node: tree_sitter.Node,
        source: bytes,
        known_names: set[str],
        self_name: str,
        found: set[str],
    ) -> None:
        """Recursively walk the AST collecting call-target names."""
        if node.type in self._CALL_NODE_TYPES:
            name = self._resolve_call_name(node, source)
            if name and name != self_name and name in known_names:
                found.add(name)

        for child in node.children:
            self._walk_calls(child, source, known_names, self_name, found)

    @staticmethod
    def _resolve_call_name(call_node: tree_sitter.Node, source: bytes) -> str | None:
        """Resolve the callee name from a call/call_expression node.

        Handles:
        - ``foo()``: direct identifier call
        - ``obj.method()``: attribute/member access — returns ``method``
        - ``pkg::func()``: scoped identifier (Rust/C++) — returns ``func``
        """
        # The function/target is typically the first named child
        func = call_node.child_by_field_name("function")
        if func is None:
            # Java method_invocation uses "name" field
            func = call_node.child_by_field_name("name")
        if func is None and call_node.children:
            func = call_node.children[0]
        if func is None:
            return None

        # Drill through attribute access to get the final name
        if func.type in ("attribute", "member_expression", "field_expression",
                         "scoped_identifier", "member_access_expression"):
            # The method name is the last named child / field "attribute"/"field"
            attr = func.child_by_field_name("attribute") or func.child_by_field_name("field")
            if attr is not None:
                return source[attr.start_byte:attr.end_byte].decode("utf-8", errors="replace")
            # Fallback: last named child
            for ch in reversed(func.children):
                if ch.is_named:
                    return source[ch.start_byte:ch.end_byte].decode("utf-8", errors="replace")
            return None

        if func.type == "identifier":
            return source[func.start_byte:func.end_byte].decode("utf-8", errors="replace")

        return None

    # ----- regex fallback -----

    @staticmethod
    def _extract_calls_regex(
        body: str,
        known_names: set[str],
        self_name: str,
    ) -> set[str]:
        """Fallback regex heuristic for unsupported languages."""
        found: set[str] = set()
        for name in known_names:
            if name == self_name:
                continue
            if re.search(r"\b" + re.escape(name) + r"\s*[\(\.]", body):
                found.add(name)
        return found

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

    def __repr__(self) -> str:
        return f"CallGraph(edges={len(self._edges)})"


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

    def __repr__(self) -> str:
        return f"DependencyMap(files={len(self._dependencies)})"
