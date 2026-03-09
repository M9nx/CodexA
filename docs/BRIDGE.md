# Bridge Protocol Reference

Auto-generated from the CodexA agent cooperation protocol.

## Overview

CodexA exposes a stateless JSON/HTTP bridge (`codex serve`) that any
IDE extension or AI assistant can use to request context.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Capabilities manifest |
| GET | `/health` | Health check |
| POST | `/request` | Handle an AgentRequest |
| OPTIONS | `*` | CORS preflight |

## Request Kinds

The bridge supports **12** request types:

| Kind | Value |
|------|-------|
| `SEMANTIC_SEARCH` | `semantic_search` |
| `EXPLAIN_SYMBOL` | `explain_symbol` |
| `EXPLAIN_FILE` | `explain_file` |
| `GET_CONTEXT` | `get_context` |
| `GET_DEPENDENCIES` | `get_dependencies` |
| `GET_CALL_GRAPH` | `get_call_graph` |
| `SUMMARIZE_REPO` | `summarize_repo` |
| `FIND_REFERENCES` | `find_references` |
| `VALIDATE_CODE` | `validate_code` |
| `LIST_CAPABILITIES` | `list_capabilities` |
| `INVOKE_TOOL` | `invoke_tool` |
| `LIST_TOOLS` | `list_tools` |

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
| `kind` | `string` | One of the RequestKind values |
| `params` | `object` | Operation-specific parameters |
| `request_id` | `string` | Caller-assigned correlation ID |
| `source` | `string` | Identifier of calling agent |

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
| `success` | `boolean` | Whether the request succeeded |
| `data` | `object` | Structured response payload |
| `error` | `string` | Error message if success is false |
| `request_id` | `string` | Echoed correlation ID |
| `elapsed_ms` | `number` | Processing time in milliseconds |
