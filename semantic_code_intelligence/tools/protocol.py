"""Tool invocation protocol — structured request/response types for AI agent tool use.

Defines the data structures that AI coding agents use to invoke CodexA
tools in a deterministic, type-safe manner:

- ``ToolInvocation``: a request to execute a specific tool with arguments
- ``ToolExecutionResult``: the structured outcome of a tool execution
- ``ToolError``: a typed error emitted when a tool invocation fails

All types are JSON-serializable with ``to_dict()`` / ``from_dict()``
round-trip support, so agents can reliably parse and construct them.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

class ToolErrorCode(str, Enum):
    """Typed error codes for tool failures."""

    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    MISSING_REQUIRED_ARG = "missing_required_arg"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"


# ---------------------------------------------------------------------------
# Tool Invocation (request)
# ---------------------------------------------------------------------------

@dataclass
class ToolInvocation:
    """A request to execute a specific CodexA tool.

    Attributes:
        tool_name: Name of the tool to invoke (must match a registered tool).
        arguments: Key-value arguments required by the tool.
        request_id: Caller-assigned correlation ID (auto-generated if empty).
        timestamp: Unix timestamp of the invocation.
    """

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.request_id:
            self.request_id = uuid.uuid4().hex[:12]
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolInvocation:
        return cls(
            tool_name=data.get("tool_name", ""),
            arguments=data.get("arguments", {}),
            request_id=data.get("request_id", ""),
            timestamp=data.get("timestamp", 0.0),
        )

    @classmethod
    def from_json(cls, text: str) -> ToolInvocation:
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# Tool Error
# ---------------------------------------------------------------------------

@dataclass
class ToolError:
    """A typed error from a failed tool invocation.

    Attributes:
        tool_name: The tool that failed.
        error_code: Machine-readable error classification.
        error_message: Human-readable description of what went wrong.
        request_id: Correlation ID from the original invocation.
    """

    tool_name: str
    error_code: str
    error_message: str
    request_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "request_id": self.request_id,
        }

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolError:
        return cls(
            tool_name=data.get("tool_name", ""),
            error_code=data.get("error_code", ""),
            error_message=data.get("error_message", ""),
            request_id=data.get("request_id", ""),
        )


# ---------------------------------------------------------------------------
# Tool Execution Result (response)
# ---------------------------------------------------------------------------

@dataclass
class ToolExecutionResult:
    """Structured outcome of a tool invocation.

    Attributes:
        tool_name: Name of the tool that was executed.
        request_id: Correlation ID from the original invocation.
        success: Whether the tool completed without error.
        result_payload: Tool output data (only present when success=True).
        error: Typed error (only present when success=False).
        execution_time_ms: Wall-clock execution time in milliseconds.
        timestamp: Unix timestamp of result creation.
    """

    tool_name: str
    request_id: str = ""
    success: bool = True
    result_payload: dict[str, Any] = field(default_factory=dict)
    error: ToolError | None = None
    execution_time_ms: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tool_name": self.tool_name,
            "request_id": self.request_id,
            "success": self.success,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "timestamp": self.timestamp,
        }
        if self.success:
            result["result_payload"] = self.result_payload
        else:
            result["error"] = self.error.to_dict() if self.error else None
        return result

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolExecutionResult:
        error_data = data.get("error")
        error = ToolError.from_dict(error_data) if error_data else None
        return cls(
            tool_name=data.get("tool_name", ""),
            request_id=data.get("request_id", ""),
            success=data.get("success", True),
            result_payload=data.get("result_payload", {}),
            error=error,
            execution_time_ms=data.get("execution_time_ms", 0.0),
            timestamp=data.get("timestamp", 0.0),
        )
