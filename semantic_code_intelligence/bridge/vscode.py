"""VSCode extension bridge — helpers for integrating with VS Code.

This module provides:

* **VSCodeBridge** — high-level façade that packages CodexA results into
  shapes understood by VS Code extensions (completions, diagnostics, hovers,
  code-actions, etc.).
* **Manifest helpers** — generate ``package.json`` fragments for a companion
  VS Code extension that talks to the CodexA bridge server.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.bridge.context_provider import ContextProvider
from semantic_code_intelligence.bridge.protocol import (
    AgentRequest,
    AgentResponse,
    BridgeCapabilities,
    RequestKind,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("bridge.vscode")


# ---------------------------------------------------------------------------
# Format adapters — translate ContextProvider dicts into VSCode-friendly shapes
# ---------------------------------------------------------------------------

def _to_diagnostic(issue: dict[str, Any]) -> dict[str, Any]:
    """Convert a SafetyValidator issue dict into a VS Code Diagnostic shape."""
    severity_map = {"critical": 1, "high": 1, "medium": 2, "low": 3}
    return {
        "severity": severity_map.get(issue.get("severity", "medium"), 2),
        "message": issue.get("description", issue.get("pattern", "")),
        "source": "CodexA",
        "range": {
            "start": {"line": issue.get("line", 0), "character": 0},
            "end": {"line": issue.get("line", 0), "character": 999},
        },
    }


def _to_hover(context: dict[str, Any]) -> dict[str, Any]:
    """Package symbol context as a VS Code hover tooltip payload."""
    parts: list[str] = []
    if context.get("explanation"):
        parts.append(context["explanation"])
    if context.get("type"):
        parts.append(f"**Type:** `{context['type']}`")
    if context.get("file"):
        parts.append(f"Defined in `{context['file']}`")
    if context.get("callers"):
        callers = ", ".join(f"`{c}`" for c in context["callers"][:5])
        parts.append(f"**Callers:** {callers}")
    return {"contents": {"kind": "markdown", "value": "\n\n".join(parts)}}


def _to_completion_items(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate semantic search results into VS Code CompletionItem shapes."""
    items: list[dict[str, Any]] = []
    for idx, r in enumerate(results[:20]):
        items.append({
            "label": r.get("symbol", r.get("file", f"result_{idx}")),
            "kind": 1,  # Text
            "detail": r.get("explanation", ""),
            "documentation": {
                "kind": "markdown",
                "value": r.get("snippet", ""),
            },
            "sortText": f"{idx:04d}",
        })
    return items


# ---------------------------------------------------------------------------
# VSCodeBridge
# ---------------------------------------------------------------------------

