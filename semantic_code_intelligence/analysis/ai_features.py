"""AI features — repository summary, AI-friendly output, code explanation helpers.

Provides tools to generate structured summaries of a codebase suitable
for feeding into LLMs or other AI systems.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.context.engine import (
    CallGraph,
    ContextBuilder,
    DependencyMap,
)
from semantic_code_intelligence.parsing.parser import Symbol
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("analysis")


# ---------------------------------------------------------------------------
# Repository Summary
# ---------------------------------------------------------------------------

@dataclass
class LanguageStats:
    """Statistics for a single programming language."""

    language: str
    file_count: int = 0
    function_count: int = 0
    class_count: int = 0
    method_count: int = 0
    import_count: int = 0
    total_lines: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "file_count": self.file_count,
            "function_count": self.function_count,
            "class_count": self.class_count,
            "method_count": self.method_count,
            "import_count": self.import_count,
            "total_lines": self.total_lines,
        }


@dataclass
class RepoSummary:
    """A summary of a repository's code structure."""

    total_files: int = 0
    total_symbols: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_methods: int = 0
    total_imports: int = 0
    languages: list[LanguageStats] = field(default_factory=list)
    top_functions: list[dict[str, Any]] = field(default_factory=list)
    top_classes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_symbols": self.total_symbols,
            "total_functions": self.total_functions,
            "total_classes": self.total_classes,
            "total_methods": self.total_methods,
            "total_imports": self.total_imports,
            "languages": [l.to_dict() for l in self.languages],
            "top_functions": self.top_functions,
            "top_classes": self.top_classes,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def render(self) -> str:
        """Render a human-readable summary."""
        lines: list[str] = []
        lines.append("=== Repository Summary ===")
        lines.append(f"Files: {self.total_files}")
        lines.append(f"Total symbols: {self.total_symbols}")
        lines.append(f"Functions: {self.total_functions}")
        lines.append(f"Classes: {self.total_classes}")
        lines.append(f"Methods: {self.total_methods}")
        lines.append(f"Imports: {self.total_imports}")
        lines.append("")

        if self.languages:
            lines.append("-- Languages --")
            for lang in self.languages:
                lines.append(
                    f"  {lang.language}: {lang.file_count} files, "
                    f"{lang.function_count} functions, "
                    f"{lang.class_count} classes"
                )
            lines.append("")

        if self.top_functions:
            lines.append("-- Top Functions --")
            for f in self.top_functions[:10]:
                lines.append(f"  {f['name']} ({f['file_path']}, L{f['start_line']})")
            lines.append("")

        if self.top_classes:
            lines.append("-- Top Classes --")
            for c in self.top_classes[:10]:
                lines.append(f"  {c['name']} ({c['file_path']}, L{c['start_line']})")

        return "\n".join(lines)


def summarize_repository(builder: ContextBuilder) -> RepoSummary:
    """Generate a structured summary from an indexed ContextBuilder.

    Args:
        builder: A ContextBuilder that has already indexed files.

    Returns:
        A RepoSummary with aggregated statistics.
    """
    all_symbols = builder.get_all_symbols()
    summary = RepoSummary()

    # Group symbols by language (via file extension)
    from semantic_code_intelligence.parsing.parser import detect_language

    lang_data: dict[str, LanguageStats] = {}
    files_seen: set[str] = set()

    for sym in all_symbols:
        lang = detect_language(sym.file_path) or "unknown"
        if lang not in lang_data:
            lang_data[lang] = LanguageStats(language=lang)
        stats = lang_data[lang]

        if sym.file_path not in files_seen:
            files_seen.add(sym.file_path)
            stats.file_count += 1

        if sym.kind == "function":
            stats.function_count += 1
        elif sym.kind == "class":
            stats.class_count += 1
        elif sym.kind == "method":
            stats.method_count += 1
        elif sym.kind == "import":
            stats.import_count += 1

    summary.total_files = len(files_seen)
    summary.total_symbols = len(all_symbols)
    summary.total_functions = sum(s.function_count for s in lang_data.values())
    summary.total_classes = sum(s.class_count for s in lang_data.values())
    summary.total_methods = sum(s.method_count for s in lang_data.values())
    summary.total_imports = sum(s.import_count for s in lang_data.values())
    summary.languages = sorted(lang_data.values(), key=lambda x: x.file_count, reverse=True)

    # Top functions (longest body = most complex)
    functions = [s for s in all_symbols if s.kind == "function"]
    functions.sort(key=lambda s: s.end_line - s.start_line, reverse=True)
    summary.top_functions = [f.to_dict() for f in functions[:10]]

    # Top classes
    classes = [s for s in all_symbols if s.kind == "class"]
    classes.sort(key=lambda s: s.end_line - s.start_line, reverse=True)
    summary.top_classes = [c.to_dict() for c in classes[:10]]

    return summary


# ---------------------------------------------------------------------------
# AI-friendly JSON output
# ---------------------------------------------------------------------------

