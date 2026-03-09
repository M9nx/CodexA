# AI Agent Setup

CodexA is designed as an **AI-native** tool — it provides structured interfaces
for AI coding assistants to understand and navigate your codebase.

## Integration Methods

| Method | Transport | Best For |
|--------|-----------|----------|
| [VS Code Copilot](#vs-code-copilot) | CLI subprocess | GitHub Copilot Chat |
| [MCP Server](#mcp-server) | stdio JSON-RPC | Claude Desktop, Cursor |
| [HTTP Bridge](#http-bridge) | REST/SSE | Any HTTP client, custom agents |
| [CLI](#cli-integration) | Shell subprocess | Scripts, CI, any agent |

## VS Code Copilot

Create `.github/copilot-instructions.md` in your project:

```markdown
## CodexA Integration

This project uses CodexA for semantic code search.

### Available Commands

- `codex search "<query>" --json` — Search the codebase
- `codex tool run explain_symbol --arg symbol_name="<name>" --json`
- `codex tool run get_call_graph --arg symbol_name="<name>" --json`
- `codex tool run get_dependencies --arg file_path="<path>" --json`
- `codex tool run find_references --arg symbol_name="<name>" --json`
- `codex quality <path> --json` — Code quality analysis
- `codex impact <target> --json` — Blast radius analysis

### Rules

1. Always use `--json` flag for machine-readable output.
2. When asked about code structure, search with `codex search` first.
3. When explaining a function, use `codex tool run explain_symbol`.
```

Then enable it in VS Code `settings.json`:

```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    { "file": ".github/copilot-instructions.md" }
  ]
}
```

## MCP Server

Start the MCP server for Claude Desktop or Cursor:

```bash
codex mcp --path /your/project
```

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codex": {
      "command": "codex",
      "args": ["mcp", "--path", "/your/project"]
    }
  }
}
```

### Available MCP Tools

All 8 built-in tools are exposed via MCP:

| Tool | Description |
|------|-------------|
| `semantic_search` | Natural language code search |
| `explain_symbol` | Structural symbol explanation |
| `explain_file` | All symbols in a file |
| `summarize_repo` | Repository overview |
| `find_references` | Cross-reference lookup |
| `get_dependencies` | File import/dependency map |
| `get_call_graph` | Caller/callee relationships |
| `get_context` | Rich context window for AI |

## HTTP Bridge

For persistent connections from any HTTP client:

```bash
codex serve --host 127.0.0.1 --port 24842 --path /your/project
```

### Invoke a Tool

```bash
curl -X POST http://127.0.0.1:24842/tools/invoke \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "semantic_search", "arguments": {"query": "auth"}}'
```

### List Available Tools

```bash
curl http://127.0.0.1:24842/tools/list
```

### Bridge Request Format

```json
{
  "kind": "semantic_search",
  "params": {"query": "authentication", "top_k": 5},
  "request_id": "req-001",
  "source": "my-agent"
}
```

See the [Bridge Reference](../reference/bridge) for the full HTTP API.

## CLI Integration

Any agent that can spawn subprocesses can use CodexA directly:

```bash
# All commands support --json for structured output
codex search "error handling" --json
codex tool run semantic_search --arg query="auth" --json
codex quality src/ --json
codex impact parse_file --json
codex summary --json
```

### Output Format

JSON output is always a structured object:

```json
{
  "tool_name": "semantic_search",
  "success": true,
  "result_payload": {
    "snippets": [
      {
        "file_path": "src/auth.py",
        "symbol": "authenticate",
        "score": 0.89,
        "content": "def authenticate(token): ..."
      }
    ]
  },
  "execution_time_ms": 42.5
}
```

## Tool Protocol

All AI integration methods share the same **Tool Invocation Protocol**:

1. **Request** — `ToolInvocation` with tool name, arguments, and request ID
2. **Validation** — Arguments checked against declared schemas
3. **Execution** — Tool runs and produces a `ToolExecutionResult`
4. **Response** — Success with `result_payload` or failure with typed `ToolError`

Error codes are machine-readable: `unknown_tool`, `invalid_arguments`,
`missing_required_arg`, `execution_error`, `timeout`, `permission_denied`.

See the [AI Tools](../features/ai-tools) feature page for the full protocol specification.
