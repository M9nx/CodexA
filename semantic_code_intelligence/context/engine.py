"""Context engine — builds rich code context from parsed symbols.

Provides:
- ContextBuilder: assembles context windows around symbols
- CallGraph: AST-based call/reference graph (tree-sitter powered)
- DependencyMap: file-level dependency tracking from imports
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter

from semantic_code_intelligence.parsing.parser import (
    NAME_NODE_TYPES,
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

    def has_file(self, file_path: str) -> bool:
        """Return True if *file_path* is already indexed."""
        return file_path in self._file_contents

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
        return asdict(self)


class CallGraph:
    """AST-based call graph built from tree-sitter function-call nodes.

    Walks the AST of each callable symbol's body to find call nodes
    (function/method invocations, static calls, and instantiations).
    The callee name(s) are resolved from the AST node — ``identifier``,
    attribute/member access chains, PHP ``Class::method()`` scopes, and
    ``new ClassName()`` targets — and matched against indexed symbol
    names to produce precise edges.

    Falls back to the regex heuristic only when tree-sitter cannot parse
    the file (e.g. unsupported language).
    """

    # Node types that represent a function/method call across languages
    _CALL_NODE_TYPES: set[str] = {
        "call",                             # Python, Ruby
        "call_expression",                  # JS, TS, Go, Rust, C++, Java
        "function_call_expression",         # PHP: plain function calls
        "scoped_call_expression",           # PHP: Class::method()
        "member_call_expression",           # PHP: $obj->method()
        "nullsafe_member_call_expression",  # PHP: $obj?->method()
        "method_invocation",                # Java
        "invocation_expression",            # C#
        "object_creation_expression",       # PHP, Java, C#: new ClassName()
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
                        lang_name,
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
        lang_name: str | None = None,
    ) -> set[str]:
        """Extract function/method call names from *body* via tree-sitter.

        Returns the set of *known* callee names that appear as call
        targets in the AST (excluding self-references).
        """
        # PHP's merged grammar treats a bare snippet without an opening
        # tag as inline HTML, silently hiding every call node.  Symbol
        # bodies are snippets, so restore the program context.
        if lang_name == "php" and not body.lstrip().startswith("<?php"):
            body = "<?php\n" + body

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
        """Collect call-target names from the AST into *found*.

        Uses an explicit stack instead of recursion: deeply nested trees
        (generated or minified files) must not trip Python's recursion
        limit, which would fail the whole call-graph build.
        """
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type in self._CALL_NODE_TYPES:
                for candidate in self._resolve_call_candidates(current, source):
                    if candidate and candidate != self_name and candidate in known_names:
                        found.add(candidate)
            stack.extend(current.children)

    @staticmethod
    def _resolve_call_candidates(
        call_node: tree_sitter.Node, source: bytes
    ) -> list[str]:
        """Resolve the callee name candidates from a call node.

        Some call shapes name more than one target, e.g. PHP's
        ``ConnectionFactory::make()`` names both the class (scope) and the
        method — both are useful callees, so all candidates are returned
        and the caller keeps only those matching indexed symbol names.
        """
        def text(node: tree_sitter.Node) -> str:
            return source[node.start_byte:node.end_byte].decode(
                "utf-8", errors="replace"
            )

        def last_segment(qualified: str) -> str:
            # ``App\Namespace\Class``, ``pkg::func`` -> trailing name
            return re.split(r"[:\\]+", qualified.strip())[-1]

        node_type = call_node.type

        if node_type == "scoped_call_expression":
            candidates: list[str] = []
            scope = call_node.child_by_field_name("scope")
            if scope is not None:
                candidates.append(last_segment(text(scope)))
            member = call_node.child_by_field_name("name")
            if member is not None:
                candidates.append(text(member))
            return candidates

        if node_type in ("member_call_expression",
                         "nullsafe_member_call_expression"):
            member = call_node.child_by_field_name("name")
            return [text(member)] if member is not None else []

        if node_type == "object_creation_expression":
            # Java / C# carry the instantiated type in a "type" field
            type_node = call_node.child_by_field_name("type")
            if type_node is not None:
                return [last_segment(text(type_node))]
            # PHP has no fields here: the class name is the first named
            # child before the argument list.
            for child in call_node.named_children:
                if child.type not in ("arguments", "argument_list"):
                    return [last_segment(text(child))]
            return []

        # Generic shapes: call / call_expression / function_call_expression /
        # method_invocation / invocation_expression
        func = call_node.child_by_field_name("function")
        if func is None:
            # Java method_invocation uses "name" field
            func = call_node.child_by_field_name("name")
        if func is None and call_node.children:
            func = call_node.children[0]
        if func is None:
            return []

        # Drill through attribute access to get the final name
        if func.type in ("attribute", "member_expression", "field_expression",
                         "scoped_identifier", "member_access_expression"):
            # The method name is the last named child / field "attribute"/"field"
            attr = func.child_by_field_name("attribute") or func.child_by_field_name("field")
            if attr is not None:
                return [source[attr.start_byte:attr.end_byte].decode(
                    "utf-8", errors="replace")]
            # Fallback: last named child
            for ch in reversed(func.children):
                if ch.is_named:
                    return [last_segment(
                        source[ch.start_byte:ch.end_byte].decode(
                            "utf-8", errors="replace"))]
            return []

        if func.type in NAME_NODE_TYPES:
            return [last_segment(source[func.start_byte:func.end_byte].decode(
                "utf-8", errors="replace"))]

        return []

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
# Symbol References (tree-sitter identifier scan)
# ---------------------------------------------------------------------------

def find_references(
    builder: ContextBuilder, symbol_name: str
) -> list[dict[str, Any]]:
    """Find definitions and usages of *symbol_name* across indexed files.

    Definitions are exact symbol-name matches already indexed by the
    builder.  Usages are detected by scanning every indexed file with
    tree-sitter for identifier nodes whose text is exactly *symbol_name*
    (word-complete: ``MyConnectionFactory`` does not match
    ``ConnectionFactory``), with a line-oriented word-boundary regex
    fallback for languages whose grammar is unavailable.

    Each returned entry has a ``match`` key — ``definition`` or ``usage``.
    Usage entries carry the precise occurrence ``line`` plus the smallest
    enclosing symbol (``referencing_symbol`` / ``kind`` / ``start_line`` /
    ``end_line``) or ``referencing_symbol: None`` for top-level code.
    """
    definitions = builder.find_symbol(symbol_name)

    usage_entries: list[dict[str, Any]] = []
    def_positions = {
        (sym.file_path, sym.start_line, sym.name_column)
        for sym in definitions
    }

    for file_path in sorted(builder._file_contents):
        content = builder._file_contents[file_path]
        lines = content.split("\n")
        line_symbols = builder.get_symbols(file_path)

        for line_no, col in _scan_identifiers(file_path, content, symbol_name):
            if (file_path, line_no, col) in def_positions:
                # The definition's own name token only — other hits on the
                # same line (one-liner usages, type hints) are references.
                continue
            entry: dict[str, Any] = {
                "match": "usage",
                "file_path": file_path,
                "line": line_no,
                "column": _char_column(content, line_no, col) + 1,
            }
            enclosing = _enclosing_symbol(line_symbols, line_no)
            if enclosing is not None:
                entry.update({
                    "referencing_symbol": enclosing.name,
                    "kind": enclosing.kind,
                    "start_line": enclosing.start_line,
                    "end_line": enclosing.end_line,
                })
            else:
                entry.update({
                    "referencing_symbol": None,
                    "kind": lines[line_no - 1].strip()[:80] if line_no <= len(lines) else "",
                    "start_line": line_no,
                    "end_line": line_no,
                })
            usage_entries.append(entry)

    result = [{**s.to_dict(), "match": "definition"} for s in definitions]
    result.extend(usage_entries)
    return result


def _scan_identifiers(
    file_path: str, content: str, symbol_name: str
) -> list[tuple[int, int]]:
    """Return (line, byte column) of *symbol_name* identifier occurrences.

    Uses tree-sitter name nodes when a grammar is available for the file
    type (tree-sitter columns are byte offsets); falls back to a
    word-boundary regex scan otherwise, converted to the same byte
    columns.  Byte columns make the definition-token skip directly
    comparable with the byte-based ``Symbol.name_column``; user-facing
    values are converted to character offsets by ``_char_column``.
    """
    lang_name = detect_language(file_path)
    language_obj = get_language(lang_name) if lang_name else None
    if language_obj is None:
        pattern = re.compile(r"\b" + re.escape(symbol_name) + r"\b")
        regex_hits: list[tuple[int, int]] = []
        for idx, line in enumerate(content.split("\n"), start=1):
            for m in pattern.finditer(line):
                # Match offsets are character offsets; report byte columns
                # for consistency with the tree-sitter path.
                regex_hits.append((idx, len(line[:m.start()].encode("utf-8"))))
        return regex_hits

    hits: list[tuple[int, int]] = []
    source = content.encode("utf-8")
    parser = tree_sitter.Parser(language_obj)
    tree = parser.parse(source)

    # Explicit stack instead of recursion: deeply nested trees (generated
    # or minified files) must not trip Python's recursion limit.
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in NAME_NODE_TYPES:
            text = source[node.start_byte:node.end_byte].decode(
                "utf-8", errors="replace")
            if text == symbol_name:
                hits.append((node.start_point[0] + 1, node.start_point[1]))
        stack.extend(reversed(node.children))
    return hits


def _char_column(content: str, line_no: int, byte_col: int) -> int:
    """Convert a 0-based byte offset into a 0-based character offset.

    Both `_scan_identifiers` paths report byte columns: tree-sitter
    columns are byte offsets and the regex paths converts its character
    match offsets to bytes, keeping definition-token comparison against
    ``Symbol.name_column`` (byte-based) consistent.  User-facing values
    are converted to character offsets only here.
    """
    lines = content.split("\n")
    if line_no < 1 or line_no > len(lines):
        return byte_col
    return len(lines[line_no - 1].encode("utf-8")[:byte_col].decode(
        "utf-8", errors="replace"))


def _enclosing_symbol(symbols: list[Symbol], line: int) -> Symbol | None:
    """Return the innermost symbol whose line span contains *line*."""
    best: Symbol | None = None
    for sym in symbols:
        if sym.kind == "import":
            continue
        if sym.start_line <= line <= sym.end_line:
            if best is None or sym.end_line - sym.start_line < (
                    best.end_line - best.start_line):
                best = sym
    return best


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
        return asdict(self)


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
