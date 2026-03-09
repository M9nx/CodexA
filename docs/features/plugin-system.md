# Plugin System

CodexA provides a plugin architecture with **22 hook points** for extending
and customizing every stage of the pipeline.

## Quick Start

Create a plugin:

```bash
codex plugin new my-formatter --hooks POST_SEARCH,POST_AI
```

This generates a ready-to-use plugin file in `.codex/plugins/`.

## Plugin Base Class

All plugins extend `PluginBase`:

```python
from semantic_code_intelligence.plugins import PluginBase, PluginMetadata, PluginHook

class MyPlugin(PluginBase):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my-plugin",
            version="0.1.0",
            description="My custom plugin",
            author="Your Name",
            hooks=[PluginHook.POST_SEARCH, PluginHook.POST_AI],
        )

    def activate(self, context: dict) -> None:
        """Called when the plugin is activated."""
        pass

    def deactivate(self) -> None:
        """Called when the plugin is deactivated."""
        pass

    def on_hook(self, hook: PluginHook, data: dict) -> dict:
        """Called when a registered hook fires."""
        if hook == PluginHook.POST_SEARCH:
            # Modify search results
            data["results"] = self.filter_results(data["results"])
        return data

def create_plugin():
    return MyPlugin()
```

## Hook Points

### Indexing

| Hook | When | Data |
|------|------|------|
| `PRE_INDEX` | Before indexing starts | File list, config |
| `POST_INDEX` | After indexing completes | Index stats |
| `ON_CHUNK` | Each chunk is created | Chunk content, metadata |

### Search

| Hook | When | Data |
|------|------|------|
| `PRE_SEARCH` | Before search execution | Query, parameters |
| `POST_SEARCH` | After results ranked | Results list |

### Analysis

| Hook | When | Data |
|------|------|------|
| `PRE_ANALYSIS` | Before code analysis | Target info |
| `POST_ANALYSIS` | After analysis completes | Analysis results |

### AI

| Hook | When | Data |
|------|------|------|
| `PRE_AI` | Before LLM call | Prompt, context |
| `POST_AI` | After LLM response | Response text |
| `ON_STREAM` | Each streaming token | Token event |

### Workflow Intelligence

| Hook | When | Data |
|------|------|------|
| `PRE_HOTSPOT_ANALYSIS` | Before hotspot scoring | Symbols, config |
| `POST_HOTSPOT_ANALYSIS` | After hotspot report | Report |
| `PRE_IMPACT_ANALYSIS` | Before impact BFS | Target, graph |
| `POST_IMPACT_ANALYSIS` | After impact report | Report |
| `PRE_TRACE` | Before symbol trace | Target, graph |
| `POST_TRACE` | After trace result | Result |

### Tools

| Hook | When | Data |
|------|------|------|
| `REGISTER_TOOL` | Plugin can register tools | Tool list |
| `PRE_TOOL_INVOKE` | Before tool execution | Invocation |
| `POST_TOOL_INVOKE` | After tool execution | Result |

### Other

| Hook | When | Data |
|------|------|------|
| `ON_FILE_CHANGE` | File change detected | File path, event |
| `CUSTOM_VALIDATION` | Custom validation pass | Validation data |
| `CUSTOM` | User-defined | User-defined |

## Plugin Discovery

Plugins are discovered from `.codex/plugins/`. Each file must export a
`create_plugin()` factory function.

## Plugin Lifecycle

1. **Register** — `PluginManager.register(plugin)` adds the plugin
2. **Activate** — `PluginManager.activate(name, context)` calls `plugin.activate()`
3. **Dispatch** — Hooks are dispatched in registration order; each plugin can modify data
4. **Deactivate** — `PluginManager.deactivate(name)` calls `plugin.deactivate()`

## CLI Management

```bash
codex plugin list              # List discovered plugins
codex plugin info my-plugin    # Plugin details
codex plugin new name          # Scaffold new plugin
```

## Custom Tool Registration

Plugins can register tools exposed via CLI, HTTP bridge, and MCP:

```python
def on_hook(self, hook, data):
    if hook == PluginHook.REGISTER_TOOL:
        data["tools"].append({
            "name": "my_custom_search",
            "description": "Domain-specific search",
            "parameters": {
                "query": {"type": "string", "required": True},
                "domain": {"type": "string", "required": False},
            },
            "handler": self.custom_search,
        })
    return data
```

Plugin tools cannot overwrite built-in tool names.
