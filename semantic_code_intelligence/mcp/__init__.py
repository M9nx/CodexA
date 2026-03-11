"""MCP server — Model Context Protocol server for AI agent integration.

Uses the official ``mcp`` SDK (https://pypi.org/project/mcp/) to expose
CodexA as a tool provider for Claude Desktop, Cursor, and other
MCP-compatible clients.

Exposes 13 tools: semantic_search, keyword_search, hybrid_search,
regex_search, explain_symbol, index_status, reindex, health_check,
get_quality_score, find_duplicates, grep_files, get_file_context,
list_languages.

Search tools support pagination via ``page_size`` and ``cursor`` parameters.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
    _HAS_MCP = True
except ImportError:  # mcp SDK not installed (e.g. Python 3.13)
    _HAS_MCP = False
    Server = None  # type: ignore[assignment,misc]
    TextContent = None  # type: ignore[assignment,misc]
    Tool = None  # type: ignore[assignment,misc]

from semantic_code_intelligence.config.settings import AppConfig
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("mcp")


# ---- Tool definitions ---------------------------------------------------

if _HAS_MCP:
    MCP_TOOLS = [
        Tool(
            name="semantic_search",
            description="Semantic vector similarity search over the indexed codebase.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query."},
                    "top_k": {"type": "integer", "description": "Number of results.", "default": 10},
                    "page_size": {"type": "integer", "description": "Results per page (pagination).", "default": 10},
                    "cursor": {"type": "string", "description": "Opaque cursor for next page."},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="keyword_search",
            description="BM25-ranked keyword search over indexed code chunks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword query."},
                    "top_k": {"type": "integer", "default": 10},
                    "page_size": {"type": "integer", "description": "Results per page.", "default": 10},
                    "cursor": {"type": "string", "description": "Opaque cursor for next page."},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="hybrid_search",
            description="Fused semantic + BM25 search via Reciprocal Rank Fusion.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "top_k": {"type": "integer", "default": 10},
                    "page_size": {"type": "integer", "description": "Results per page.", "default": 10},
                    "cursor": {"type": "string", "description": "Opaque cursor for next page."},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="regex_search",
            description="Grep-compatible regex search over indexed code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern."},
                    "top_k": {"type": "integer", "default": 10},
                    "case_insensitive": {"type": "boolean", "default": True},
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="explain_symbol",
            description="Get detailed info about a code symbol (function, class, method).",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol_name": {"type": "string", "description": "Name of the symbol."},
                },
                "required": ["symbol_name"],
            },
        ),
        Tool(
            name="index_status",
            description="Get the current index health and stats.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="reindex",
            description="Trigger a full or incremental re-index of the codebase.",
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="health_check",
            description="Check if the MCP server is running and responsive.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_quality_score",
            description="Run code quality analysis: complexity, dead code, duplicates, safety.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Specific file to analyze (omit for full project)."},
                },
            },
        ),
        Tool(
            name="find_duplicates",
            description="Detect duplicate or near-duplicate code blocks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold": {"type": "number", "default": 0.75, "description": "Similarity threshold (0-1)."},
                },
            },
        ),
        Tool(
            name="grep_files",
            description="Search raw files using regex — no index required. Uses ripgrep when available.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern."},
                    "file_glob": {"type": "string", "description": "Glob filter (e.g. '*.py')."},
                    "max_results": {"type": "integer", "default": 50},
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="get_file_context",
            description="Retrieve full surrounding function/class context for a symbol or line in a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative file path."},
                    "line": {"type": "integer", "description": "Line number to get context for."},
                    "symbol_name": {"type": "string", "description": "Symbol name to locate."},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="list_languages",
            description="List all programming languages supported by the tree-sitter parser.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]
else:
    MCP_TOOLS: list = []  # type: ignore[no-redef]


# ---- Tool dispatch -------------------------------------------------------

def _dispatch_tool(name: str, args: dict[str, Any], project_root: Path) -> Any:
    """Execute a tool and return its result."""
    from semantic_code_intelligence.services.search_service import search_codebase
    from semantic_code_intelligence.services.indexing_service import run_indexing
    from semantic_code_intelligence.storage.index_stats import IndexStats
    from semantic_code_intelligence.storage.symbol_registry import SymbolRegistry

    index_dir = AppConfig.index_dir(project_root)

    def _paginate(results: list[dict[str, Any]], args: dict[str, Any]) -> dict[str, Any]:
        """Apply cursor-based pagination to result list."""
        page_size = args.get("page_size", 10)
        cursor = args.get("cursor")
        start = 0
        if cursor:
            try:
                start = int(cursor)
            except (ValueError, TypeError):
                start = 0
        page = results[start : start + page_size]
        next_cursor = str(start + page_size) if start + page_size < len(results) else None
        return {
            "results": page,
            "total": len(results),
            "page_size": page_size,
            "next_cursor": next_cursor,
        }

    if name == "semantic_search":
        top_k = args.get("top_k", args.get("page_size", 10))
        results = search_codebase(
            query=args["query"], project_root=project_root,
            top_k=max(top_k, 50), mode="semantic",
        )
        return _paginate([r.to_dict() for r in results], args)

    if name == "keyword_search":
        top_k = args.get("top_k", args.get("page_size", 10))
        results = search_codebase(
            query=args["query"], project_root=project_root,
            top_k=max(top_k, 50), mode="keyword",
        )
        return _paginate([r.to_dict() for r in results], args)

    if name == "hybrid_search":
        top_k = args.get("top_k", args.get("page_size", 10))
        results = search_codebase(
            query=args["query"], project_root=project_root,
            top_k=max(top_k, 50), mode="hybrid",
        )
        return _paginate([r.to_dict() for r in results], args)

    if name == "regex_search":
        results = search_codebase(
            query=args["pattern"], project_root=project_root,
            top_k=args.get("top_k", 10), mode="regex",
            case_insensitive=args.get("case_insensitive", True),
        )
        return [r.to_dict() for r in results]

    if name == "explain_symbol":
        registry = SymbolRegistry.load(index_dir)
        entries = registry.find_by_name(args["symbol_name"])
        return [
            {
                "name": e.name, "kind": e.kind, "file_path": e.file_path,
                "start_line": e.start_line, "end_line": e.end_line,
                "parent": e.parent, "parameters": e.parameters,
                "language": e.language,
            }
            for e in entries
        ]

    if name == "index_status":
        try:
            stats = IndexStats.load(index_dir)
            return stats.to_dict() if stats else {"status": "no index"}
        except Exception:
            return {"status": "no index"}

    if name == "reindex":
        result = run_indexing(project_root, force=args.get("force", False))
        return {
            "files_indexed": result.files_indexed,
            "chunks_created": result.chunks_created,
            "chunks_reused": result.chunks_reused,
            "total_vectors": result.total_vectors,
        }

    if name == "health_check":
        return {"status": "ok", "project_root": str(project_root)}

    if name == "get_quality_score":
        from semantic_code_intelligence.ci.quality import analyze_project
        file_paths = [args["file_path"]] if args.get("file_path") else None
        report = analyze_project(project_root, file_paths=file_paths)
        return {
            "complexity_issues": len(report.complexity_issues),
            "dead_code": len(report.dead_code),
            "duplicates": len(report.duplicates),
            "safety_issues": len(report.bandit_issues),
            "maintainability_index": report.maintainability_index,
        }

    if name == "find_duplicates":
        from semantic_code_intelligence.ci.quality import detect_duplicates
        from semantic_code_intelligence.context.engine import ContextBuilder
        builder = ContextBuilder()
        from semantic_code_intelligence.indexing.scanner import scan_repository
        from semantic_code_intelligence.config.settings import load_config
        config = load_config(project_root)
        scanned = scan_repository(project_root, config.index)
        for sf in scanned:
            try:
                builder.index_file(str(project_root / sf.relative_path))
            except Exception:
                pass
        all_syms = builder.get_all_symbols()
        threshold = args.get("threshold", 0.75)
        dupes = detect_duplicates(all_syms, threshold=threshold)
        return [
            {"symbol_a": d.symbol_a, "symbol_b": d.symbol_b,
             "similarity": round(d.similarity, 3),
             "file_a": d.file_a, "file_b": d.file_b}
            for d in dupes[:20]
        ]

    if name == "grep_files":
        from semantic_code_intelligence.search.grep import grep_search
        result = grep_search(
            args["pattern"], project_root,
            max_results=args.get("max_results", 50),
            file_glob=args.get("file_glob"),
        )
        return result.to_dict()

    if name == "get_file_context":
        file_path = args.get("file_path", "")
        target_line = args.get("line")
        symbol_name = args.get("symbol_name")
        full_path = project_root / file_path
        if not full_path.is_file():
            return {"error": f"File not found: {file_path}"}
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"error": str(exc)}

        lines = content.splitlines()

        # If symbol_name given, find its line
        if symbol_name and not target_line:
            for i, ln in enumerate(lines, 1):
                if symbol_name in ln:
                    target_line = i
                    break
            if not target_line:
                return {"error": f"Symbol '{symbol_name}' not found in {file_path}"}

        if not target_line:
            return {"error": "Provide either 'line' or 'symbol_name'."}

        # Return a generous context window (±30 lines)
        start = max(0, target_line - 31)
        end = min(len(lines), target_line + 30)
        context_lines = lines[start:end]
        return {
            "file_path": file_path,
            "start_line": start + 1,
            "end_line": end,
            "content": "\n".join(context_lines),
        }

    if name == "list_languages":
        from semantic_code_intelligence.parsing.parser import (
            _LANGUAGE_MODULES,
            EXTENSION_TO_LANGUAGE,
        )
        ext_map: dict[str, list[str]] = {}
        for ext, lang in EXTENSION_TO_LANGUAGE.items():
            ext_map.setdefault(lang, []).append(ext)
        return [
            {"language": lang, "module": mod, "extensions": sorted(ext_map.get(lang, []))}
            for lang, mod in sorted(_LANGUAGE_MODULES.items())
        ]

    return {"error": f"Unknown tool: {name}"}


# ---- Server factory ------------------------------------------------------

def _create_server(project_root: Path) -> "Server":
    """Create and configure an MCP ``Server`` with all CodexA tools."""
    if not _HAS_MCP:
        raise RuntimeError("The 'mcp' package is required but not installed.")
    server = Server("codexa-mcp")

    @server.list_tools()
    async def handle_list_tools() -> list:
        return MCP_TOOLS

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list:
        args = arguments or {}
        try:
            result = _dispatch_tool(name, args, project_root)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    return server


# ---- Entry point ---------------------------------------------------------

def run_mcp_server(project_root: Path) -> None:
    """Run the MCP server in stdio mode.

    Uses the official MCP SDK to handle JSON-RPC over stdio.
    Compatible with Claude Desktop, Cursor, and other MCP clients.
    """
    if not _HAS_MCP:
        raise RuntimeError("The 'mcp' package is required but not installed.")
    project_root = project_root.resolve()
    logger.info("MCP server starting for %s", project_root)

    server = _create_server(project_root)

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_run())
    logger.info("MCP server stopped.")
