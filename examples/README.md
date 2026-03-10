# CodexA Examples

## Basic Workflow

```bash
# 1. Install
pip install codexa

# 2. Initialize and index your project
cd /path/to/your-project
codexa init --index

# 3. Search your code
codexa search "authentication"
codexa search "error handling" --json

# 4. Explore symbols
codexa explain UserService
codexa context parse_config
codexa deps src/auth.py

# 5. Quality analysis
codexa quality src/
codexa hotspots
codexa impact
```

## JSON Output for Scripting

Every command supports `--json` for machine-readable output:

```bash
# Pipe search results to jq
codexa search "database" --json | jq '.snippets[].file_path'

# Quality report as JSON
codexa quality src/ --json > quality-report.json

# Doctor check in CI
codexa doctor --json
```

## AI Agent Integration

### CLI Tool Mode (for GitHub Copilot)

```bash
codexa tool list --json
codexa tool run semantic_search --arg query="auth middleware" --json
codexa tool run explain_symbol --arg symbol_name="UserService" --json
codexa tool run get_call_graph --arg symbol_name="process_payment" --json
```

### HTTP Bridge Server

```bash
# Start the server
codexa serve --port 24842

# Query via curl
curl -X POST http://127.0.0.1:24842/tools/invoke \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "semantic_search", "arguments": {"query": "auth"}}'
```

### MCP Server (for Claude Desktop / Cursor)

```bash
codexa mcp --path /your/project
```

## Grep (No Index Required)

```bash
codexa grep "TODO|FIXME" -n
codexa grep "def test_" --hidden -c
codexa grep "import os" -A 3 -B 1
```

## Watch Mode (Live Re-indexing)

```bash
codexa index . --watch
```

## Multi-Repo Workspace

```bash
codexa workspace init my-workspace
codexa workspace add /path/to/repo1
codexa workspace add /path/to/repo2
codexa workspace search "auth" --json
```
