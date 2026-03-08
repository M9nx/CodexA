"""Tool execution engine — validates, routes, and executes tool invocations.

Wraps the existing ``ToolRegistry`` with:
- Argument validation against ``TOOL_DEFINITIONS`` schemas
- Structured ``ToolInvocation`` → ``ToolExecutionResult`` pipeline
- Plugin-registered tool support via ``REGISTER_TOOL`` hook
- Safety guardrails (deterministic, no arbitrary code execution)

Usage::

    executor = ToolExecutor(Path("."))
    result = executor.execute(ToolInvocation(tool_name="semantic_search",
                                              arguments={"query": "parse"}))
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from semantic_code_intelligence.tools import TOOL_DEFINITIONS, ToolRegistry
from semantic_code_intelligence.tools.protocol import (
    ToolError,
    ToolErrorCode,
    ToolExecutionResult,
    ToolInvocation,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("tools.executor")

# Type alias for plugin-registered tool handlers
ToolHandler = Callable[..., dict[str, Any]]


# ---------------------------------------------------------------------------
# Allowed tool names (safety guardrail)
# ---------------------------------------------------------------------------

_BUILTIN_TOOL_NAMES: frozenset[str] = frozenset(
    t["name"] for t in TOOL_DEFINITIONS
)


class ToolExecutor:
    """Validates and executes tool invocations against the registry.

    Adds a structured protocol layer on top of ToolRegistry:
    - Input validation against declared schemas
    - Typed error handling with ToolError / ToolErrorCode
    - Plugin-registered tool dispatch
    - Timing and correlation tracking
    """

    def __init__(self, project_root: Path) -> None:
        self._registry = ToolRegistry(project_root)
        self._plugin_tools: dict[str, dict[str, Any]] = {}
        self._plugin_handlers: dict[str, ToolHandler] = {}

    # ── tool discovery ────────────────────────────────────────────────

    @property
    def available_tools(self) -> list[dict[str, Any]]:
        """Return schemas of all available tools (built-in + plugin)."""
        tools = list(TOOL_DEFINITIONS)
        for name, schema in self._plugin_tools.items():
            tools.append(schema)
        return tools

    def list_tool_names(self) -> list[str]:
        """Return names of all available tools."""
        return [t["name"] for t in self.available_tools]

    def get_tool_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Return the schema definition for a specific tool, or None."""
        for t in self.available_tools:
            if t["name"] == tool_name:
                return t
        return None

    # ── plugin tool registration ──────────────────────────────────────

    def register_plugin_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        """Register a tool provided by a plugin.

        Args:
            name: Tool name (must not collide with built-in names).
            description: Human-readable purpose of the tool.
            parameters: Parameter schema matching TOOL_DEFINITIONS format.
            handler: Callable(**kwargs) → dict[str, Any].
        """
        if name in _BUILTIN_TOOL_NAMES:
            raise ValueError(
                f"Cannot register plugin tool '{name}': collides with built-in tool"
            )
        self._plugin_tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "source": "plugin",
        }
        self._plugin_handlers[name] = handler
        logger.info("Registered plugin tool: %s", name)

    def unregister_plugin_tool(self, name: str) -> bool:
        """Remove a plugin-registered tool. Returns True if it existed."""
        removed = name in self._plugin_tools
        self._plugin_tools.pop(name, None)
        self._plugin_handlers.pop(name, None)
        return removed

    # ── validation ────────────────────────────────────────────────────

    def _validate_arguments(
        self, invocation: ToolInvocation
    ) -> ToolError | None:
        """Validate invocation arguments against the tool schema.

        Returns a ToolError if validation fails, otherwise None.
        """
        schema = self.get_tool_schema(invocation.tool_name)
        if schema is None:
            return ToolError(
                tool_name=invocation.tool_name,
                error_code=ToolErrorCode.UNKNOWN_TOOL,
                error_message=f"Unknown tool: {invocation.tool_name}",
                request_id=invocation.request_id,
            )

        params_schema = schema.get("parameters", {})
        for param_name, param_def in params_schema.items():
            if param_def.get("required", False) and param_name not in invocation.arguments:
                return ToolError(
                    tool_name=invocation.tool_name,
                    error_code=ToolErrorCode.MISSING_REQUIRED_ARG,
                    error_message=f"Missing required argument: {param_name}",
                    request_id=invocation.request_id,
                )

        return None

    # ── execution ─────────────────────────────────────────────────────

    def execute(self, invocation: ToolInvocation) -> ToolExecutionResult:
        """Execute a tool invocation with full validation and error handling.

        Pipeline:
        1. Validate tool name and arguments
        2. Route to ToolRegistry (built-in) or plugin handler
        3. Wrap result in ToolExecutionResult with timing
        """
        # 1. validate
        validation_error = self._validate_arguments(invocation)
        if validation_error is not None:
            return ToolExecutionResult(
                tool_name=invocation.tool_name,
                request_id=invocation.request_id,
                success=False,
                error=validation_error,
            )

        # 2. route + execute
        start = time.monotonic()
        try:
            if invocation.tool_name in self._plugin_handlers:
                # Plugin tool
                handler = self._plugin_handlers[invocation.tool_name]
                data = handler(**invocation.arguments)
                success = True
                error = None
            else:
                # Built-in tool via ToolRegistry
                tool_result = self._registry.invoke(
                    invocation.tool_name, **invocation.arguments
                )
                data = tool_result.to_dict()
                success = tool_result.success
                error = None
                if not success:
                    error = ToolError(
                        tool_name=invocation.tool_name,
                        error_code=ToolErrorCode.EXECUTION_ERROR,
                        error_message=tool_result.error or "Tool execution failed",
                        request_id=invocation.request_id,
                    )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.exception("Tool execution failed: %s", invocation.tool_name)
            return ToolExecutionResult(
                tool_name=invocation.tool_name,
                request_id=invocation.request_id,
                success=False,
                error=ToolError(
                    tool_name=invocation.tool_name,
                    error_code=ToolErrorCode.EXECUTION_ERROR,
                    error_message=str(exc),
                    request_id=invocation.request_id,
                ),
                execution_time_ms=elapsed,
            )

        elapsed = (time.monotonic() - start) * 1000

        # 3. wrap result
        return ToolExecutionResult(
            tool_name=invocation.tool_name,
            request_id=invocation.request_id,
            success=success,
            result_payload=data if success else {},
            error=error,
            execution_time_ms=elapsed,
        )

    def execute_batch(
        self, invocations: list[ToolInvocation]
    ) -> list[ToolExecutionResult]:
        """Execute multiple tool invocations sequentially."""
        return [self.execute(inv) for inv in invocations]

    # ── convenience ───────────────────────────────────────────────────

    @property
    def registry(self) -> ToolRegistry:
        """Access the underlying ToolRegistry (for indexing etc.)."""
        return self._registry