@dataclass
class VSCodeBridge:
    """Façade that adapts ContextProvider output to VS Code extension shapes.

    This is *not* a running server — it's a formatting layer.  Pair it with
    ``BridgeServer`` for HTTP access, or call methods directly from a
    VS Code extension host written in Python.
    """

    provider: ContextProvider

    # --- public methods ---------------------------------------------------

    def hover(self, symbol_name: str, file_path: str | None = None) -> dict[str, Any]:
        """Return VS Code hover content for *symbol_name*."""
        ctx = self.provider.context_for_symbol(
            symbol_name=symbol_name, file_path=file_path,
        )
        return _to_hover(ctx)

    def diagnostics(self, code: str) -> list[dict[str, Any]]:
        """Run safety/validation and return VS Code diagnostics."""
        report = self.provider.validate_code(code)
        diagnostics: list[dict[str, Any]] = []
        for issue in report.get("issues", []):
            diagnostics.append(_to_diagnostic(issue))
        return diagnostics

    def completions(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Return completion items from semantic search results."""
        ctx = self.provider.context_for_query(query=query, top_k=top_k)
        return _to_completion_items(ctx.get("results", []))

    def code_actions(self, code: str) -> list[dict[str, Any]]:
        """Return VS Code code-actions derived from safety diagnostics."""
        report = self.provider.validate_code(code)
        actions: list[dict[str, Any]] = []
        for issue in report.get("issues", []):
            actions.append({
                "title": f"CodexA: {issue.get('description', 'Fix issue')}",
                "kind": "quickfix",
                "diagnostics": [_to_diagnostic(issue)],
            })
        return actions

    def file_summary(self, file_path: str) -> dict[str, Any]:
        """Return a summary of *file_path* suitable for an editor tooltip."""
        ctx = self.provider.context_for_file(file_path)
        return {
            "contents": {
                "kind": "markdown",
                "value": _format_file_summary(ctx),
            }
        }


def _format_file_summary(ctx: dict[str, Any]) -> str:
    lines: list[str] = []
    if ctx.get("explanation"):
        lines.append(ctx["explanation"])
    symbols = ctx.get("symbols", [])
    if symbols:
        sym_list = ", ".join(f"`{s}`" for s in symbols[:10])
        lines.append(f"**Symbols:** {sym_list}")
    deps = ctx.get("dependencies", [])
    if deps:
        dep_list = ", ".join(f"`{d}`" for d in deps[:10])
        lines.append(f"**Dependencies:** {dep_list}")
    return "\n\n".join(lines) if lines else "No information available."


# ---------------------------------------------------------------------------
# Extension manifest helpers
# ---------------------------------------------------------------------------

def generate_extension_manifest(
    server_port: int = 24842,
    extension_name: str = "codexa-bridge",
    display_name: str = "CodexA Bridge",
    version: str = "0.9.0",
) -> dict[str, Any]:
    """Generate a ``package.json`` fragment for a companion VS Code extension."""
    return {
        "name": extension_name,
        "displayName": display_name,
        "description": "Bridge to CodexA semantic code intelligence",
        "version": version,
        "publisher": "codexa",
        "engines": {"vscode": "^1.85.0"},
        "categories": ["Other"],
        "activationEvents": ["onStartupFinished"],
        "main": "./out/extension.js",
        "contributes": {
            "commands": [
                {
                    "command": "codexa.explainSymbol",
                    "title": "CodexA: Explain Symbol",
                },
                {
                    "command": "codexa.searchContext",
                    "title": "CodexA: Search Context",
                },
                {
                    "command": "codexa.validateCode",
                    "title": "CodexA: Validate Code",
                },
                {
                    "command": "codexa.fileSummary",
                    "title": "CodexA: File Summary",
                },
            ],
            "configuration": {
                "title": "CodexA Bridge",
                "properties": {
                    "codexa.bridge.port": {
                        "type": "number",
                        "default": server_port,
                        "description": "Port where the CodexA bridge server is running.",
                    },
                    "codexa.bridge.host": {
                        "type": "string",
                        "default": "127.0.0.1",
                        "description": "Host where the CodexA bridge server is running.",
                    },
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Streaming context (Phase 12)
# ---------------------------------------------------------------------------

@dataclass
class StreamChunk:
    """A single chunk in a streaming response from VSCode bridge."""

    kind: str  # "token", "context", "done", "error"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_sse(self) -> str:
        """Format as a Server-Sent Event line."""
        return f"data: {json.dumps(self.to_dict())}\n\n"


def build_streaming_context(
    query: str,
    provider: ContextProvider,
    *,
    top_k: int = 5,
) -> list[StreamChunk]:
    """Build a sequence of StreamChunks suitable for SSE delivery.

    Produces an initial context chunk (with search results) followed by a
    done chunk.  This can be extended to interleave LLM token chunks when
    streaming LLM responses are available.
    """
    chunks: list[StreamChunk] = []

    # 1. Emit context from semantic search
    ctx = provider.context_for_query(query=query, top_k=top_k)
    results = ctx.get("results", [])
    chunks.append(StreamChunk(
        kind="context",
        content=f"Found {len(results)} relevant snippets.",
        metadata={"result_count": len(results), "query": query},
    ))

    # 2. Emit each search result as a token-shaped chunk
    for r in results:
        chunks.append(StreamChunk(
            kind="token",
            content=r.get("content", r.get("snippet", "")),
            metadata={
                "file_path": r.get("file_path", ""),
                "score": r.get("score", 0),
            },
        ))

    # 3. Done sentinel
    chunks.append(StreamChunk(kind="done", content="", metadata={}))
    return chunks
