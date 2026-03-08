"""MCP server — Model Context Protocol server for AI agent integration.

Implements the MCP (Model Context Protocol) JSON-RPC interface so that
Claude Desktop, Cursor, and other MCP-compatible clients can use CodexA
as a tool provider.

Exposes 8 tools: semantic_search, keyword_search, hybrid_search,
regex_search, explain_symbol, get_call_graph, index_status, reindex.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("mcp")


# ---- Tool definitions ---------------------------------------------------

MCP_TOOLS = [
    {
        "name": "semantic_search",
        "description": "Semantic vector similarity search over the indexed codebase.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query."},
                "top_k": {"type": "integer", "description": "Number of results.", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "keyword_search",
        "description": "BM25-ranked keyword search over indexed code chunks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query."},
                "top_k": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "hybrid_search",
        "description": "Fused semantic + BM25 search via Reciprocal Rank Fusion.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "top_k": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "regex_search",
        "description": "Grep-compatible regex search over indexed code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern."},
                "top_k": {"type": "integer", "default": 10},
                "case_insensitive": {"type": "boolean", "default": True},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "explain_symbol",
        "description": "Get detailed info about a code symbol (function, class, method).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {"type": "string", "description": "Name of the symbol."},
            },
            "required": ["symbol_name"],
        },
    },
    {
        "name": "index_status",
        "description": "Get the current index health and stats.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "reindex",
        "description": "Trigger a full or incremental re-index of the codebase.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "health_check",
        "description": "Check if the MCP server is running and responsive.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ---- Tool dispatch -------------------------------------------------------

def _dispatch_tool(name: str, args: dict[str, Any], project_root: Path) -> Any:
    """Execute a tool and return its result."""
    from semantic_code_intelligence.services.search_service import search_codebase
    from semantic_code_intelligence.services.indexing_service import run_indexing
    from semantic_code_intelligence.storage.index_stats import IndexStats
    from semantic_code_intelligence.storage.symbol_registry import SymbolRegistry

    index_dir = AppConfig.index_dir(project_root)

    if name == "semantic_search":
        results = search_codebase(
            query=args["query"], project_root=project_root,
            top_k=args.get("top_k", 10), mode="semantic",
        )
        return [r.to_dict() for r in results]

    if name == "keyword_search":
        results = search_codebase(
            query=args["query"], project_root=project_root,
            top_k=args.get("top_k", 10), mode="keyword",
        )
        return [r.to_dict() for r in results]

    if name == "hybrid_search":
        results = search_codebase(
            query=args["query"], project_root=project_root,
            top_k=args.get("top_k", 10), mode="hybrid",
        )
        return [r.to_dict() for r in results]

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

    return {"error": f"Unknown tool: {name}"}


# ---- JSON-RPC over stdio ------------------------------------------------

def _read_message() -> dict[str, Any] | None:
    """Read a JSON-RPC message from stdin."""
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _write_message(msg: dict[str, Any]) -> None:
    """Write a JSON-RPC response to stdout."""
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle_request(request: dict[str, Any], project_root: Path) -> dict[str, Any]:
    """Handle a single JSON-RPC request."""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "codex-mcp", "version": "0.26.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            result = _dispatch_tool(tool_name, tool_args, project_root)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                },
            }

    # notifications (no id) — acknowledge silently
    if req_id is None:
        return {}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def run_mcp_server(project_root: Path) -> None:
    """Run the MCP server in stdio mode.

    Reads JSON-RPC messages from stdin and writes responses to stdout.
    Terminates on EOF.
    """
    project_root = project_root.resolve()
    logger.info("MCP server starting for %s", project_root)

    while True:
        msg = _read_message()
        if msg is None:
            break
        response = _handle_request(msg, project_root)
        if response:
            _write_message(response)

    logger.info("MCP server stopped.")
