"""Agent cooperation protocol — request/response types for external AI systems.

Defines a model-neutral JSON protocol that any IDE AI assistant (Copilot,
Cursor, Continue, etc.) can use to request context from CodexA and receive
structured responses.

The protocol is intentionally simple and stateless — every request carries
the information needed to produce a response.  This keeps the bridge
lightweight and easy to integrate with any tool that speaks JSON.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RequestKind(str, Enum):
    """Types of requests the bridge can handle."""

    SEMANTIC_SEARCH = "semantic_search"
    EXPLAIN_SYMBOL = "explain_symbol"
    EXPLAIN_FILE = "explain_file"
    GET_CONTEXT = "get_context"
    GET_DEPENDENCIES = "get_dependencies"
    GET_CALL_GRAPH = "get_call_graph"
    SUMMARIZE_REPO = "summarize_repo"
    FIND_REFERENCES = "find_references"
    VALIDATE_CODE = "validate_code"
    LIST_CAPABILITIES = "list_capabilities"

    # Phase 19 — AI Agent Tooling Protocol
    INVOKE_TOOL = "invoke_tool"
    LIST_TOOLS = "list_tools"


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------

@dataclass
class AgentRequest:
    """Incoming request from an external AI agent or IDE extension.

    Attributes:
        kind: The type of operation requested.
        params: Operation-specific parameters (key-value).
        request_id: Optional caller-assigned ID for correlation.
        source: Optional identifier for the calling agent (e.g. "copilot").
    """

    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "params": self.params,
            "request_id": self.request_id,
            "source": self.source,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRequest":
        return cls(
            kind=data.get("kind", ""),
            params=data.get("params", {}),
            request_id=data.get("request_id", ""),
            source=data.get("source", ""),
        )

    @classmethod
    def from_json(cls, text: str) -> "AgentRequest":
        return cls.from_dict(json.loads(text))


@dataclass
class AgentResponse:
    """Outgoing response to an external AI agent or IDE extension.

    Attributes:
        success: Whether the request was handled without error.
        data: The structured response payload.
        error: Human-readable error message if success is False.
        request_id: Echoes the caller's request_id for correlation.
        elapsed_ms: Time taken to process the request.
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    request_id: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "success": self.success,
            "request_id": self.request_id,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error
        return result

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ---------------------------------------------------------------------------
# Capabilities manifest
# ---------------------------------------------------------------------------

@dataclass
class BridgeCapabilities:
    """Advertises what CodexA can do to external consumers.

    Returned in response to ``list_capabilities`` requests and also
    served at ``GET /`` by the bridge server.
    """

    version: str = "0.9.0"
    name: str = "CodexA Bridge"
    description: str = (
        "Semantic code intelligence provider — context, search, "
        "explanation, dependency analysis, and safety validation "
        "for external AI coding assistants."
    )
    supported_requests: list[str] = field(
        default_factory=lambda: [k.value for k in RequestKind]
    )
    tools: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "supported_requests": self.supported_requests,
        }
        if self.tools:
            result["tools"] = self.tools
        return result

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
