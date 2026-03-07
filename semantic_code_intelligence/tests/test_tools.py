"""Tests for the AI tool interaction layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantic_code_intelligence.tools import (
    TOOL_DEFINITIONS,
    ToolRegistry,
    ToolResult,
)


SAMPLE_PYTHON = """\
import os

def greet(name):
    return f"Hello, {name}!"

class Service:
    def __init__(self, url):
        self.url = url

    def call(self):
        return os.getenv("API_KEY")
"""


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------

class TestToolResult:
    def test_success(self):
        r = ToolResult(tool_name="test", success=True, data={"x": 1})
        d = r.to_dict()
        assert d["success"] is True
        assert d["data"]["x"] == 1

    def test_failure(self):
        r = ToolResult(tool_name="test", success=False, error="boom")
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "boom"

    def test_to_json(self):
        r = ToolResult(tool_name="test", success=True, data={})
        j = r.to_json()
        assert '"tool": "test"' in j
        assert '"success": true' in j


# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    def test_definitions_exist(self):
        assert len(TOOL_DEFINITIONS) > 0

    def test_all_have_names(self):
        for defn in TOOL_DEFINITIONS:
            assert "name" in defn
            assert "description" in defn

    def test_known_tools(self):
        names = {d["name"] for d in TOOL_DEFINITIONS}
        assert "semantic_search" in names
        assert "explain_symbol" in names
        assert "summarize_repo" in names
        assert "get_context" in names


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_init(self, tmp_path):
        registry = ToolRegistry(tmp_path)
        assert registry.tool_definitions == TOOL_DEFINITIONS

    def test_unknown_tool(self, tmp_path):
        registry = ToolRegistry(tmp_path)
        result = registry.invoke("nonexistent_tool")
        assert result.success is False
        assert "Unknown tool" in result.error

    def test_explain_symbol_not_found(self, tmp_path):
        registry = ToolRegistry(tmp_path)
        result = registry.invoke("explain_symbol", symbol_name="NoSuchSymbol")
        assert result.success is False

    def test_index_and_explain_symbol(self, tmp_path):
        f = tmp_path / "service.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")

        registry = ToolRegistry(tmp_path)
        registry.index_file(str(f))

        result = registry.invoke("explain_symbol", symbol_name="greet")
        assert result.success is True
        assert result.data["symbol_name"] == "greet"
        assert len(result.data["explanations"]) >= 1

    def test_explain_file(self, tmp_path):
        f = tmp_path / "service.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")

        registry = ToolRegistry(tmp_path)
        result = registry.invoke("explain_file", file_path=str(f))
        assert result.success is True
        assert len(result.data["symbols"]) >= 1

    def test_summarize_repo(self, tmp_path):
        f = tmp_path / "service.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")

        registry = ToolRegistry(tmp_path)
        registry.index_file(str(f))

        result = registry.invoke("summarize_repo")
        assert result.success is True
        assert "total_files" in result.data

    def test_find_references(self, tmp_path):
        f = tmp_path / "service.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")

        registry = ToolRegistry(tmp_path)
        registry.index_file(str(f))

        result = registry.invoke("find_references", symbol_name="greet")
        assert result.success is True
        assert result.data["reference_count"] >= 1

    def test_get_dependencies(self, tmp_path):
        f = tmp_path / "service.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")

        registry = ToolRegistry(tmp_path)
        result = registry.invoke("get_dependencies", file_path=str(f))
        assert result.success is True

    def test_get_call_graph(self, tmp_path):
        f = tmp_path / "service.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")

        registry = ToolRegistry(tmp_path)
        registry.index_file(str(f))

        result = registry.invoke("get_call_graph", symbol_name="greet")
        assert result.success is True
        assert "callers" in result.data
        assert "callees" in result.data

    def test_get_context_found(self, tmp_path):
        f = tmp_path / "service.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")

        registry = ToolRegistry(tmp_path)
        registry.index_file(str(f))

        result = registry.invoke("get_context", symbol_name="Service")
        assert result.success is True

    def test_get_context_not_found(self, tmp_path):
        registry = ToolRegistry(tmp_path)
        result = registry.invoke("get_context", symbol_name="Missing")
        assert result.success is False

    def test_index_directory(self, tmp_path):
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".codex" / "config.json").write_text("{}", encoding="utf-8")
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("y = 2\n", encoding="utf-8")

        registry = ToolRegistry(tmp_path)
        count = registry.index_directory()
        assert count >= 2
