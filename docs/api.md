# API Reference

CodexA exposes four API surfaces: Python API, REST API, Bridge Protocol, and MCP.

## Python API

### ToolExecutor

The primary programmatic interface for invoking CodexA tools.

```python
from semantic_code_intelligence.tools import ToolExecutor, ToolInvocation

executor = ToolExecutor(project_path=".")
invocation = ToolInvocation(tool_name="semantic_search", arguments={"query": "auth"})
result = executor.execute(invocation)

print(result.success)   # True
print(result.data)      # Search results
```

### Available Tools

| Tool | Arguments | Returns |
|------|-----------|---------|
| `semantic_search` | `query: str` | Ranked code snippets |
| `explain_symbol` | `symbol_name: str` | Symbol explanation |
| `explain_file` | `file_path: str` | All symbols in file |
| `summarize_repo` | *(none)* | Repository summary |
| `find_references` | `symbol_name: str` | All references |
| `get_dependencies` | `file_path: str` | Import/dependency map |
| `get_call_graph` | `symbol_name: str` | Callers and callees |
| `get_context` | `symbol_name: str` | Rich context window |

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

---

## REST API

Start the web server:

```bash
codex web --port 8080
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/search?q=QUERY&top_k=N` | Semantic search |
| `GET` | `/api/symbol/:name` | Symbol details |
| `GET` | `/api/deps/:file_path` | File dependencies |
| `GET` | `/api/call-graph/:symbol` | Call graph |
| `GET` | `/api/quality?path=PATH` | Quality analysis |
| `GET` | `/api/hotspots?top=N` | Hotspot detection |
| `GET` | `/api/metrics` | Code metrics |
| `GET` | `/api/health` | Health check |

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

See [Web Interface](WEB.md) for the complete REST API documentation.

---

## Bridge Protocol

The bridge provides a stateless JSON/HTTP protocol for IDE extensions.

Start the bridge:

```bash
codex serve --port 24842
```

### Tool Invocation

```bash
curl -X POST http://127.0.0.1:24842/tools/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "semantic_search",
    "arguments": {"query": "error handling"}
  }'
```

### Request Kinds

| Kind | Description |
|------|-------------|
| `semantic_search` | Search codebase |
| `explain_symbol` | Explain a symbol |
| `get_context` | Rich context for AI |
| `validate_code` | Code validation |
| `invoke_tool` | Generic tool invocation |
| `complete` | Code completion |
| `hover` | Hover information |
| `definition` | Go to definition |
| `references` | Find references |
| `diagnostics` | Code diagnostics |
| `format` | Code formatting |
| `actions` | Code actions |

See [Bridge Protocol](BRIDGE.md) for the full specification.

---

## MCP (Model Context Protocol)

CodexA implements an MCP server using the official MCP SDK with stdio transport.

### Start MCP Server

```bash
codex mcp
```

### Configure in VS Code

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "codexa": {
      "command": "codex",
      "args": ["mcp"]
    }
  }
}
```

### Available MCP Tools

All 8 built-in tools are exposed via MCP:

- `semantic_search` — Search codebase by query
- `explain_symbol` — Explain a symbol
- `explain_file` — Explain all symbols in a file
- `summarize_repo` — Repository summary
- `find_references` — Find references to a symbol
- `get_dependencies` — File dependency map
- `get_call_graph` — Function call graph
- `get_context` — Rich context window

See [AI Tool Protocol](AI_TOOL_PROTOCOL.md) for detailed tool schemas.
