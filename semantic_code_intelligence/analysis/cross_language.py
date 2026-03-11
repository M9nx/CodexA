"""Cross-language intelligence — unified code intelligence across language boundaries.

Provides:
- Cross-language symbol resolution (Python→Rust FFI, JS→WASM, etc.)
- Polyglot dependency graphs spanning multiple languages
- Language-aware search boosting
- Universal call graph across the entire workspace
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.context.engine import (
    CallEdge,
    CallGraph,
    DependencyMap,
    FileDependency,
)
from semantic_code_intelligence.parsing.parser import (
    EXTENSION_TO_LANGUAGE,
    Symbol,
    parse_file,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("cross_language")


# ---------------------------------------------------------------------------
# FFI / cross-language binding patterns
# ---------------------------------------------------------------------------

# Patterns that indicate cross-language calls
FFI_PATTERNS: dict[str, list[dict[str, str]]] = {
    "python_rust": [
        {"import_pattern": "import codexa_core", "target_lang": "rust"},
        {"import_pattern": "from codexa_core", "target_lang": "rust"},
        {"import_pattern": "pyo3", "target_lang": "rust"},
    ],
    "python_c": [
        {"import_pattern": "ctypes", "target_lang": "cpp"},
        {"import_pattern": "cffi", "target_lang": "cpp"},
    ],
    "js_wasm": [
        {"import_pattern": "WebAssembly", "target_lang": "rust"},
        {"import_pattern": ".wasm", "target_lang": "rust"},
    ],
    "java_jni": [
        {"import_pattern": "native ", "target_lang": "cpp"},
        {"import_pattern": "System.loadLibrary", "target_lang": "cpp"},
    ],
}


@dataclass
class CrossLanguageEdge:
    """An edge connecting symbols across language boundaries."""

    source_symbol: str
    source_language: str
    source_file: str
    target_symbol: str
    target_language: str
    target_file: str = ""
    binding_type: str = ""  # ffi, import, wasm, jni

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_symbol": self.source_symbol,
            "source_language": self.source_language,
            "source_file": self.source_file,
            "target_symbol": self.target_symbol,
            "target_language": self.target_language,
            "target_file": self.target_file,
            "binding_type": self.binding_type,
        }


@dataclass
class PolyglotDependency:
    """A dependency that crosses language boundaries."""

    source_file: str
    source_language: str
    target_module: str
    target_language: str
    import_text: str
    line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_language": self.source_language,
            "target_module": self.target_module,
            "target_language": self.target_language,
            "import_text": self.import_text,
            "line": self.line,
        }


class CrossLanguageResolver:
    """Resolves symbols and dependencies across language boundaries.

    Scans FFI patterns, import statements, and binding declarations
    to build a unified cross-language graph.
    """

    def __init__(self) -> None:
        self._symbols_by_lang: dict[str, dict[str, Symbol]] = {}
        self._cross_edges: list[CrossLanguageEdge] = []
        self._polyglot_deps: list[PolyglotDependency] = []
        self._dep_map = DependencyMap()

    def index_file(self, file_path: str, content: str | None = None) -> None:
        """Parse and index a file's symbols by language."""
        ext = Path(file_path).suffix
        language = EXTENSION_TO_LANGUAGE.get(ext, "unknown")
        if language == "unknown":
            return

        symbols = parse_file(file_path, content)
        if language not in self._symbols_by_lang:
            self._symbols_by_lang[language] = {}
        for sym in symbols:
            if sym.kind != "import":
                self._symbols_by_lang[language][sym.name] = sym

        # Track dependencies for polyglot graph
        self._dep_map.add_file(file_path, content)

    def index_directory(self, root: str) -> int:
        """Recursively index all supported files under root."""
        root_path = Path(root)
        count = 0
        for ext in EXTENSION_TO_LANGUAGE:
            for fp in root_path.rglob(f"*{ext}"):
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                    self.index_file(str(fp), content)
                    count += 1
                except (OSError, PermissionError):
                    pass
        return count

    def resolve_cross_language_symbols(self) -> list[CrossLanguageEdge]:
        """Detect cross-language symbol references via FFI patterns.

        Scans import statements and FFI bindings to find where one
        language calls into another.
        """
        self._cross_edges.clear()

        for file_path in self._dep_map.get_all_files():
            ext = Path(file_path).suffix
            source_lang = EXTENSION_TO_LANGUAGE.get(ext, "unknown")
            deps = self._dep_map.get_dependencies(file_path)

            for dep in deps:
                target_lang = self._detect_cross_lang_target(dep, source_lang)
                if target_lang and target_lang != source_lang:
                    self._polyglot_deps.append(PolyglotDependency(
                        source_file=file_path,
                        source_language=source_lang,
                        target_module=dep.import_text,
                        target_language=target_lang,
                        import_text=dep.import_text,
                        line=dep.line,
                    ))

                    # Try to resolve specific symbols
                    target_symbols = self._symbols_by_lang.get(target_lang, {})
                    for sym_name, sym in target_symbols.items():
                        if sym_name in dep.import_text:
                            self._cross_edges.append(CrossLanguageEdge(
                                source_symbol=dep.import_text,
                                source_language=source_lang,
                                source_file=file_path,
                                target_symbol=sym_name,
                                target_language=target_lang,
                                target_file=sym.file_path,
                                binding_type="ffi",
                            ))

        return self._cross_edges

    def _detect_cross_lang_target(
        self, dep: FileDependency, source_lang: str,
    ) -> str | None:
        """Detect if a dependency points to a different language."""
        import_text = dep.import_text.lower()

        for _pattern_set, patterns in FFI_PATTERNS.items():
            for p in patterns:
                if p["import_pattern"].lower() in import_text:
                    return p["target_lang"]

        return None

    def get_polyglot_dependencies(self) -> list[PolyglotDependency]:
        """Return all cross-language dependencies."""
        return list(self._polyglot_deps)

    def build_universal_call_graph(self) -> CallGraph:
        """Build a call graph spanning all indexed languages.

        Merges per-language call graphs and adds cross-language edges.
        """
        all_symbols: list[Symbol] = []
        for lang_symbols in self._symbols_by_lang.values():
            all_symbols.extend(lang_symbols.values())

        graph = CallGraph()
        graph.build(all_symbols)

        # Add cross-language edges
        for edge in self._cross_edges:
            call_edge = CallEdge(
                caller=f"{edge.source_file}:{edge.source_symbol}",
                callee=edge.target_symbol,
                file_path=edge.source_file,
                line=0,
            )
            graph._edges.append(call_edge)
            graph._callers.setdefault(edge.target_symbol, []).append(call_edge)
            caller_key = f"{edge.source_file}:{edge.source_symbol}"
            graph._callees.setdefault(caller_key, []).append(call_edge)

        return graph

    def to_dict(self) -> dict[str, Any]:
        """Serialize the cross-language intelligence state."""
        return {
            "languages": {
                lang: len(syms) for lang, syms in self._symbols_by_lang.items()
            },
            "cross_edges": [e.to_dict() for e in self._cross_edges],
            "polyglot_deps": [d.to_dict() for d in self._polyglot_deps],
            "total_symbols": sum(
                len(s) for s in self._symbols_by_lang.values()
            ),
        }


def boost_search_by_language(
    results: list[dict[str, Any]],
    context_language: str | None,
    boost_factor: float = 1.5,
) -> list[dict[str, Any]]:
    """Re-rank search results by boosting results in the context language.

    When a user is editing a Python file, results from Python files are
    boosted relative to results from other languages.
    """
    if not context_language:
        return results

    for r in results:
        file_path = r.get("file_path", "")
        ext = Path(file_path).suffix
        result_lang = EXTENSION_TO_LANGUAGE.get(ext, "unknown")
        if result_lang == context_language:
            r["score"] = r.get("score", 0) * boost_factor
            r["boosted"] = True

    # Re-sort by score descending
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results
