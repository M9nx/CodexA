# API Reference

CodexA exposes four API surfaces: Python API, REST API, Bridge Protocol, and MCP.

## Python API

### ToolExecutor

The primary programmatic interface for invoking CodexA tools:

```python
from semantic_code_intelligence.tools import ToolExecutor, ToolInvocation

executor = ToolExecutor(project_path=".")
invocation = ToolInvocation(tool_name="semantic_search", arguments={"query": "auth"})
result = executor.execute(invocation)

print(result.success)        # True
print(result.result_payload) # Search results
print(result.execution_time_ms)
```

### Available Tools

| Tool | Arguments | Returns |
|------|-----------|---------|
| `semantic_search` | `query: str`, `top_k: int` | Ranked code snippets |
| `explain_symbol` | `symbol_name: str`, `file_path: str` | Symbol explanation |
| `explain_file` | `file_path: str` | All symbols in file |
| `summarize_repo` | *(none)* | Repository summary |
| `find_references` | `symbol_name: str` | All references |
| `get_dependencies` | `file_path: str` | Import/dependency map |
| `get_call_graph` | `symbol_name: str` | Callers and callees |
| `get_context` | `symbol_name: str`, `file_path: str` | Rich context window |

### Indexing

```python
from semantic_code_intelligence.indexing import run_indexing
from pathlib import Path

result = run_indexing(Path("."))
print(f"Indexed {result.files} files, {result.chunks} chunks")
```

### Search

```python
from semantic_code_intelligence.search import hybrid_search

results = hybrid_search("authentication middleware", top_k=10)
for r in results:
    print(f"{r.file}:{r.line} (score: {r.score:.3f})")
```

### Context Building

```python
from semantic_code_intelligence.context import ContextBuilder

builder = ContextBuilder(project_path=".")
context = builder.build_context("UserService", max_tokens=4000)
print(context.text)
```

### Quality Analysis

```python
from semantic_code_intelligence.ci import run_quality_analysis

report = run_quality_analysis("src/")
print(f"Maintainability: {report.maintainability_index:.1f}")
print(f"Security issues: {len(report.bandit_issues)}")
```

## REST API

Start the web server:

```bash
codexa web --port 8080
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server health and project metadata |
| `GET` | `/api/search?q=&top_k=&threshold=` | Semantic code search |
| `GET` | `/api/symbols?file=&kind=` | Symbol table browser |
| `GET` | `/api/deps?file=` | File dependency graph |
| `GET` | `/api/callgraph?symbol=` | Call graph edges |
| `GET` | `/api/summary` | Project summary |
| `POST` | `/api/ask` | Natural language question |
| `POST` | `/api/analyze` | Code validation/explanation |

### Example

```bash
curl "http://localhost:8080/api/search?q=authentication&top_k=5"
```

```json
{
  "results": [
    {
      "file": "src/auth/middleware.py",
      "line": 42,
      "score": 0.89,
      "snippet": "class AuthMiddleware:..."
    }
  ]
}
```

## Bridge Protocol

The bridge provides a stateless JSON/HTTP protocol for IDE extensions:

```bash
codexa serve --port 24842
```

### Tool Invocation

```bash
curl -X POST http://127.0.0.1:24842/tools/invoke \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "semantic_search", "arguments": {"query": "auth"}}'
```

### Bridge Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Capabilities manifest |
| `GET` | `/health` | Health check |
| `POST` | `/request` | Handle an AgentRequest |
| `POST` | `/tools/invoke` | Execute a tool |
| `GET` | `/tools/list` | List tools |
| `GET` | `/tools/stream` | SSE event stream |

### Request Format

```json
{
  "kind": "semantic_search",
  "params": {"query": "authentication", "top_k": 5},
  "request_id": "req-001",
  "source": "copilot"
}
```

### Response Format

```json
{
  "success": true,
  "data": {"snippets": [...]},
  "error": "",
  "request_id": "req-001",
  "elapsed_ms": 42.5
}
```

See the [Bridge Reference](bridge) for the full protocol specification.

## MCP (Model Context Protocol)

```bash
codexa mcp --path /your/project
```

All 13 tools are exposed via MCP with typed schemas. See [MCP Integration](../features/mcp-integration) for setup instructions.
