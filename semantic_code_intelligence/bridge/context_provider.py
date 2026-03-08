"""Context provider — structured context generation for external AI pipelines.

The ``ContextProvider`` is the heart of CodexA's cooperation model.  It
wraps the existing semantic search, symbol analysis, and dependency tools
into a single entry point that external AI assistants can call to enrich
their prompts with deep repository knowledge.

All public methods return plain ``dict`` objects ready for JSON
serialisation, so they can be consumed by any agent that speaks JSON —
no CodexA-specific types leak across the boundary.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from semantic_code_intelligence.analysis.ai_features import (
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
from semantic_code_intelligence.llm.safety import SafetyValidator
from semantic_code_intelligence.services.search_service import search_codebase
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("bridge.context")


class ContextProvider:
    """Generates structured context for consumption by external AI agents.

    Usage::

        provider = ContextProvider(Path("/my/project"))
        ctx = provider.context_for_symbol("authenticate")
        # ctx is a plain dict ready to be injected into an LLM prompt

    All expensive work (scanning, parsing) is done lazily on first access.
    """

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()
        self._builder: ContextBuilder | None = None
        self._indexed = False
        self._validator = SafetyValidator()

    # --- lazy indexing -------------------------------------------------

    def _ensure_indexed(self) -> ContextBuilder:
        if self._builder is not None and self._indexed:
            return self._builder

        from semantic_code_intelligence.config.settings import load_config
        from semantic_code_intelligence.indexing.scanner import scan_repository

        self._builder = ContextBuilder()
        config = load_config(self._root)
        scanned = scan_repository(self._root, config.index)
        for sf in scanned:
            full = str(self._root / sf.relative_path)
            try:
                self._builder.index_file(full)
            except Exception:
                logger.debug("Skip %s", full)
        self._indexed = True
        return self._builder

    # --- public context generators ----------------------------------

    def context_for_query(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.2,
        include_repo_summary: bool = False,
    ) -> dict[str, Any]:
        """Return semantic-search context for a natural-language query.

        Designed to be injected as additional context into an LLM prompt
        by an external AI assistant.
        """
        snippets: list[dict[str, Any]] = []
        try:
            results = search_codebase(query, self._root, top_k=top_k, threshold=threshold)
            snippets = [r.to_dict() for r in results]
        except Exception:
            logger.debug("Search unavailable — returning empty snippets.")

        resp: dict[str, Any] = {
            "query": query,
            "snippet_count": len(snippets),
            "snippets": snippets,
        }

        if include_repo_summary:
            builder = self._ensure_indexed()
            resp["repo_summary"] = summarize_repository(builder).to_dict()

        return resp

    def context_for_symbol(
        self,
        symbol_name: str,
        *,
        file_path: str | None = None,
        include_call_graph: bool = True,
        include_dependencies: bool = True,
    ) -> dict[str, Any]:
        """Return rich context around a symbol for external AI consumption.

        Includes the symbol's definition, related symbols, callers/callees,
        and dependency information.
        """
        builder = self._ensure_indexed()

        if file_path:
            builder.index_file(file_path)

        matches = builder.find_symbol(symbol_name)
        if not matches:
            return {"symbol_name": symbol_name, "found": False}

        explanations = [explain_symbol(s, builder).to_dict() for s in matches[:5]]
        context_windows = [
            builder.build_context(s).to_dict() for s in matches[:5]
        ]

        result: dict[str, Any] = {
            "symbol_name": symbol_name,
            "found": True,
            "match_count": len(matches),
            "explanations": explanations,
            "context_windows": context_windows,
        }

        if include_call_graph:
            all_syms = builder.get_all_symbols()
            graph = CallGraph()
            graph.build(all_syms)
            callers = [e.to_dict() for e in graph.callers_of(symbol_name)]
            callees: list[dict[str, Any]] = []
            for edge in graph.edges:
                if edge.caller.endswith(f":{symbol_name}"):
                    callees.append(edge.to_dict())
            result["call_graph"] = {"callers": callers, "callees": callees}

        if include_dependencies:
            for s in matches[:1]:
                dep_map = DependencyMap()
                if s.file_path in builder._file_contents:
                    dep_map.add_file(s.file_path, builder._file_contents[s.file_path])
                result["dependencies"] = dep_map.to_dict()

        return result

    def context_for_file(self, file_path: str) -> dict[str, Any]:
        """Return structured context for an entire file."""
        builder = self._ensure_indexed()
        builder.index_file(file_path)

        symbols = builder.get_symbols(file_path)
        explanations = explain_file(file_path)

        dep_map = DependencyMap()
        if file_path in builder._file_contents:
            dep_map.add_file(file_path, builder._file_contents[file_path])

        return {
            "file_path": file_path,
            "symbol_count": len(symbols),
            "symbols": [s.to_dict() for s in symbols],
            "explanations": [e.to_dict() for e in explanations],
            "dependencies": dep_map.to_dict(),
        }

    def context_for_repo(self) -> dict[str, Any]:
        """Return a repository-level summary."""
        builder = self._ensure_indexed()
        summary = summarize_repository(builder)
        return summary.to_dict()

    def validate_code(self, code: str) -> dict[str, Any]:
        """Validate code (e.g. AI-generated) for safety issues."""
        report = self._validator.validate(code)
        return report.to_dict()

    def get_dependencies(self, file_path: str) -> dict[str, Any]:
        """Return file-level dependency map."""
        builder = self._ensure_indexed()
        builder.index_file(file_path)
        dep_map = DependencyMap()
        if file_path in builder._file_contents:
            dep_map.add_file(file_path, builder._file_contents[file_path])
        return {"file_path": file_path, "dependencies": dep_map.to_dict()}

    def get_call_graph(self, symbol_name: str) -> dict[str, Any]:
        """Return callers and callees for a symbol."""
        builder = self._ensure_indexed()
        all_syms = builder.get_all_symbols()
        graph = CallGraph()
        graph.build(all_syms)
        callers = [e.to_dict() for e in graph.callers_of(symbol_name)]
        callees: list[dict[str, Any]] = []
        for edge in graph.edges:
            if edge.caller.endswith(f":{symbol_name}"):
                callees.append(edge.to_dict())
        return {"symbol_name": symbol_name, "callers": callers, "callees": callees}

    def find_references(self, symbol_name: str) -> dict[str, Any]:
        """Find all references to a symbol."""
        builder = self._ensure_indexed()
        all_syms = builder.get_all_symbols()
        refs: list[dict[str, Any]] = []
        for sym in all_syms:
            if sym.name == symbol_name:
                refs.append(sym.to_dict())
            elif symbol_name in sym.body:
                refs.append({
                    "referencing_symbol": sym.name,
                    "kind": sym.kind,
                    "file_path": sym.file_path,
                    "start_line": sym.start_line,
                    "end_line": sym.end_line,
                })
        return {"symbol_name": symbol_name, "reference_count": len(refs), "references": refs}
