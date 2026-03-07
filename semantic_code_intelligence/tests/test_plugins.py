"""Tests for the plugin architecture SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from semantic_code_intelligence.plugins import (
    PluginBase,
    PluginHook,
    PluginManager,
    PluginMetadata,
)


# ---------------------------------------------------------------------------
# Test Plugin Implementation
# ---------------------------------------------------------------------------

class SamplePlugin(PluginBase):
    """A simple plugin for testing."""

    def __init__(self, name: str = "test-plugin") -> None:
        self._name = name
        self.activated = False
        self.deactivated = False
        self.hooks_received: list[tuple[PluginHook, dict]] = []

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version="1.0.0",
            description="Test plugin",
            hooks=[PluginHook.PRE_INDEX, PluginHook.POST_INDEX],
        )

    def activate(self, context: dict[str, Any]) -> None:
        self.activated = True

    def deactivate(self) -> None:
        self.deactivated = True

    def on_hook(self, hook: PluginHook, data: dict[str, Any]) -> dict[str, Any]:
        self.hooks_received.append((hook, dict(data)))
        data["processed_by"] = self._name
        return data


class FailingPlugin(PluginBase):
    """A plugin that raises during hook dispatch."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="failing-plugin",
            hooks=[PluginHook.PRE_INDEX],
        )

    def on_hook(self, hook: PluginHook, data: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Plugin error!")


# ---------------------------------------------------------------------------
# PluginMetadata
# ---------------------------------------------------------------------------

class TestPluginMetadata:
    def test_to_dict(self):
        meta = PluginMetadata(
            name="my-plugin",
            version="2.0",
            description="Test",
            hooks=[PluginHook.PRE_SEARCH],
        )
        d = meta.to_dict()
        assert d["name"] == "my-plugin"
        assert d["version"] == "2.0"
        assert "pre_search" in d["hooks"]

    def test_defaults(self):
        meta = PluginMetadata(name="minimal")
        assert meta.version == "0.1.0"
        assert meta.hooks == []


# ---------------------------------------------------------------------------
# PluginHook Enum
# ---------------------------------------------------------------------------

class TestPluginHook:
    def test_values(self):
        assert PluginHook.PRE_INDEX.value == "pre_index"
        assert PluginHook.POST_SEARCH.value == "post_search"
        assert PluginHook.ON_FILE_CHANGE.value == "on_file_change"

    def test_all_hooks_are_strings(self):
        for hook in PluginHook:
            assert isinstance(hook.value, str)


# ---------------------------------------------------------------------------
# PluginManager — Registration
# ---------------------------------------------------------------------------

class TestPluginManagerRegistration:
    def test_register(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        assert "test-plugin" in mgr.registered_plugins

    def test_register_duplicate_replaces(self):
        mgr = PluginManager()
        p1 = SamplePlugin("dup")
        p2 = SamplePlugin("dup")
        mgr.register(p1)
        mgr.register(p2)
        assert mgr.registered_plugins.count("dup") == 1

    def test_unregister(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        mgr.unregister("test-plugin")
        assert "test-plugin" not in mgr.registered_plugins

    def test_unregister_nonexistent(self):
        mgr = PluginManager()
        mgr.unregister("nope")  # should not raise


# ---------------------------------------------------------------------------
# PluginManager — Activation
# ---------------------------------------------------------------------------

class TestPluginManagerActivation:
    def test_activate(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        mgr.activate("test-plugin")
        assert "test-plugin" in mgr.active_plugins
        assert plugin.activated

    def test_deactivate(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        mgr.activate("test-plugin")
        mgr.deactivate("test-plugin")
        assert "test-plugin" not in mgr.active_plugins
        assert plugin.deactivated

    def test_activate_unregistered(self):
        mgr = PluginManager()
        with pytest.raises(ValueError):
            mgr.activate("nope")

    def test_unregister_active_deactivates(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        mgr.activate("test-plugin")
        mgr.unregister("test-plugin")
        assert plugin.deactivated


# ---------------------------------------------------------------------------
# PluginManager — Hook Dispatch
# ---------------------------------------------------------------------------

class TestPluginManagerDispatch:
    def test_dispatch_basic(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        mgr.activate("test-plugin")

        result = mgr.dispatch(PluginHook.PRE_INDEX, {"file": "test.py"})
        assert result["processed_by"] == "test-plugin"
        assert len(plugin.hooks_received) == 1

    def test_dispatch_skips_inactive(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        # Not activated
        result = mgr.dispatch(PluginHook.PRE_INDEX, {"file": "test.py"})
        assert "processed_by" not in result
        assert len(plugin.hooks_received) == 0

    def test_dispatch_unregistered_hook(self):
        mgr = PluginManager()
        plugin = SamplePlugin()  # only PRE_INDEX and POST_INDEX
        mgr.register(plugin)
        mgr.activate("test-plugin")

        result = mgr.dispatch(PluginHook.PRE_SEARCH, {"query": "test"})
        assert "processed_by" not in result  # plugin not registered for this hook

    def test_dispatch_chain(self):
        mgr = PluginManager()
        p1 = SamplePlugin("plugin-a")
        p2 = SamplePlugin("plugin-b")
        mgr.register(p1)
        mgr.register(p2)
        mgr.activate("plugin-a")
        mgr.activate("plugin-b")

        result = mgr.dispatch(PluginHook.PRE_INDEX, {"count": 0})
        # Last plugin wins for processed_by
        assert result["processed_by"] == "plugin-b"

    def test_dispatch_failing_plugin_continues(self):
        mgr = PluginManager()
        failing = FailingPlugin()
        good = SamplePlugin()
        mgr.register(failing)
        mgr.register(good)
        mgr.activate("failing-plugin")
        mgr.activate("test-plugin")

        # Should not raise; failing plugin error is caught
        result = mgr.dispatch(PluginHook.PRE_INDEX, {"x": 1})
        assert result["processed_by"] == "test-plugin"


# ---------------------------------------------------------------------------
# PluginManager — Info
# ---------------------------------------------------------------------------

class TestPluginManagerInfo:
    def test_get_plugin_info(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        info = mgr.get_plugin_info("test-plugin")
        assert info is not None
        assert info["name"] == "test-plugin"
        assert info["active"] is False

    def test_get_plugin_info_active(self):
        mgr = PluginManager()
        plugin = SamplePlugin()
        mgr.register(plugin)
        mgr.activate("test-plugin")
        info = mgr.get_plugin_info("test-plugin")
        assert info["active"] is True

    def test_get_plugin_info_missing(self):
        mgr = PluginManager()
        assert mgr.get_plugin_info("nope") is None


# ---------------------------------------------------------------------------
# Plugin Discovery
# ---------------------------------------------------------------------------

class TestPluginDiscovery:
    def test_discover_empty_dir(self, tmp_path):
        mgr = PluginManager()
        count = mgr.discover_from_directory(tmp_path)
        assert count == 0

    def test_discover_nonexistent_dir(self, tmp_path):
        mgr = PluginManager()
        count = mgr.discover_from_directory(tmp_path / "nope")
        assert count == 0

    def test_discover_valid_plugin(self, tmp_path):
        plugin_code = '''\
from semantic_code_intelligence.plugins import PluginBase, PluginMetadata, PluginHook

class MyPlugin(PluginBase):
    def metadata(self):
        return PluginMetadata(name="discovered", hooks=[PluginHook.PRE_INDEX])

def create_plugin():
    return MyPlugin()
'''
        (tmp_path / "my_plugin.py").write_text(plugin_code, encoding="utf-8")

        mgr = PluginManager()
        count = mgr.discover_from_directory(tmp_path)
        assert count == 1
        assert "discovered" in mgr.registered_plugins

    def test_discover_skips_underscore_files(self, tmp_path):
        (tmp_path / "_private.py").write_text("x = 1", encoding="utf-8")
        mgr = PluginManager()
        count = mgr.discover_from_directory(tmp_path)
        assert count == 0
