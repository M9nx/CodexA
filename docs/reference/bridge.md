# Bridge Protocol

CodexA exposes a stateless JSON/HTTP bridge (`codexa serve`) that any
IDE extension or AI assistant can use to request context.

## Quick Start

```bash
codexa serve --port 24842
```

The bridge binds to `127.0.0.1:24842` by default.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Capabilities manifest |
| `GET` | `/health` | Health check |
| `POST` | `/request` | Handle an AgentRequest |
| `POST` | `/tools/invoke` | Execute a tool invocation |
| `GET` | `/tools/list` | List available tools |
| `GET` | `/tools/stream` | SSE stream of tool events |
| `OPTIONS` | `*` | CORS preflight |

## Request Kinds

The bridge supports **12** request types:

| Kind | Value |
|------|-------|
| Semantic Search | `semantic_search` |
| Explain Symbol | `explain_symbol` |
| Explain File | `explain_file` |
| Get Context | `get_context` |
| Get Dependencies | `get_dependencies` |
| Get Call Graph | `get_call_graph` |
| Summarize Repo | `summarize_repo` |
| Find References | `find_references` |
| Validate Code | `validate_code` |
| List Capabilities | `list_capabilities` |
| Invoke Tool | `invoke_tool` |
| List Tools | `list_tools` |

## AgentRequest

```json
{
  "kind": "semantic_search",
  "params": {"query": "authentication", "top_k": 5},
  "request_id": "req-001",
  "source": "copilot"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `kind` | string | One of the RequestKind values |
| `params` | object | Operation-specific parameters |
| `request_id` | string | Caller-assigned correlation ID |
| `source` | string | Identifier of calling agent |

## AgentResponse

```json
{
  "success": true,
  "data": {"snippets": [...]},
  "error": "",
  "request_id": "req-001",
  "elapsed_ms": 42.5
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the request succeeded |
| `data` | object | Structured response payload |
| `error` | string | Error message (if failed) |
| `request_id` | string | Echoed correlation ID |
| `elapsed_ms` | number | Processing time in ms |

## Tool Invocation via Bridge

### Direct Tool Invoke

```bash
curl -X POST http://127.0.0.1:24842/tools/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "semantic_search",
    "arguments": {"query": "error handling"}
  }'
```

Response:

```json
{
  "tool_name": "semantic_search",
  "request_id": "auto-generated-id",
  "success": true,
  "result_payload": {
    "snippets": [...]
  },
  "execution_time_ms": 42.5
}
```

### List Available Tools

```bash
curl http://127.0.0.1:24842/tools/list
```

### SSE Event Stream

```bash
curl http://127.0.0.1:24842/tools/stream
```

Events are dispatched for each tool invocation, streaming, and completion.

## CORS

The bridge includes CORS headers for browser-based clients. Preflight
`OPTIONS` requests are handled automatically.

## Configuration

```bash
codexa serve [options]

Options:
  --host, -h TEXT     Host to bind (default: 127.0.0.1)
  --port, -p INTEGER  Port to bind (default: 24842)
  --path DIRECTORY    Project root path
```

## Architecture

```
Agent/IDE  →  HTTP  →  BridgeServer  →  RequestRouter  →  ToolExecutor  →  Core
                                                                            ↑
                                          ContextProvider  →  Search/Analysis
```

The bridge is a thin HTTP layer over the same `ToolExecutor` used by CLI and MCP.
