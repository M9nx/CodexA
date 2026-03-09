# Tool Registry Reference

Auto-generated from the CodexA tool-calling interface.

These tools provide a structured JSON interface for LLM agents.

**8 tools available:**

| Tool | Description |
|------|-------------|
| `semantic_search` | Search the codebase using natural language. Returns relevant code snippets ranked by similarity. |
| `explain_symbol` | Get a structural explanation of a code symbol (function, class, method). |
| `explain_file` | Get explanations of all symbols in a source file. |
| `summarize_repo` | Get a structured summary of the entire repository. |
| `find_references` | Find all references to a symbol across the codebase. |
| `get_dependencies` | Get the dependency map (imports) for a specific file. |
| `get_call_graph` | Get the call graph for a symbol, showing callers and callees. |
| `get_context` | Build a rich context window around a symbol for AI-assisted tasks. |

## Usage

```python
from semantic_code_intelligence.tools import ToolRegistry

registry = ToolRegistry(project_root="/path/to/repo")
result = registry.call("search", {"query": "auth"})
print(result.to_json())
```
