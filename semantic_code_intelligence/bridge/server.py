"""Lightweight HTTP bridge server — exposes CodexA tools over JSON/HTTP.

Uses only the Python standard library (``http.server``) so there are zero
additional dependencies.  The server is designed to be started via
``codexa serve`` and consumed by IDE extensions, editor plugins, or any
HTTP client.

Endpoints
---------
GET  /                → capabilities manifest
POST /request         → handle an AgentRequest, return an AgentResponse
GET  /health          → simple health check (``{"status": "ok"}``)

All request/response bodies are JSON.
"""

from __future__ import annotations

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from semantic_code_intelligence.bridge.context_provider import ContextProvider
from semantic_code_intelligence.bridge.protocol import (
    AgentRequest,
    AgentResponse,
    BridgeCapabilities,
    RequestKind,
)
from semantic_code_intelligence.tools.executor import ToolExecutor
from semantic_code_intelligence.tools.protocol import ToolInvocation
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("bridge.server")


class _BridgeHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the bridge server."""

    # Assigned by BridgeServer before the HTTPServer starts.
    context_provider: ContextProvider
    capabilities: BridgeCapabilities
    tool_executor: ToolExecutor | None = None

    # Silence default stderr logging — we use our own logger.
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D102
        logger.debug(fmt, *args)

    # --- routing ---

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path == "/capabilities":
            self._json_response(200, self.capabilities.to_dict())
        elif self.path == "/health":
            self._json_response(200, {"status": "ok"})
        elif self.path == "/tools/list":
            self._handle_list_tools()
        elif self.path == "/tools/stream":
            self._handle_tool_stream()
        else:
            self._json_response(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/request":
            self._handle_request()
        elif self.path == "/tools/invoke":
            self._handle_tool_invoke()
        else:
            self._json_response(404, {"error": "Not found"})

    # --- core dispatch ---

    def _handle_request(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._json_response(400, {"error": "Empty body"})
            return

        raw = self.rfile.read(content_length)
        try:
            req = AgentRequest.from_json(raw.decode("utf-8"))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            self._json_response(400, {"error": f"Invalid JSON: {exc}"})
            return

        start = time.monotonic()
        resp = _dispatch(req, self.context_provider, self.capabilities, self.tool_executor)
        resp.elapsed_ms = (time.monotonic() - start) * 1000
        resp.request_id = req.request_id

        status = 200 if resp.success else 422
        self._json_response(status, resp.to_dict())

    # --- tool endpoints (Phase 19) ---

    def _handle_list_tools(self) -> None:
        """GET /tools/list — return schemas of all available tools."""
        if self.tool_executor is None:
            self._json_response(503, {"error": "Tool executor not initialized"})
            return
        tools = self.tool_executor.available_tools
        self._json_response(200, {"tools": tools, "count": len(tools)})

    def _handle_tool_invoke(self) -> None:
        """POST /tools/invoke — execute a ToolInvocation and return result."""
        if self.tool_executor is None:
            self._json_response(503, {"error": "Tool executor not initialized"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._json_response(400, {"error": "Empty body"})
            return

        raw = self.rfile.read(content_length)
        try:
            data = json.loads(raw.decode("utf-8"))
            invocation = ToolInvocation.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            self._json_response(400, {"error": f"Invalid JSON: {exc}"})
            return

        result = self.tool_executor.execute(invocation)
        status = 200 if result.success else 422
        self._json_response(status, result.to_dict())

    def _handle_tool_stream(self) -> None:
        """GET /tools/stream — SSE endpoint for tool execution events.

        Sends a heartbeat followed by tool list in SSE format.
        Agents can use this to discover tools via a streaming connection.
        """
        if self.tool_executor is None:
            self._json_response(503, {"error": "Tool executor not initialized"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        import time as _time

        # Send discovery event
        tools = self.tool_executor.available_tools
        discovery_event = {
            "kind": "tool_discovery",
            "content": "",
            "metadata": {"tools": [t["name"] for t in tools], "count": len(tools)},
        }
        self.wfile.write(f"data: {json.dumps(discovery_event)}\n\n".encode("utf-8"))
        self.wfile.flush()

        # Send heartbeat and close
        heartbeat = {"kind": "heartbeat", "content": "", "metadata": {"timestamp": _time.time()}}
        self.wfile.write(f"data: {json.dumps(heartbeat)}\n\n".encode("utf-8"))
        self.wfile.flush()

    # --- helpers ---

    def _json_response(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        # CORS headers — allow local IDE extensions to call the bridge.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def _dispatch(
    req: AgentRequest,
    provider: ContextProvider,
    capabilities: BridgeCapabilities,
    executor: ToolExecutor | None = None,
) -> AgentResponse:
    """Route an AgentRequest to the appropriate ContextProvider method."""
    kind = req.kind
    params = req.params

    try:
        if kind == RequestKind.SEMANTIC_SEARCH:
            data = provider.context_for_query(
                query=params.get("query", ""),
                top_k=params.get("top_k", 5),
                threshold=params.get("threshold", 0.2),
                include_repo_summary=params.get("include_repo_summary", False),
            )
        elif kind == RequestKind.EXPLAIN_SYMBOL:
            data = provider.context_for_symbol(
                symbol_name=params.get("symbol_name", ""),
                file_path=params.get("file_path"),
                include_call_graph=params.get("include_call_graph", True),
                include_dependencies=params.get("include_dependencies", True),
            )
        elif kind == RequestKind.EXPLAIN_FILE:
            data = provider.context_for_file(file_path=params.get("file_path", ""))
        elif kind == RequestKind.GET_CONTEXT:
            data = provider.context_for_symbol(
                symbol_name=params.get("symbol_name", ""),
            )
        elif kind == RequestKind.GET_DEPENDENCIES:
            data = provider.get_dependencies(file_path=params.get("file_path", ""))
        elif kind == RequestKind.GET_CALL_GRAPH:
            data = provider.get_call_graph(symbol_name=params.get("symbol_name", ""))
        elif kind == RequestKind.SUMMARIZE_REPO:
            data = provider.context_for_repo()
        elif kind == RequestKind.FIND_REFERENCES:
            data = provider.find_references(symbol_name=params.get("symbol_name", ""))
        elif kind == RequestKind.VALIDATE_CODE:
            data = provider.validate_code(code=params.get("code", ""))
        elif kind == RequestKind.LIST_CAPABILITIES:
            data = capabilities.to_dict()
        elif kind == RequestKind.INVOKE_TOOL:
            # Delegate to ToolExecutor if available
            tool_name = params.get("tool_name", "")
            arguments = params.get("arguments", {})
            invocation = ToolInvocation(tool_name=tool_name, arguments=arguments)
            _executor = executor or getattr(_BridgeHandler, "tool_executor", None)
            if _executor is None:
                return AgentResponse(success=False, error="Tool executor not initialized")
            result = _executor.execute(invocation)
            data = result.to_dict()
            if not result.success:
                return AgentResponse(success=False, error=data.get("error", {}).get("error_message", "Tool execution failed"))
        elif kind == RequestKind.LIST_TOOLS:
            _executor = executor or getattr(_BridgeHandler, "tool_executor", None)
            if _executor is None:
                return AgentResponse(success=False, error="Tool executor not initialized")
            data = {"tools": _executor.available_tools, "count": len(_executor.available_tools)}
        else:
            return AgentResponse(success=False, error=f"Unknown request kind: {kind}")

        return AgentResponse(success=True, data=data)

    except Exception as exc:
        logger.exception("Error handling request %s", kind)
        return AgentResponse(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Public server class
# ---------------------------------------------------------------------------

class BridgeServer:
    """Lightweight HTTP server that exposes CodexA tools for external agents.

    Usage::

        server = BridgeServer(Path("."), host="127.0.0.1", port=24842)
        server.start()        # blocks
        # or
        server.start_background()   # runs in a daemon thread
        server.stop()
    """

    DEFAULT_PORT = 24842

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
        self._capabilities = BridgeCapabilities()
        self._executor = ToolExecutor(self._root)

        # Populate capabilities with tool schemas
        self._capabilities.tools = self._executor.available_tools

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def _make_server(self) -> HTTPServer:
        # Inject dependencies into the handler class.
        _BridgeHandler.context_provider = self._provider
        _BridgeHandler.capabilities = self._capabilities
        _BridgeHandler.tool_executor = self._executor
        httpd = HTTPServer((self._host, self._port), _BridgeHandler)
        return httpd

    def start(self) -> None:
        """Start the server (blocking)."""
        self._httpd = self._make_server()
        logger.info("Bridge server listening on %s", self.url)
        try:
            self._httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self._httpd.server_close()

    def start_background(self) -> None:
        """Start the server in a background daemon thread."""
        self._httpd = self._make_server()
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        logger.info("Bridge server started in background on %s", self.url)

    def stop(self) -> None:
        """Shut down the background server."""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def dispatch(self, request: AgentRequest) -> AgentResponse:
        """Dispatch a request directly (no HTTP round-trip).

        Useful for in-process testing or when the server is embedded
        inside a larger application.
        """
        start = time.monotonic()
        resp = _dispatch(request, self._provider, self._capabilities, self._executor)
        resp.elapsed_ms = (time.monotonic() - start) * 1000
        resp.request_id = request.request_id
        return resp
