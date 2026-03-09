"""LSP server — Language Server Protocol implementation for CodexA.

Provides a JSON-RPC 2.0 LSP server over stdio so any LSP-compatible editor
(VS Code, Neovim, Sublime Text, JetBrains, Emacs) gets:

- **textDocument/hover** — explain symbol under cursor
- **textDocument/completion** — semantic search suggestions
- **textDocument/publishDiagnostics** — quality issues (complexity, dead code, security)
- **workspace/symbol** — global symbol search
- **textDocument/definition** — jump to symbol definition
- **textDocument/references** — find all references
- **codex/search** — custom semantic search request

The server reuses the same service layer (SearchService, IndexingService,
ContextProvider) as the MCP server, bridge, and CLI.
"""

from __future__ import annotations

import json
import re
import sys
import threading
from pathlib import Path
from typing import Any

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("lsp")

# ── LSP message framing (Content-Length headers) ──────────────────────

def _read_lsp_message() -> dict[str, Any] | None:
    """Read a single LSP message from stdin using Content-Length framing."""
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line_str = line.decode("utf-8").rstrip("\r\n")
        if line_str == "":
            break  # blank line separates headers from body
        if ":" in line_str:
            key, value = line_str.split(":", 1)
            headers[key.strip()] = value.strip()

    content_length = int(headers.get("Content-Length", "0"))
    if content_length == 0:
        return None

    body = sys.stdin.buffer.read(content_length)
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _write_lsp_message(msg: dict[str, Any]) -> None:
    """Write a single LSP message to stdout with Content-Length framing."""
    body = json.dumps(msg, ensure_ascii=False)
    encoded = body.encode("utf-8")
    header = f"Content-Length: {len(encoded)}\r\n\r\n"
    sys.stdout.buffer.write(header.encode("utf-8"))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


# ── LSP capabilities & constants ─────────────────────────────────────

_SERVER_INFO = {
    "name": "codex-lsp",
    "version": "0.28.0",
}

_SERVER_CAPABILITIES = {
    "textDocumentSync": {
        "openClose": True,
        "change": 1,  # Full document sync
        "save": {"includeText": True},
    },
    "hoverProvider": True,
    "completionProvider": {
        "triggerCharacters": [".", "(", ":", " "],
        "resolveProvider": False,
    },
    "definitionProvider": True,
    "referencesProvider": True,
    "workspaceSymbolProvider": True,
    "diagnosticProvider": {
        "interFileDependencies": False,
        "workspaceDiagnostics": False,
    },
}


# ── Document store (open documents in memory) ────────────────────────

class _DocumentStore:
    """Track open text documents for hover/completion context."""

    def __init__(self) -> None:
        self._docs: dict[str, str] = {}  # uri → content

    def open(self, uri: str, text: str) -> None:
        self._docs[uri] = text

    def update(self, uri: str, text: str) -> None:
        self._docs[uri] = text

    def close(self, uri: str) -> None:
        self._docs.pop(uri, None)

    def get(self, uri: str) -> str | None:
        return self._docs.get(uri)

    def get_word_at(self, uri: str, line: int, character: int) -> str:
        """Extract the word (symbol name) at a given position."""
        text = self._docs.get(uri)
        if not text:
            return ""
        lines = text.splitlines()
        if line >= len(lines):
            return ""
        row = lines[line]
        if character >= len(row):
            return ""
        # Walk left and right to find word boundaries
        start = character
        while start > 0 and (row[start - 1].isalnum() or row[start - 1] == "_"):
            start -= 1
        end = character
        while end < len(row) and (row[end].isalnum() or row[end] == "_"):
            end += 1
        return row[start:end]

    def uri_to_path(self, uri: str) -> str:
        """Convert a file:// URI to a filesystem path."""
        if uri.startswith("file:///"):
            # Windows: file:///C:/... → C:/...
            path = uri[8:] if len(uri) > 9 and uri[9] == ":" else uri[7:]
        elif uri.startswith("file://"):
            path = uri[7:]
        else:
            path = uri
        # Decode percent-encoding
        import urllib.parse
        return urllib.parse.unquote(path)


# ── LSP Server ───────────────────────────────────────────────────────

