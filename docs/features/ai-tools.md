# AI Tools

CodexA implements a structured **AI Agent Tooling Protocol** — a typed
request/response system that enables AI coding assistants to invoke CodexA
tools via CLI, HTTP, or MCP.

## Available Tools

| Tool | Description |
|------|-------------|
| `semantic_search` | Natural language code search with ranked results |
| `explain_symbol` | Structural explanation of a function, class, or method |
| `explain_file` | Explain all symbols in a source file |
| `summarize_repo` | Structured summary of the entire repository |
| `find_references` | Find all references to a symbol across the codebase |
| `get_dependencies` | Import/dependency map for a file |
| `get_call_graph` | Callers and callees of a function |
| `get_context` | Rich context window for AI-assisted tasks |

## Invocation Methods

### CLI

```bash
codex tool list                                            # List tools
codex tool run semantic_search --arg query="auth" --json   # Run a tool
codex tool schema semantic_search                          # View schema
```

### HTTP Bridge

```bash
# Start the bridge server
codex serve --port 24842

# Invoke a tool
curl -X POST http://127.0.0.1:24842/tools/invoke \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "semantic_search", "arguments": {"query": "auth"}}'

# List tools
curl http://127.0.0.1:24842/tools/list

# SSE event stream
curl http://127.0.0.1:24842/tools/stream
```

### MCP (Model Context Protocol)

```bash
codex mcp --path /your/project
```

All 8 tools are exposed as MCP tools with proper schemas.

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
| `execution_time_ms` | `float` | Execution time in milliseconds |

### ToolError

| Code | Meaning |
|------|---------|
| `unknown_tool` | Tool name not recognized |
| `invalid_arguments` | Argument validation failed |
| `missing_required_arg` | Required argument not provided |
| `execution_error` | Runtime error during execution |
| `timeout` | Execution timed out |
| `permission_denied` | Permission denied |

## AI Workflows

### Multi-Turn Chat

Persistent conversations about your codebase:

```bash
codex chat "How does auth work?"
codex chat --session my-session "Follow up question"
codex chat --list-sessions
```

Sessions are stored in `.codex/sessions/` with full message history.

### Autonomous Investigation

Multi-step autonomous code exploration:

```bash
codex investigate "Find all security vulnerabilities"
codex investigate "How is the payment flow implemented?" --max-steps 10
```

The investigation loop:
1. LLM planner receives the question
2. Decides an action: `search`, `analyze`, `deps`, or `conclude`
3. Action is executed, results fed back to the planner
4. Repeats until conclusion or step limit

### Cross-Repo Refactoring

Find duplicate logic across workspace repos:

```bash
codex cross-refactor --threshold 0.70
```

### Streaming Responses

All LLM-powered commands support streaming:

```bash
codex chat --stream "Explain the auth flow"
codex investigate --stream "Find performance issues"
```

| Provider | Streaming |
|----------|-----------|
| OpenAI | Native streaming API |
| Ollama | Native HTTP streaming |
| Mock | Word-by-word simulation |

## Safety

- All tools are **read-only** — no code execution or modification
- Arguments are validated against declared schemas
- Plugin tools cannot overwrite built-in tool names
- Error codes are typed for reliable machine parsing

## Plugin Integration

Register custom tools via the `REGISTER_TOOL` hook:

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

Additional hooks: `PRE_TOOL_INVOKE`, `POST_TOOL_INVOKE`, `PRE_AI`, `POST_AI`, `ON_STREAM`.
