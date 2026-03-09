# AI Tool Protocol Reference

This document describes the AI Agent Tooling Protocol introduced in
**Phase 19** of CodexA.  It enables AI coding agents to invoke CodexA
tools via structured JSON requests and receive typed results.

## Overview

The protocol provides three layers:

1. **Tool Invocation Protocol** — typed request/response dataclasses
2. **Tool Execution Engine** — validates, routes, and executes tools
3. **Bridge HTTP Endpoints** — REST + SSE for external agents

## Protocol Dataclasses

### ToolInvocation

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Name of the tool to invoke |
| `arguments` | `dict` | Key-value arguments |
| `request_id` | `str` | Correlation ID (auto-generated) |
| `timestamp` | `float` | Unix timestamp |

### ToolExecutionResult

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Tool that was executed |
| `request_id` | `str` | Correlation ID |
| `success` | `bool` | Whether execution succeeded |
| `result_payload` | `dict` | Output data (success only) |
| `error` | `ToolError` | Error details (failure only) |
| `execution_time_ms` | `float` | Execution time |

### ToolError

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Tool that failed |
| `error_code` | `str` | Machine-readable code |
| `error_message` | `str` | Human-readable message |
| `request_id` | `str` | Correlation ID |

### Error Codes

| Code | Meaning |
|------|---------|
| `unknown_tool` | Unknown Tool |
| `invalid_arguments` | Invalid Arguments |
| `missing_required_arg` | Missing Required Arg |
| `execution_error` | Execution Error |
| `timeout` | Timeout |
| `permission_denied` | Permission Denied |

## Available Tools

| Tool | Description |
|------|-------------|
| `semantic_search` | Search the codebase using natural language. Returns relevant code snippets ranke |
| `explain_symbol` | Get a structural explanation of a code symbol (function, class, method). |
| `explain_file` | Get explanations of all symbols in a source file. |
| `summarize_repo` | Get a structured summary of the entire repository. |
| `find_references` | Find all references to a symbol across the codebase. |
| `get_dependencies` | Get the dependency map (imports) for a specific file. |
| `get_call_graph` | Get the call graph for a symbol, showing callers and callees. |
| `get_context` | Build a rich context window around a symbol for AI-assisted tasks. |

## HTTP Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tools/invoke` | Execute a tool invocation |
| `GET` | `/tools/list` | List available tools |
| `GET` | `/tools/stream` | SSE stream of tool events |
| `POST` | `/request` | Legacy bridge request (supports `invoke_tool`, `list_tools` kinds) |

## CLI Usage

```
codex tool list              # list all tools
codex tool run <name> --arg key=value
codex tool schema <name>     # show tool schema
```

## Plugin Tool Registration

Plugins can register custom tools via the `REGISTER_TOOL` hook:

```python
def on_hook(self, hook, data):
    if hook == PluginHook.REGISTER_TOOL:
        data["tools"].append({
            "name": "my_tool",
            "description": "My custom tool",
            "parameters": {"input": {"type": "string", "required": True}},
            "handler": my_handler_function,
        })
    return data
```

## Safety Guardrails

- Tools are deterministic and read-only (no code execution)
- All arguments are validated against declared schemas
- Plugin tools cannot overwrite built-in tool names
- Error codes are typed for reliable machine parsing
