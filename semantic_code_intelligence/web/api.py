"""REST API server — developer-friendly HTTP endpoints wrapping CodexA services.

Uses only the Python standard library (``http.server``).  All endpoints
return JSON and can be selectively enabled/disabled.

Endpoints
---------
GET  /health           → system & index status
GET  /api/search       → semantic search (``?q=...&top_k=5``)
POST /api/ask          → natural-language code Q\u0026A
POST /api/analyze      → code explanation / validation
GET  /api/symbols      → list indexed symbols (``?file=...&kind=...``)
GET  /api/deps         → dependency map (``?file=...``)
GET  /api/callgraph    → call graph (``?symbol=...``)
GET  /api/summary      → repository summary
"""

from __future__ import annotations

import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from semantic_code_intelligence.bridge.context_provider import ContextProvider
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("web.api")


class APIHandler(BaseHTTPRequestHandler):
    """JSON REST API handler for CodexA developer endpoints.

    Class-level attributes are injected before the server starts:
        project_root  — the root path of the project being served
        provider      — a ``ContextProvider`` instance
    """

    project_root: Path
    provider: ContextProvider

    # Use our own logger instead of stderr.
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D102
        logger.debug(fmt, *args)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = urllib.parse.parse_qs(parsed.query)

        routes: dict[str, Any] = {
            "/health": self._handle_health,
            "/api/search": self._handle_search,
            "/api/symbols": self._handle_symbols,
            "/api/deps": self._handle_deps,
            "/api/callgraph": self._handle_callgraph,
            "/api/summary": self._handle_summary,
        }

        handler = routes.get(path)
        if handler:
            handler(qs)
        else:
            self._json(404, {"error": "Not found", "path": self.path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        body = self._read_body()
        if body is None:
            return  # error already sent

        routes: dict[str, Any] = {
            "/api/ask": self._handle_ask,
            "/api/analyze": self._handle_analyze,
        }

        handler = routes.get(path)
        if handler:
            handler(body)
        else:
            self._json(404, {"error": "Not found", "path": self.path})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # ------------------------------------------------------------------
    # GET handlers
    # ------------------------------------------------------------------

    def _handle_health(self, qs: dict[str, list[str]]) -> None:
        """GET /health — project status and basic info."""
        codex_dir = self.project_root / ".codex"
        self._json(200, {
            "status": "ok",
            "project_root": str(self.project_root),
            "indexed": (codex_dir / "index").exists() if codex_dir.exists() else False,
            "config_found": (codex_dir / "config.json").exists() if codex_dir.exists() else False,
        })

    def _handle_search(self, qs: dict[str, list[str]]) -> None:
        """GET /api/search?q=...&top_k=5&threshold=0.2"""
        query = _qs_first(qs, "q", "")
        if not query:
            self._json(400, {"error": "Missing required parameter: q"})
            return

        top_k = int(_qs_first(qs, "top_k", "5"))
        threshold = float(_qs_first(qs, "threshold", "0.2"))

        start = time.monotonic()
        data = self.provider.context_for_query(
            query, top_k=top_k, threshold=threshold,
        )
        elapsed = (time.monotonic() - start) * 1000
        data["elapsed_ms"] = round(elapsed, 2)
        self._json(200, data)

    def _handle_symbols(self, qs: dict[str, list[str]]) -> None:
        """GET /api/symbols?file=...&kind=..."""
        builder = self.provider._ensure_indexed()
        file_filter = _qs_first(qs, "file", "")
        kind_filter = _qs_first(qs, "kind", "")

        symbols = builder.get_all_symbols()
        if file_filter:
            symbols = [s for s in symbols if file_filter in s.file_path]
        if kind_filter:
            symbols = [s for s in symbols if s.kind == kind_filter]

        self._json(200, {
            "count": len(symbols),
            "symbols": [s.to_dict() for s in symbols[:200]],  # cap at 200
        })

    def _handle_deps(self, qs: dict[str, list[str]]) -> None:
        """GET /api/deps?file=..."""
        file_path = _qs_first(qs, "file", "")
        data = self.provider.get_dependencies(file_path=file_path)
        self._json(200, data)

    def _handle_callgraph(self, qs: dict[str, list[str]]) -> None:
        """GET /api/callgraph?symbol=..."""
        symbol = _qs_first(qs, "symbol", "")
        data = self.provider.get_call_graph(symbol_name=symbol)
        self._json(200, data)

    def _handle_summary(self, qs: dict[str, list[str]]) -> None:
        """GET /api/summary"""
        data = self.provider.context_for_repo()
        self._json(200, data)

    # ------------------------------------------------------------------
    # POST handlers
    # ------------------------------------------------------------------

    def _handle_ask(self, body: dict[str, Any]) -> None:
        """POST /api/ask — natural-language question about the codebase.

        Request body: ``{"question": "...", "top_k": 5}``
        """
        question = body.get("question", "")
        if not question:
            self._json(400, {"error": "Missing required field: question"})
            return

        top_k = body.get("top_k", 5)
        start = time.monotonic()
        data = self.provider.context_for_query(question, top_k=top_k)
        elapsed = (time.monotonic() - start) * 1000
        data["elapsed_ms"] = round(elapsed, 2)
        self._json(200, data)

    def _handle_analyze(self, body: dict[str, Any]) -> None:
        """POST /api/analyze — code validation / explanation.

        Request body: ``{"code": "...", "mode": "validate|explain"}``
        """
        code = body.get("code", "")
        mode = body.get("mode", "validate")

        if not code:
            self._json(400, {"error": "Missing required field: code"})
            return

        if mode == "validate":
            data = self.provider.validate_code(code=code)
        elif mode == "explain":
            # File-level explanation for the provided code snippet
            file_path = body.get("file_path", "snippet.py")
            data = self.provider.context_for_file(file_path=file_path)
        else:
            self._json(400, {"error": f"Unknown mode: {mode}. Use 'validate' or 'explain'."})
            return

        self._json(200, data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_body(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._json(400, {"error": "Empty request body"})
            return None
        raw = self.rfile.read(content_length)
        try:
            parsed: dict[str, Any] | None = json.loads(raw.decode("utf-8"))
            return parsed
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"error": f"Invalid JSON: {exc}"})
            return None

    def _json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def _qs_first(qs: dict[str, list[str]], key: str, default: str = "") -> str:
    """Return the first value for a query-string key, or *default*."""
    vals = qs.get(key, [])
    return vals[0] if vals else default
