"""AI tool interaction layer — structured protocol for LLM agents.

Provides a tool-calling interface that LLMs can use to interact with
the CodexA intelligence engine: search, explain, summarize, navigate.
Each tool returns structured JSON suitable for LLM consumption.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.analysis.ai_features import (
    CodeExplanation,
    explain_file,
    explain_symbol,
    generate_ai_context,
    summarize_repository,
)
from semantic_code_intelligence.context.engine import (
    CallGraph,
    ContextBuilder,
    DependencyMap,
)
from semantic_code_intelligence.services.search_service import SearchResult, search_codebase
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("tools")


# ---------------------------------------------------------------------------
# Tool Result Protocol
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Structured result from a tool invocation."""

    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tool": self.tool_name,
            "success": self.success,
        }
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error or "Unknown error"
        return result

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ---------------------------------------------------------------------------
# Tool Definitions (for schema / manifest)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "semantic_search",
        "description": "Search the codebase using natural language. Returns relevant code snippets ranked by similarity.",
        "parameters": {
            "query": {"type": "string", "required": True, "description": "Natural language search query"},
            "top_k": {"type": "integer", "required": False, "default": 10, "description": "Max results"},
            "threshold": {"type": "float", "required": False, "default": 0.3, "description": "Min similarity"},
        },
    },
    {
        "name": "explain_symbol",
        "description": "Get a structural explanation of a code symbol (function, class, method).",
        "parameters": {
            "symbol_name": {"type": "string", "required": True, "description": "Name of the symbol"},
            "file_path": {"type": "string", "required": False, "description": "File containing the symbol"},
        },
    },
    {
        "name": "explain_file",
        "description": "Get explanations of all symbols in a source file.",
        "parameters": {
            "file_path": {"type": "string", "required": True, "description": "Path to the source file"},
        },
    },
    {
        "name": "summarize_repo",
        "description": "Get a structured summary of the entire repository.",
        "parameters": {},
    },
    {
        "name": "find_references",
        "description": "Find all references to a symbol across the codebase.",
        "parameters": {
            "symbol_name": {"type": "string", "required": True, "description": "Name to search for"},
        },
    },
    {
        "name": "get_dependencies",
        "description": "Get the dependency map (imports) for a specific file.",
        "parameters": {
            "file_path": {"type": "string", "required": True, "description": "Source file path"},
        },
    },
    {
        "name": "get_call_graph",
        "description": "Get the call graph for a symbol, showing callers and callees.",
        "parameters": {
            "symbol_name": {"type": "string", "required": True, "description": "Symbol to analyze"},
        },
    },
    {
        "name": "get_context",
        "description": "Build a rich context window around a symbol for AI-assisted tasks.",
        "parameters": {
            "symbol_name": {"type": "string", "required": True, "description": "Focal symbol name"},
        },
    },
    {
        "name": "get_quality_score",
        "description": "Run code quality analysis: complexity, dead code, duplicates, and safety issues.",
        "parameters": {
            "file_path": {"type": "string", "required": False, "description": "Specific file to analyze (omit for full project)"},
        },
    },
    {
        "name": "find_duplicates",
        "description": "Detect duplicate or near-duplicate code blocks across the codebase.",
        "parameters": {
            "threshold": {"type": "float", "required": False, "default": 0.75, "description": "Similarity threshold (0-1)"},
        },
    },
    {
        "name": "grep_files",
        "description": "Search raw files using regex — no index required. Uses ripgrep when available.",
        "parameters": {
            "pattern": {"type": "string", "required": True, "description": "Regex pattern to search for"},
            "file_glob": {"type": "string", "required": False, "description": "Glob to filter files (e.g. '*.py')"},
            "max_results": {"type": "integer", "required": False, "default": 50, "description": "Max matches"},
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Registry & Executor
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Central registry that maps tool names to their implementations.

    Provides a unified interface for LLM agents to discover and invoke tools.
    """

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()
        self._builder: ContextBuilder | None = None
        self._indexed_files: set[str] = set()

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        """Return schema of all available tools."""
        return TOOL_DEFINITIONS

    def _ensure_builder(self) -> ContextBuilder:
        """Lazily initialize ContextBuilder with repo files."""
        if self._builder is None:
            self._builder = ContextBuilder()
        return self._builder

    def index_file(self, file_path: str, content: str | None = None) -> None:
        """Index a file for tools that need parsed symbol data."""
        builder = self._ensure_builder()
        if file_path not in self._indexed_files:
            builder.index_file(file_path, content)
            self._indexed_files.add(file_path)

    def index_directory(self, directory: Path | None = None) -> int:
        """Index all supported files in a directory."""
        from semantic_code_intelligence.config.settings import load_config
        from semantic_code_intelligence.indexing.scanner import scan_repository

        target = directory or self._root
        config = load_config(self._root)
        scanned = scan_repository(target, config.index)

        builder = self._ensure_builder()
        count = 0
        for sf in scanned:
            full_path = str(target / sf.relative_path)
            if full_path not in self._indexed_files:
                try:
                    builder.index_file(full_path)
                    self._indexed_files.add(full_path)
                    count += 1
                except Exception:
                    logger.debug("Failed to index %s", full_path)
        return count

    def invoke(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Invoke a tool by name with keyword arguments."""
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
            )
        try:
            result: ToolResult = handler(**kwargs)
            return result
        except Exception as e:
            logger.exception("Tool %s failed", tool_name)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    # --- Tool implementations ---

    def _tool_semantic_search(
        self, query: str, top_k: int = 10, threshold: float = 0.3
    ) -> ToolResult:
        results = search_codebase(
            query, self._root, top_k=top_k, threshold=threshold
        )
        return ToolResult(
            tool_name="semantic_search",
            success=True,
            data={
                "query": query,
                "result_count": len(results),
                "results": [r.to_dict() for r in results],
            },
        )

    def _tool_explain_symbol(
        self, symbol_name: str, file_path: str | None = None
    ) -> ToolResult:
        builder = self._ensure_builder()

        if file_path:
            self.index_file(file_path)
            symbols = builder.get_symbols(file_path)
            match = [s for s in symbols if s.name == symbol_name]
        else:
            match = builder.find_symbol(symbol_name)

        if not match:
            return ToolResult(
                tool_name="explain_symbol",
                success=False,
                error=f"Symbol '{symbol_name}' not found.",
            )

        explanations = [explain_symbol(s, builder) for s in match]
        return ToolResult(
            tool_name="explain_symbol",
            success=True,
            data={
                "symbol_name": symbol_name,
                "explanations": [e.to_dict() for e in explanations],
            },
        )

    def _tool_explain_file(self, file_path: str) -> ToolResult:
        self.index_file(file_path)
        explanations = explain_file(file_path)
        return ToolResult(
            tool_name="explain_file",
            success=True,
            data={
                "file_path": file_path,
                "symbols": [e.to_dict() for e in explanations],
            },
        )

    def _tool_summarize_repo(self) -> ToolResult:
        builder = self._ensure_builder()
        summary = summarize_repository(builder)
        return ToolResult(
            tool_name="summarize_repo",
            success=True,
            data=summary.to_dict(),
        )

    def _tool_find_references(self, symbol_name: str) -> ToolResult:
        builder = self._ensure_builder()
        all_syms = builder.get_all_symbols()

        references: list[dict[str, Any]] = []
        for sym in all_syms:
            if sym.name == symbol_name:
                references.append(sym.to_dict())
            elif symbol_name in sym.body:
                references.append({
                    "referencing_symbol": sym.name,
                    "kind": sym.kind,
                    "file_path": sym.file_path,
                    "start_line": sym.start_line,
                    "end_line": sym.end_line,
                })

        return ToolResult(
            tool_name="find_references",
            success=True,
            data={
                "symbol_name": symbol_name,
                "reference_count": len(references),
                "references": references,
            },
        )

    def _tool_get_dependencies(self, file_path: str) -> ToolResult:
        self.index_file(file_path)
        builder = self._ensure_builder()
        dep_map = DependencyMap()

        if file_path in builder._file_contents:
            dep_map.add_file(file_path, builder._file_contents[file_path])

        return ToolResult(
            tool_name="get_dependencies",
            success=True,
            data={
                "file_path": file_path,
                "dependencies": dep_map.to_dict(),
            },
        )

    def _tool_get_call_graph(self, symbol_name: str) -> ToolResult:
        builder = self._ensure_builder()
        all_syms = builder.get_all_symbols()
        graph = CallGraph()
        graph.build(all_syms)

        callers = [e.to_dict() for e in graph.callers_of(symbol_name)]

        # callees_of needs "file:name" key; collect from all matching
        all_callees: list[dict[str, Any]] = []
        for edge in graph.edges:
            if edge.caller.endswith(f":{symbol_name}"):
                all_callees.append(edge.to_dict())

        return ToolResult(
            tool_name="get_call_graph",
            success=True,
            data={
                "symbol_name": symbol_name,
                "callers": callers,
                "callees": all_callees,
            },
        )

    def _tool_get_context(self, symbol_name: str) -> ToolResult:
        builder = self._ensure_builder()
        contexts = builder.build_context_for_name(symbol_name)

        if not contexts:
            return ToolResult(
                tool_name="get_context",
                success=False,
                error=f"Symbol '{symbol_name}' not found.",
            )

        return ToolResult(
            tool_name="get_context",
            success=True,
            data={
                "symbol_name": symbol_name,
                "contexts": [c.to_dict() for c in contexts],
            },
        )

    def _tool_get_quality_score(self, file_path: str | None = None) -> ToolResult:
        from semantic_code_intelligence.ci.quality import analyze_project

        file_paths = [file_path] if file_path else None
        report = analyze_project(self._root, file_paths=file_paths)

        return ToolResult(
            tool_name="get_quality_score",
            success=True,
            data={
                "complexity_issues": len(report.complexity_issues),
                "dead_code": len(report.dead_code),
                "duplicates": len(report.duplicates),
                "safety_issues": len(report.bandit_issues),
                "maintainability_index": report.maintainability_index,
                "high_complexity": [
                    {"symbol": c.symbol_name, "file": c.file_path,
                     "complexity": c.complexity}
                    for c in report.complexity_issues[:10]
                ],
            },
        )

    def _tool_find_duplicates(self, threshold: float = 0.75) -> ToolResult:
        from semantic_code_intelligence.ci.quality import detect_duplicates

        builder = self._ensure_builder()
        all_syms = builder.get_all_symbols()
        duplicates = detect_duplicates(all_syms, threshold=threshold)

        return ToolResult(
            tool_name="find_duplicates",
            success=True,
            data={
                "duplicate_count": len(duplicates),
                "duplicates": [
                    {
                        "symbol_a": d.symbol_a,
                        "symbol_b": d.symbol_b,
                        "similarity": round(d.similarity, 3),
                        "file_a": d.file_a,
                        "file_b": d.file_b,
                    }
                    for d in duplicates[:20]
                ],
            },
        )

    def _tool_grep_files(
        self, pattern: str, file_glob: str | None = None, max_results: int = 50
    ) -> ToolResult:
        from semantic_code_intelligence.search.grep import grep_search

        result = grep_search(
            pattern, self._root,
            max_results=max_results, file_glob=file_glob,
        )

        return ToolResult(
            tool_name="grep_files",
            success=True,
            data=result.to_dict(),
        )
