"""Combined web server — serves both the REST API and web UI.

Merges API and UI routing into a single HTTP handler so that
a single ``codex web`` command provides both the browser interface and the
developer API on the same port.

Uses only the Python standard library.
"""

from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from semantic_code_intelligence.bridge.context_provider import ContextProvider
from semantic_code_intelligence.utils.logging import get_logger
from semantic_code_intelligence.web.api import APIHandler, _qs_first
from semantic_code_intelligence.web.ui import (
    UIHandler,
    page_search,
    page_symbols,
    page_workspace,
    page_viz,
    _page,
)
from semantic_code_intelligence.web.visualize import (
    render_call_graph,
    render_dependency_graph,
)

logger = get_logger("web.server")


class _CombinedHandler(BaseHTTPRequestHandler):
    """Routes API requests to ``APIHandler`` logic and UI requests to page builders.

    Requests starting with ``/api/`` or ``/health`` are handled by API
    logic; everything else returns server-rendered HTML pages.
    """

    project_root: Path
    provider: ContextProvider

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug(fmt, *args)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)

        # API routes — delegate to APIHandler methods directly
        if path.startswith("/api/") or path == "/health":
            self._dispatch_api_get(path, qs)
        else:
            self._dispatch_ui(path, qs)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        self._dispatch_api_post(path)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # ------------------------------------------------------------------
    # API dispatch (inline — avoids creating new handler instances)
    # ------------------------------------------------------------------

    def _dispatch_api_get(self, path: str, qs: dict[str, list[str]]) -> None:
        import time

        if path == "/health":
            codex_dir = self.project_root / ".codex"
            self._json(200, {
                "status": "ok",
                "project_root": str(self.project_root),
                "indexed": (codex_dir / "index").exists() if codex_dir.exists() else False,
                "config_found": (codex_dir / "config.json").exists() if codex_dir.exists() else False,
            })
        elif path == "/api/search":
            query = _qs_first(qs, "q", "")
            if not query:
                self._json(400, {"error": "Missing required parameter: q"})
                return
            top_k = int(_qs_first(qs, "top_k", "5"))
            threshold = float(_qs_first(qs, "threshold", "0.2"))
            start = time.monotonic()
            data = self.provider.context_for_query(query, top_k=top_k, threshold=threshold)
            data["elapsed_ms"] = round((time.monotonic() - start) * 1000, 2)
            self._json(200, data)
        elif path == "/api/symbols":
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
                "symbols": [s.to_dict() for s in symbols[:200]],
            })
        elif path == "/api/deps":
            file_path = _qs_first(qs, "file", "")
            data = self.provider.get_dependencies(file_path=file_path)
            self._json(200, data)
        elif path == "/api/callgraph":
            symbol = _qs_first(qs, "symbol", "")
            data = self.provider.get_call_graph(symbol_name=symbol)
            self._json(200, data)
        elif path == "/api/summary":
            data = self.provider.context_for_repo()
            self._json(200, data)
        elif path.startswith("/api/viz/"):
            kind = path.replace("/api/viz/", "").strip("/")
            target = _qs_first(qs, "target", "")
            try:
                if kind == "callgraph":
                    data = self.provider.get_call_graph(symbol_name=target)
                    edges = data.get("edges", [])
                    mermaid = render_call_graph(edges)
                elif kind == "deps":
                    data = self.provider.get_dependencies(file_path=target)
                    mermaid = render_dependency_graph(data)
                else:
                    self._json(400, {"error": f"Unknown viz kind: {kind}"})
                    return
                self._json(200, {"kind": kind, "mermaid": mermaid})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
        else:
            self._json(404, {"error": "Not found", "path": self.path})

    def _dispatch_api_post(self, path: str) -> None:
        import time

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._json(400, {"error": "Empty request body"})
            return
        raw = self.rfile.read(content_length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"error": f"Invalid JSON: {exc}"})
            return

        if path == "/api/ask":
            question = body.get("question", "")
            if not question:
                self._json(400, {"error": "Missing required field: question"})
                return
            top_k = body.get("top_k", 5)
            start = time.monotonic()
            data = self.provider.context_for_query(question, top_k=top_k)
            data["elapsed_ms"] = round((time.monotonic() - start) * 1000, 2)
            self._json(200, data)
        elif path == "/api/analyze":
            code = body.get("code", "")
            mode = body.get("mode", "validate")
            if not code:
                self._json(400, {"error": "Missing required field: code"})
                return
            if mode == "validate":
                data = self.provider.validate_code(code=code)
            elif mode == "explain":
                file_path = body.get("file_path", "snippet.py")
                data = self.provider.context_for_file(file_path=file_path)
            else:
                self._json(400, {"error": f"Unknown mode: {mode}"})
                return
            self._json(200, data)
        else:
            self._json(404, {"error": "Not found"})

    # ------------------------------------------------------------------
    # UI dispatch
    # ------------------------------------------------------------------

    def _dispatch_ui(self, path: str, qs: dict[str, list[str]]) -> None:
        pages: dict[str, str] = {
            "/": page_search(),
            "/symbols": page_symbols(),
            "/workspace": page_workspace(),
            "/viz": page_viz(),
        }
        content = pages.get(path)
        if content:
            self._html(200, content)
        else:
            self._html(404, _page("Not Found", '<div class="empty">Page not found.</div>'))

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, status: int, content: str) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


class WebServer:
    """Combined web server serving API and UI on a single port.

    Usage::

        server = WebServer(Path("."), host="127.0.0.1", port=8080)
        server.start()        # blocks
        # or
        server.start_background()
        server.stop()
    """

    DEFAULT_PORT = 8080

    def __init__(
        self,
        project_root: Path,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
    ) -> None:
        self._root = project_root.resolve()
        self._host = host
        self._port = port
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._provider = ContextProvider(self._root)

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def _make_server(self) -> HTTPServer:
        _CombinedHandler.project_root = self._root
        _CombinedHandler.provider = self._provider
        return HTTPServer((self._host, self._port), _CombinedHandler)

    def start(self) -> None:
        """Start the server (blocking)."""
        self._httpd = self._make_server()
        logger.info("CodexA web server listening on %s", self.url)
        try:
            self._httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self._httpd.server_close()

    def start_background(self) -> None:
        """Start in a background daemon thread."""
        self._httpd = self._make_server()
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        logger.info("CodexA web server started in background on %s", self.url)

    def stop(self) -> None:
        """Shut down the server."""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