class LSPServer:
    """CodexA Language Server Protocol server.

    Reads JSON-RPC 2.0 messages from stdin and writes responses to stdout,
    using the standard LSP Content-Length framing.
    """

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()
        self._docs = _DocumentStore()
        self._initialized = False
        self._shutdown = False

    # ── main loop ─────────────────────────────────────────────────

    def run(self) -> None:
        """Run the LSP server — blocks until stdin closes or shutdown."""
        logger.info("LSP server starting for %s", self._root)

        while not self._shutdown:
            msg = _read_lsp_message()
            if msg is None:
                break
            response = self._handle(msg)
            if response:
                _write_lsp_message(response)

        logger.info("LSP server stopped.")

    # ── dispatch ──────────────────────────────────────────────────

    def _handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """Route a JSON-RPC message to the correct handler."""
        method = msg.get("method", "")
        req_id = msg.get("id")
        params = msg.get("params", {})

        # Lifecycle
        if method == "initialize":
            return self._on_initialize(req_id, params)
        if method == "initialized":
            self._initialized = True
            return None  # notification
        if method == "shutdown":
            self._shutdown = True
            return _ok(req_id, None)
        if method == "exit":
            return None

        # Document sync
        if method == "textDocument/didOpen":
            self._on_did_open(params)
            return None
        if method == "textDocument/didChange":
            self._on_did_change(params)
            return None
        if method == "textDocument/didClose":
            self._on_did_close(params)
            return None
        if method == "textDocument/didSave":
            self._on_did_save(params)
            return None

        # Language features
        if method == "textDocument/hover":
            return self._on_hover(req_id, params)
        if method == "textDocument/completion":
            return self._on_completion(req_id, params)
        if method == "textDocument/definition":
            return self._on_definition(req_id, params)
        if method == "textDocument/references":
            return self._on_references(req_id, params)
        if method == "workspace/symbol":
            return self._on_workspace_symbol(req_id, params)

        # Custom CodexA methods
        if method == "codex/search":
            return self._on_codex_search(req_id, params)
        if method == "codex/quality":
            return self._on_codex_quality(req_id, params)

        # Unknown method
        if req_id is not None:
            return _error(req_id, -32601, f"Method not found: {method}")
        return None  # unknown notification — ignore

    # ── lifecycle ─────────────────────────────────────────────────

    def _on_initialize(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        return _ok(req_id, {
            "capabilities": _SERVER_CAPABILITIES,
            "serverInfo": _SERVER_INFO,
        })

    # ── document sync ─────────────────────────────────────────────

    def _on_did_open(self, params: dict[str, Any]) -> None:
        td = params.get("textDocument", {})
        self._docs.open(td.get("uri", ""), td.get("text", ""))

    def _on_did_change(self, params: dict[str, Any]) -> None:
        td = params.get("textDocument", {})
        changes = params.get("contentChanges", [])
        if changes:
            self._docs.update(td.get("uri", ""), changes[-1].get("text", ""))

    def _on_did_close(self, params: dict[str, Any]) -> None:
        td = params.get("textDocument", {})
        self._docs.close(td.get("uri", ""))

    def _on_did_save(self, params: dict[str, Any]) -> None:
        # Trigger diagnostics on save
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        file_path = self._docs.uri_to_path(uri)
        self._publish_diagnostics(uri, file_path)

    # ── hover (explain symbol) ────────────────────────────────────

    def _on_hover(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        td = params.get("textDocument", {})
        pos = params.get("position", {})
        uri = td.get("uri", "")
        line = pos.get("line", 0)
        char = pos.get("character", 0)

        word = self._docs.get_word_at(uri, line, char)
        if not word:
            return _ok(req_id, None)

        try:
            from semantic_code_intelligence.storage.symbol_registry import SymbolRegistry

            index_dir = AppConfig.index_dir(self._root)
            registry = SymbolRegistry.load(index_dir)
            entries = registry.find_by_name(word)

            if not entries:
                return _ok(req_id, None)

            # Build hover markdown
            parts = [f"**{word}**\n"]
            for e in entries[:5]:
                parts.append(f"- `{e.kind}` in `{e.file_path}` "
                             f"(L{e.start_line}–{e.end_line})")
                if e.parameters:
                    parts.append(f"  Parameters: `{e.parameters}`")
            markdown = "\n".join(parts)

            return _ok(req_id, {
                "contents": {"kind": "markdown", "value": markdown},
            })
        except Exception as exc:
            logger.debug("Hover error: %s", exc)
            return _ok(req_id, None)

    # ── completion (semantic search) ──────────────────────────────

    def _on_completion(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        td = params.get("textDocument", {})
        pos = params.get("position", {})
        uri = td.get("uri", "")
        line = pos.get("line", 0)
        char = pos.get("character", 0)

        word = self._docs.get_word_at(uri, line, char)
        if not word or len(word) < 2:
            return _ok(req_id, {"isIncomplete": False, "items": []})

        try:
            from semantic_code_intelligence.storage.symbol_registry import SymbolRegistry

            index_dir = AppConfig.index_dir(self._root)
            registry = SymbolRegistry.load(index_dir)
            entries = registry.find_by_name(word)

            items = []
            for e in entries[:20]:
                kind = _symbol_kind_to_completion(e.kind)
                detail = f"{e.file_path}:{e.start_line}"
                items.append({
                    "label": e.name,
                    "kind": kind,
                    "detail": detail,
                    "documentation": {
                        "kind": "markdown",
                        "value": f"`{e.kind}` — {e.language}",
                    },
                })

            return _ok(req_id, {
                "isIncomplete": len(entries) > 20,
                "items": items,
            })
        except Exception as exc:
            logger.debug("Completion error: %s", exc)
            return _ok(req_id, {"isIncomplete": False, "items": []})

    # ── definition ────────────────────────────────────────────────

    def _on_definition(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        td = params.get("textDocument", {})
        pos = params.get("position", {})
        uri = td.get("uri", "")
        line = pos.get("line", 0)
        char = pos.get("character", 0)

        word = self._docs.get_word_at(uri, line, char)
        if not word:
            return _ok(req_id, [])

        try:
            from semantic_code_intelligence.storage.symbol_registry import SymbolRegistry

            index_dir = AppConfig.index_dir(self._root)
            registry = SymbolRegistry.load(index_dir)
            entries = registry.find_by_name(word)

            locations = []
            for e in entries[:10]:
                loc_uri = _path_to_uri(e.file_path, self._root)
                locations.append({
                    "uri": loc_uri,
                    "range": {
                        "start": {"line": max(0, e.start_line - 1), "character": 0},
                        "end": {"line": max(0, e.end_line - 1), "character": 0},
                    },
                })
            return _ok(req_id, locations)
        except Exception as exc:
            logger.debug("Definition error: %s", exc)
            return _ok(req_id, [])

    # ── references ────────────────────────────────────────────────

    def _on_references(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        td = params.get("textDocument", {})
        pos = params.get("position", {})
        uri = td.get("uri", "")
        line = pos.get("line", 0)
        char = pos.get("character", 0)

        word = self._docs.get_word_at(uri, line, char)
        if not word:
            return _ok(req_id, [])

        try:
            from semantic_code_intelligence.services.search_service import search_codebase

            results = search_codebase(
                query=word, project_root=self._root,
                top_k=20, mode="keyword",
            )
            locations = []
            for r in results:
                loc_uri = _path_to_uri(r.file_path, self._root)
                locations.append({
                    "uri": loc_uri,
                    "range": {
                        "start": {"line": max(0, r.start_line - 1), "character": 0},
                        "end": {"line": max(0, r.end_line - 1), "character": 0},
                    },
                })
            return _ok(req_id, locations)
        except Exception as exc:
            logger.debug("References error: %s", exc)
            return _ok(req_id, [])

    # ── workspace/symbol ──────────────────────────────────────────

    def _on_workspace_symbol(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        query = params.get("query", "")
        if not query or len(query) < 2:
            return _ok(req_id, [])

        try:
            from semantic_code_intelligence.storage.symbol_registry import SymbolRegistry

            index_dir = AppConfig.index_dir(self._root)
            registry = SymbolRegistry.load(index_dir)
            entries = registry.find_by_name(query)

            symbols = []
            for e in entries[:50]:
                loc_uri = _path_to_uri(e.file_path, self._root)
                symbols.append({
                    "name": e.name,
                    "kind": _symbol_kind_to_lsp(e.kind),
                    "location": {
                        "uri": loc_uri,
                        "range": {
                            "start": {"line": max(0, e.start_line - 1), "character": 0},
                            "end": {"line": max(0, e.end_line - 1), "character": 0},
                        },
                    },
                    "containerName": e.parent or "",
                })
            return _ok(req_id, symbols)
        except Exception as exc:
            logger.debug("Workspace symbol error: %s", exc)
            return _ok(req_id, [])

    # ── custom codex/search ───────────────────────────────────────

    def _on_codex_search(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        query = params.get("query", "")
        top_k = params.get("top_k", 10)
        mode = params.get("mode", "semantic")

        if not query:
            return _error(req_id, -32602, "Missing 'query' parameter")

        try:
            from semantic_code_intelligence.services.search_service import search_codebase

            results = search_codebase(
                query=query, project_root=self._root,
                top_k=top_k, mode=mode,
            )
            return _ok(req_id, [r.to_dict() for r in results])
        except Exception as exc:
            return _error(req_id, -32603, str(exc))

    # ── custom codex/quality ──────────────────────────────────────

    def _on_codex_quality(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        file_path = params.get("file_path", "")
        if not file_path:
            return _error(req_id, -32602, "Missing 'file_path' parameter")

        try:
            from semantic_code_intelligence.ci.quality import (
                analyze_complexity,
                detect_dead_code,
            )

            issues = analyze_complexity(file_path) + detect_dead_code(file_path)
            return _ok(req_id, [i.to_dict() for i in issues])
        except Exception as exc:
            return _error(req_id, -32603, str(exc))

    # ── diagnostics ───────────────────────────────────────────────

    def _publish_diagnostics(self, uri: str, file_path: str) -> None:
        """Compute and publish diagnostics for a file."""
        if not file_path or not Path(file_path).is_file():
            return

        diagnostics: list[dict[str, Any]] = []
        try:
            from semantic_code_intelligence.ci.quality import analyze_complexity

            results = analyze_complexity(file_path)
            for r in results:
                if r.rating in ("high", "very_high"):
                    diagnostics.append({
                        "range": {
                            "start": {"line": max(0, r.start_line - 1), "character": 0},
                            "end": {"line": max(0, r.end_line - 1), "character": 0},
                        },
                        "severity": 2 if r.rating == "high" else 1,  # Warning/Error
                        "source": "codex",
                        "message": f"High cyclomatic complexity ({r.complexity}) "
                                   f"in {r.symbol_name}",
                    })
        except Exception as exc:
            logger.debug("Diagnostics error: %s", exc)

        if diagnostics or True:  # always publish (clears old diagnostics)
            _write_lsp_message({
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": diagnostics},
            })


# ── JSON-RPC helpers ─────────────────────────────────────────────────

def _ok(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ── URI / kind helpers ───────────────────────────────────────────────

def _path_to_uri(file_path: str, project_root: Path) -> str:
    """Convert a file path to a file:// URI."""
    import urllib.parse
    p = Path(file_path)
    if not p.is_absolute():
        p = project_root / p
    return "file:///" + urllib.parse.quote(str(p).replace("\\", "/"), safe="/:")


def _symbol_kind_to_lsp(kind: str) -> int:
    """Map CodexA symbol kinds to LSP SymbolKind numbers."""
    mapping = {
        "function": 12,     # Function
        "method": 6,        # Method
        "class": 5,         # Class
        "module": 2,        # Module
        "variable": 13,     # Variable
        "constant": 14,     # Constant
        "interface": 11,    # Interface
        "enum": 10,         # Enum
        "property": 7,      # Property
        "constructor": 9,   # Constructor
    }
    return mapping.get(kind.lower(), 12)


def _symbol_kind_to_completion(kind: str) -> int:
    """Map CodexA symbol kinds to LSP CompletionItemKind numbers."""
    mapping = {
        "function": 3,      # Function
        "method": 2,        # Method
        "class": 7,         # Class
        "module": 9,        # Module
        "variable": 6,      # Variable
        "constant": 21,     # Constant
        "interface": 8,     # Interface
        "enum": 13,         # Enum
        "property": 10,     # Property
        "constructor": 4,   # Constructor
    }
    return mapping.get(kind.lower(), 3)


# ── Public entry point ───────────────────────────────────────────────

def run_lsp_server(project_root: Path) -> None:
    """Run the CodexA LSP server.

    Reads JSON-RPC requests from stdin and writes responses to stdout
    using standard LSP Content-Length framing.
    """
    server = LSPServer(project_root)
    server.run()