def generate_ai_context(
    builder: ContextBuilder,
    symbol_name: str | None = None,
    file_path: str | None = None,
    include_call_graph: bool = True,
    include_dependencies: bool = True,
) -> dict[str, Any]:
    """Generate AI-friendly structured JSON context for a codebase.

    This is designed to be fed into an LLM for code understanding,
    question answering, or code generation tasks.

    Args:
        builder: An indexed ContextBuilder.
        symbol_name: Optional symbol to focus the context on.
        file_path: Optional file to focus the context on.
        include_call_graph: Whether to include call graph data.
        include_dependencies: Whether to include dependency data.

    Returns:
        A dictionary suitable for JSON serialization.
    """
    result: dict[str, Any] = {}

    # Summary
    summary = summarize_repository(builder)
    result["summary"] = summary.to_dict()

    # Focused context
    if symbol_name:
        contexts = builder.build_context_for_name(symbol_name)
        result["focused_contexts"] = [c.to_dict() for c in contexts]
    elif file_path:
        symbols = builder.get_symbols(file_path)
        result["file_symbols"] = [s.to_dict() for s in symbols]

    # Call graph
    if include_call_graph:
        all_symbols = builder.get_all_symbols()
        graph = CallGraph()
        graph.build(all_symbols)
        result["call_graph"] = graph.to_dict()

    # Dependencies
    if include_dependencies:
        dep_map = DependencyMap()
        # We need to re-parse files for imports; use the builder's cached content
        for fp in builder._file_contents:
            dep_map.add_file(fp, builder._file_contents[fp])
        result["dependencies"] = dep_map.to_dict()

    return result


# ---------------------------------------------------------------------------
# Code Explanation Helpers
# ---------------------------------------------------------------------------

@dataclass
class CodeExplanation:
    """A structured explanation of a code symbol."""

    symbol_name: str
    symbol_kind: str
    file_path: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_name": self.symbol_name,
            "symbol_kind": self.symbol_kind,
            "file_path": self.file_path,
            "summary": self.summary,
            "details": self.details,
        }

    def render(self) -> str:
        lines = [
            f"# {self.symbol_kind.title()}: {self.symbol_name}",
            f"File: {self.file_path}",
            "",
            self.summary,
        ]
        if self.details:
            lines.append("")
            for key, value in self.details.items():
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)


def explain_symbol(symbol: Symbol, builder: ContextBuilder | None = None) -> CodeExplanation:
    """Generate a structural explanation of a code symbol.

    This creates a factual description based on the code structure,
    not AI-generated prose. It's useful as a prompt component for LLMs.

    Args:
        symbol: The symbol to explain.
        builder: Optional ContextBuilder for richer context.

    Returns:
        A CodeExplanation with structural information.
    """
    details: dict[str, Any] = {}

    # Basic info
    line_count = symbol.end_line - symbol.start_line + 1
    details["lines"] = f"{symbol.start_line}-{symbol.end_line} ({line_count} lines)"

    if symbol.parameters:
        details["parameters"] = ", ".join(symbol.parameters)

    if symbol.parent:
        details["parent_class"] = symbol.parent

    if symbol.decorators:
        details["decorators"] = ", ".join(symbol.decorators)

    # Build summary
    if symbol.kind == "function":
        param_str = f"({', '.join(symbol.parameters)})" if symbol.parameters else "()"
        summary = f"Function `{symbol.name}{param_str}` defined at line {symbol.start_line}."
    elif symbol.kind == "method":
        parent = f" of class `{symbol.parent}`" if symbol.parent else ""
        param_str = f"({', '.join(symbol.parameters)})" if symbol.parameters else "()"
        summary = f"Method `{symbol.name}{param_str}`{parent} defined at line {symbol.start_line}."
    elif symbol.kind == "class":
        summary = f"Class `{symbol.name}` defined at line {symbol.start_line}, spanning {line_count} lines."
    elif symbol.kind == "import":
        summary = f"Import statement at line {symbol.start_line}: `{symbol.body.strip()}`"
    else:
        summary = f"{symbol.kind.title()} `{symbol.name}` at line {symbol.start_line}."

    # Add call context if builder is available
    if builder is not None:
        ctx = builder.build_context(symbol)
        if ctx.related_symbols:
            related_names = [s.name for s in ctx.related_symbols[:5]]
            details["related_symbols"] = ", ".join(related_names)
        if ctx.imports:
            details["file_imports"] = len(ctx.imports)

    return CodeExplanation(
        symbol_name=symbol.name,
        symbol_kind=symbol.kind,
        file_path=symbol.file_path,
        summary=summary,
        details=details,
    )


def explain_file(file_path: str, content: str | None = None) -> list[CodeExplanation]:
    """Generate explanations for all symbols in a file.

    Args:
        file_path: Path to the source file.
        content: Optional file content.

    Returns:
        List of CodeExplanation objects, one per symbol.
    """
    builder = ContextBuilder()
    builder.index_file(file_path, content)
    symbols = builder.get_symbols(file_path)
    return [explain_symbol(s, builder) for s in symbols if s.kind != "import"]
