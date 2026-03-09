# Plugin SDK Reference

Auto-generated from the CodexA plugin architecture.

## Hook Points

CodexA provides **22** hook points in the processing pipeline:

| Hook | Value | Category |
|------|-------|----------|
| `PRE_INDEX` | `pre_index` | Indexing |
| `POST_INDEX` | `post_index` | Indexing |
| `ON_CHUNK` | `on_chunk` | Indexing |
| `PRE_SEARCH` | `pre_search` | Search |
| `POST_SEARCH` | `post_search` | Search |
| `PRE_ANALYSIS` | `pre_analysis` | Analysis |
| `POST_ANALYSIS` | `post_analysis` | Analysis |
| `PRE_AI` | `pre_ai` | AI |
| `POST_AI` | `post_ai` | AI |
| `ON_FILE_CHANGE` | `on_file_change` | File Events |
| `ON_STREAM` | `on_stream` | Streaming |
| `CUSTOM_VALIDATION` | `custom_validation` | Validation |
| `PRE_HOTSPOT_ANALYSIS` | `pre_hotspot_analysis` | Other |
| `POST_HOTSPOT_ANALYSIS` | `post_hotspot_analysis` | Other |
| `PRE_IMPACT_ANALYSIS` | `pre_impact_analysis` | Other |
| `POST_IMPACT_ANALYSIS` | `post_impact_analysis` | Other |
| `PRE_TRACE` | `pre_trace` | Other |
| `POST_TRACE` | `post_trace` | Other |
| `REGISTER_TOOL` | `register_tool` | Other |
| `PRE_TOOL_INVOKE` | `pre_tool_invoke` | Other |
| `POST_TOOL_INVOKE` | `post_tool_invoke` | Other |
| `CUSTOM` | `custom` | Custom |

## Plugin Base Class

All plugins extend `PluginBase` and implement the following interface:

```python
class PluginBase(ABC):
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin name, version, description, and registered hooks."""

    def activate(self, context: dict) -> None:
        """Called when the plugin is activated."""

    def deactivate(self) -> None:
        """Called when the plugin is deactivated."""

    def on_hook(self, hook: PluginHook, data: dict) -> dict:
        """Called when a registered hook fires. Modify and return data."""
```

## PluginMetadata

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique plugin name |
| `version` | `str` | Semantic version (default: `0.1.0`) |
| `description` | `str` | Human-readable description |
| `author` | `str` | Author name |
| `hooks` | `list[PluginHook]` | Hooks this plugin subscribes to |

## Discovery

Plugins are discovered from `.codex/plugins/` directories. Each plugin file
must define a `create_plugin()` factory function that returns a `PluginBase` instance.

## Lifecycle

1. **Register** — `PluginManager.register(plugin)` adds the plugin
2. **Activate** — `PluginManager.activate(name, context)` calls `plugin.activate()`
3. **Dispatch** — `PluginManager.dispatch(hook, data)` chains through active plugins
4. **Deactivate** — `PluginManager.deactivate(name)` calls `plugin.deactivate()`
