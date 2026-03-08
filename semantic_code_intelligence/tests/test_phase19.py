"""Tests for Phase 19 — AI Agent Tooling Protocol.

Covers: tool protocol dataclasses (ToolInvocation, ToolExecutionResult,
ToolError, ToolErrorCode), ToolExecutor engine (validation, routing,
plugin tools, batch execution), bridge extensions (INVOKE_TOOL, LIST_TOOLS,
/tools/invoke, /tools/list, /tools/stream), CLI `tool` command (list, run,
schema), plugin hooks (REGISTER_TOOL, PRE_TOOL_INVOKE, POST_TOOL_INVOKE),
capability manifest (tools field), docs generation (AI_TOOL_PROTOCOL.md),
router (31 commands), version (0.19.0), and safety guardrails.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from click.testing import CliRunner


# =========================================================================
# Test helpers
# =========================================================================


def _write_sample_project(root: Path) -> None:
    """Write a small project for tool testing."""
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)

    (src / "core.py").write_text(
        "def helper():\n"
        "    return 42\n"
        "\n"
        "def compute(x):\n"
        "    return helper() + x\n",
        encoding="utf-8",
    )

    (src / "api.py").write_text(
        "from src.core import compute\n"
        "\n"
        "def handle_request(data):\n"
        "    return compute(data)\n",
        encoding="utf-8",
    )


# =========================================================================
# ToolInvocation dataclass tests
# =========================================================================


class TestToolInvocation:
    """Tests for ToolInvocation dataclass."""

    def test_basic_creation(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        inv = ToolInvocation(tool_name="semantic_search", arguments={"query": "parse"})
        assert inv.tool_name == "semantic_search"
        assert inv.arguments == {"query": "parse"}
        assert inv.request_id  # auto-generated
        assert inv.timestamp > 0

    def test_auto_request_id(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        inv = ToolInvocation(tool_name="test")
        assert len(inv.request_id) == 12

    def test_custom_request_id(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        inv = ToolInvocation(tool_name="test", request_id="custom-123")
        assert inv.request_id == "custom-123"

    def test_to_dict(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        inv = ToolInvocation(
            tool_name="explain_symbol",
            arguments={"symbol_name": "Foo"},
            request_id="r1",
        )
        d = inv.to_dict()
        assert d["tool_name"] == "explain_symbol"
        assert d["arguments"] == {"symbol_name": "Foo"}
        assert d["request_id"] == "r1"
        assert "timestamp" in d

    def test_to_json(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        inv = ToolInvocation(tool_name="test", request_id="r1")
        j = inv.to_json()
        parsed = json.loads(j)
        assert parsed["tool_name"] == "test"

    def test_from_dict(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        data = {
            "tool_name": "get_context",
            "arguments": {"symbol_name": "Bar"},
            "request_id": "abc",
            "timestamp": 1234567890.0,
        }
        inv = ToolInvocation.from_dict(data)
        assert inv.tool_name == "get_context"
        assert inv.arguments["symbol_name"] == "Bar"
        assert inv.request_id == "abc"
        assert inv.timestamp == 1234567890.0

    def test_from_json(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        j = '{"tool_name": "test", "arguments": {}, "request_id": "x", "timestamp": 0}'
        inv = ToolInvocation.from_json(j)
        assert inv.tool_name == "test"

    def test_roundtrip(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        original = ToolInvocation(tool_name="find_references", arguments={"symbol_name": "X"})
        restored = ToolInvocation.from_dict(original.to_dict())
        assert restored.tool_name == original.tool_name
        assert restored.arguments == original.arguments
        assert restored.request_id == original.request_id

    def test_empty_arguments(self):
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        inv = ToolInvocation(tool_name="summarize_repo")
        assert inv.arguments == {}


# =========================================================================
# ToolError dataclass tests
# =========================================================================


class TestToolError:
    """Tests for ToolError dataclass."""

    def test_basic_creation(self):
        from semantic_code_intelligence.tools.protocol import ToolError

        err = ToolError(
            tool_name="bad_tool",
            error_code="unknown_tool",
            error_message="Tool not found",
            request_id="r1",
        )
        assert err.tool_name == "bad_tool"
        assert err.error_code == "unknown_tool"
        assert err.error_message == "Tool not found"

    def test_to_dict(self):
        from semantic_code_intelligence.tools.protocol import ToolError

        err = ToolError(tool_name="t", error_code="e", error_message="m", request_id="r")
        d = err.to_dict()
        assert d["tool_name"] == "t"
        assert d["error_code"] == "e"
        assert d["error_message"] == "m"
        assert d["request_id"] == "r"

    def test_to_json(self):
        from semantic_code_intelligence.tools.protocol import ToolError

        err = ToolError(tool_name="t", error_code="e", error_message="m")
        j = err.to_json()
        parsed = json.loads(j)
        assert parsed["error_code"] == "e"

    def test_from_dict(self):
        from semantic_code_intelligence.tools.protocol import ToolError

        data = {"tool_name": "a", "error_code": "b", "error_message": "c", "request_id": "d"}
        err = ToolError.from_dict(data)
        assert err.tool_name == "a"
        assert err.error_code == "b"


# =========================================================================
# ToolErrorCode enum tests
# =========================================================================


class TestToolErrorCode:
    """Tests for ToolErrorCode enum."""

    def test_all_codes_exist(self):
        from semantic_code_intelligence.tools.protocol import ToolErrorCode

        expected = {"unknown_tool", "invalid_arguments", "missing_required_arg",
                    "execution_error", "timeout", "permission_denied"}
        actual = {c.value for c in ToolErrorCode}
        assert expected == actual

    def test_string_values(self):
        from semantic_code_intelligence.tools.protocol import ToolErrorCode

        assert ToolErrorCode.UNKNOWN_TOOL == "unknown_tool"
        assert ToolErrorCode.EXECUTION_ERROR == "execution_error"

    def test_is_str_enum(self):
        from semantic_code_intelligence.tools.protocol import ToolErrorCode

        assert isinstance(ToolErrorCode.TIMEOUT, str)


# =========================================================================
# ToolExecutionResult dataclass tests
# =========================================================================


class TestToolExecutionResult:
    """Tests for ToolExecutionResult dataclass."""

    def test_success_result(self):
        from semantic_code_intelligence.tools.protocol import ToolExecutionResult

        r = ToolExecutionResult(
            tool_name="semantic_search",
            request_id="r1",
            success=True,
            result_payload={"results": [1, 2, 3]},
            execution_time_ms=42.5,
        )
        assert r.success is True
        assert r.result_payload == {"results": [1, 2, 3]}

    def test_failure_result(self):
        from semantic_code_intelligence.tools.protocol import ToolError, ToolExecutionResult

        err = ToolError(tool_name="t", error_code="execution_error", error_message="boom")
        r = ToolExecutionResult(
            tool_name="t",
            success=False,
            error=err,
        )
        assert r.success is False
        assert r.error is not None
        assert r.error.error_message == "boom"

    def test_to_dict_success(self):
        from semantic_code_intelligence.tools.protocol import ToolExecutionResult

        r = ToolExecutionResult(
            tool_name="test", request_id="r1", success=True,
            result_payload={"data": 42}, execution_time_ms=10.0,
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["result_payload"]["data"] == 42
        assert "error" not in d

    def test_to_dict_failure(self):
        from semantic_code_intelligence.tools.protocol import ToolError, ToolExecutionResult

        err = ToolError(tool_name="t", error_code="x", error_message="y")
        r = ToolExecutionResult(tool_name="t", success=False, error=err)
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"]["error_code"] == "x"
        assert "result_payload" not in d

    def test_to_json(self):
        from semantic_code_intelligence.tools.protocol import ToolExecutionResult

        r = ToolExecutionResult(tool_name="t", success=True, result_payload={"k": "v"})
        j = r.to_json(indent=2)
        parsed = json.loads(j)
        assert parsed["success"] is True

    def test_from_dict_success(self):
        from semantic_code_intelligence.tools.protocol import ToolExecutionResult

        data = {
            "tool_name": "t",
            "request_id": "r1",
            "success": True,
            "result_payload": {"v": 1},
            "execution_time_ms": 5.0,
            "timestamp": 100.0,
        }
        r = ToolExecutionResult.from_dict(data)
        assert r.tool_name == "t"
        assert r.success is True
        assert r.result_payload == {"v": 1}

    def test_from_dict_failure(self):
        from semantic_code_intelligence.tools.protocol import ToolExecutionResult

        data = {
            "tool_name": "t",
            "success": False,
            "error": {"tool_name": "t", "error_code": "c", "error_message": "m", "request_id": ""},
        }
        r = ToolExecutionResult.from_dict(data)
        assert r.success is False
        assert r.error is not None
        assert r.error.error_code == "c"

    def test_auto_timestamp(self):
        from semantic_code_intelligence.tools.protocol import ToolExecutionResult

        before = time.time()
        r = ToolExecutionResult(tool_name="t")
        after = time.time()
        assert before <= r.timestamp <= after

    def test_roundtrip(self):
        from semantic_code_intelligence.tools.protocol import ToolExecutionResult

        original = ToolExecutionResult(
            tool_name="test", request_id="abc", success=True,
            result_payload={"x": [1, 2]}, execution_time_ms=3.14,
        )
        restored = ToolExecutionResult.from_dict(original.to_dict())
        assert restored.tool_name == original.tool_name
        assert restored.success == original.success
        assert restored.result_payload == original.result_payload


# =========================================================================
# ToolExecutor engine tests
# =========================================================================


class TestToolExecutor:
    """Tests for the ToolExecutor engine."""

    def test_creation(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        assert executor is not None

    def test_available_tools_includes_builtins(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        names = executor.list_tool_names()
        assert "semantic_search" in names
        assert "explain_symbol" in names
        assert "summarize_repo" in names
        assert len(names) >= 8

    def test_get_tool_schema(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        schema = executor.get_tool_schema("semantic_search")
        assert schema is not None
        assert schema["name"] == "semantic_search"
        assert "parameters" in schema

    def test_get_tool_schema_unknown(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        assert executor.get_tool_schema("nonexistent") is None

    def test_execute_unknown_tool(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        executor = ToolExecutor(tmp_path)
        inv = ToolInvocation(tool_name="nonexistent_tool", arguments={})
        result = executor.execute(inv)
        assert result.success is False
        assert result.error is not None
        assert result.error.error_code == "unknown_tool"

    def test_execute_missing_required_arg(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        executor = ToolExecutor(tmp_path)
        inv = ToolInvocation(tool_name="semantic_search", arguments={})
        result = executor.execute(inv)
        assert result.success is False
        assert result.error is not None
        assert result.error.error_code == "missing_required_arg"

    def test_execute_summarize_repo(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        _write_sample_project(tmp_path)
        executor = ToolExecutor(tmp_path)
        inv = ToolInvocation(tool_name="summarize_repo", arguments={})
        result = executor.execute(inv)
        assert result.success is True
        assert result.execution_time_ms >= 0
        assert result.tool_name == "summarize_repo"

    def test_execute_has_timing(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        executor = ToolExecutor(tmp_path)
        inv = ToolInvocation(tool_name="summarize_repo", arguments={})
        result = executor.execute(inv)
        assert result.execution_time_ms >= 0

    def test_execute_preserves_request_id(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        executor = ToolExecutor(tmp_path)
        inv = ToolInvocation(tool_name="summarize_repo", arguments={}, request_id="my-id-123")
        result = executor.execute(inv)
        assert result.request_id == "my-id-123"

    def test_execute_batch(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        executor = ToolExecutor(tmp_path)
        invocations = [
            ToolInvocation(tool_name="summarize_repo", arguments={}),
            ToolInvocation(tool_name="nonexistent", arguments={}),
        ]
        results = executor.execute_batch(invocations)
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False

    def test_registry_access(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        assert executor.registry is not None


# =========================================================================
# Plugin tool registration tests
# =========================================================================


class TestPluginToolRegistration:
    """Tests for plugin-registered tools in the ToolExecutor."""

    def test_register_plugin_tool(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        executor.register_plugin_tool(
            name="my_custom_tool",
            description="A test plugin tool",
            parameters={"input": {"type": "string", "required": True}},
            handler=lambda input: {"echo": input},
        )
        assert "my_custom_tool" in executor.list_tool_names()

    def test_plugin_tool_schema(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        executor.register_plugin_tool(
            name="plugin_tool",
            description="Plugin tool",
            parameters={},
            handler=lambda: {"ok": True},
        )
        schema = executor.get_tool_schema("plugin_tool")
        assert schema is not None
        assert schema["source"] == "plugin"

    def test_execute_plugin_tool(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        executor = ToolExecutor(tmp_path)
        executor.register_plugin_tool(
            name="echo_tool",
            description="Echoes input",
            parameters={"msg": {"type": "string", "required": True}},
            handler=lambda msg: {"echoed": msg},
        )
        inv = ToolInvocation(tool_name="echo_tool", arguments={"msg": "hello"})
        result = executor.execute(inv)
        assert result.success is True
        assert result.result_payload["echoed"] == "hello"

    def test_plugin_tool_cannot_override_builtin(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        with pytest.raises(ValueError, match="collides with built-in"):
            executor.register_plugin_tool(
                name="semantic_search",
                description="override",
                parameters={},
                handler=lambda: {},
            )

    def test_unregister_plugin_tool(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        executor.register_plugin_tool(
            name="temp_tool",
            description="Temporary",
            parameters={},
            handler=lambda: {},
        )
        assert "temp_tool" in executor.list_tool_names()
        assert executor.unregister_plugin_tool("temp_tool") is True
        assert "temp_tool" not in executor.list_tool_names()

    def test_unregister_nonexistent(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        assert executor.unregister_plugin_tool("nonexistent") is False

    def test_plugin_tool_error_handling(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        def bad_handler(**kwargs):
            raise RuntimeError("Plugin tool failure")

        executor = ToolExecutor(tmp_path)
        executor.register_plugin_tool(
            name="bad_tool",
            description="Fails",
            parameters={},
            handler=bad_handler,
        )
        inv = ToolInvocation(tool_name="bad_tool", arguments={})
        result = executor.execute(inv)
        assert result.success is False
        assert result.error is not None
        assert "Plugin tool failure" in result.error.error_message


# =========================================================================
# Bridge protocol extension tests
# =========================================================================


class TestBridgeProtocolExtensions:
    """Tests for Phase 19 bridge protocol additions."""

    def test_request_kind_invoke_tool(self):
        from semantic_code_intelligence.bridge.protocol import RequestKind

        assert RequestKind.INVOKE_TOOL == "invoke_tool"

    def test_request_kind_list_tools(self):
        from semantic_code_intelligence.bridge.protocol import RequestKind

        assert RequestKind.LIST_TOOLS == "list_tools"

    def test_capabilities_include_new_kinds(self):
        from semantic_code_intelligence.bridge.protocol import BridgeCapabilities

        caps = BridgeCapabilities()
        assert "invoke_tool" in caps.supported_requests
        assert "list_tools" in caps.supported_requests

    def test_capabilities_tools_field(self):
        from semantic_code_intelligence.bridge.protocol import BridgeCapabilities

        caps = BridgeCapabilities(tools=[{"name": "test_tool"}])
        d = caps.to_dict()
        assert "tools" in d
        assert d["tools"] == [{"name": "test_tool"}]

    def test_capabilities_no_tools_field_when_empty(self):
        from semantic_code_intelligence.bridge.protocol import BridgeCapabilities

        caps = BridgeCapabilities()
        d = caps.to_dict()
        assert "tools" not in d

    def test_request_kind_count(self):
        from semantic_code_intelligence.bridge.protocol import RequestKind

        # 10 original + 2 new (INVOKE_TOOL, LIST_TOOLS) = 12
        assert len(RequestKind) == 12


# =========================================================================
# Bridge server tool endpoint tests
# =========================================================================


class TestBridgeServerToolEndpoints:
    """Tests for the bridge server's tool-related endpoints."""

    def test_dispatch_list_tools(self, tmp_path):
        from semantic_code_intelligence.bridge.server import BridgeServer
        from semantic_code_intelligence.bridge.protocol import AgentRequest

        server = BridgeServer(tmp_path)
        req = AgentRequest(kind="list_tools", params={}, request_id="t1")
        resp = server.dispatch(req)
        assert resp.success is True
        assert "tools" in resp.data
        assert resp.data["count"] >= 8

    def test_dispatch_invoke_tool(self, tmp_path):
        from semantic_code_intelligence.bridge.server import BridgeServer
        from semantic_code_intelligence.bridge.protocol import AgentRequest

        server = BridgeServer(tmp_path)
        req = AgentRequest(
            kind="invoke_tool",
            params={"tool_name": "summarize_repo", "arguments": {}},
            request_id="t2",
        )
        resp = server.dispatch(req)
        assert resp.success is True

    def test_dispatch_invoke_unknown_tool(self, tmp_path):
        from semantic_code_intelligence.bridge.server import BridgeServer
        from semantic_code_intelligence.bridge.protocol import AgentRequest

        server = BridgeServer(tmp_path)
        req = AgentRequest(
            kind="invoke_tool",
            params={"tool_name": "fake_tool", "arguments": {}},
            request_id="t3",
        )
        resp = server.dispatch(req)
        assert resp.success is False

    def test_server_has_executor(self, tmp_path):
        from semantic_code_intelligence.bridge.server import BridgeServer

        server = BridgeServer(tmp_path)
        assert server._executor is not None

    def test_capabilities_include_tools(self, tmp_path):
        from semantic_code_intelligence.bridge.server import BridgeServer

        server = BridgeServer(tmp_path)
        caps = server._capabilities
        assert len(caps.tools) >= 8


# =========================================================================
# Plugin hooks tests
# =========================================================================


class TestPluginHooksPhase19:
    """Tests for Phase 19 plugin hooks."""

    def test_register_tool_hook_exists(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "REGISTER_TOOL")
        assert PluginHook.REGISTER_TOOL == "register_tool"

    def test_pre_tool_invoke_hook_exists(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "PRE_TOOL_INVOKE")
        assert PluginHook.PRE_TOOL_INVOKE == "pre_tool_invoke"

    def test_post_tool_invoke_hook_exists(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "POST_TOOL_INVOKE")
        assert PluginHook.POST_TOOL_INVOKE == "post_tool_invoke"

    def test_plugin_hook_count(self):
        from semantic_code_intelligence.plugins import PluginHook

        # 19 original + 3 new (REGISTER_TOOL, PRE_TOOL_INVOKE, POST_TOOL_INVOKE) = 22
        assert len(PluginHook) == 22


# =========================================================================
# CLI tool command tests
# =========================================================================


class TestCLIToolCommand:
    """Tests for the `codex tool` CLI command group."""

    def test_tool_group_exists(self):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        assert tool_cmd.name == "tool"

    def test_tool_list_subcommand(self):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "tools" in data
        assert data["count"] >= 8

    def test_tool_list_text_output(self):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, ["list"])
        assert result.exit_code == 0
        assert "semantic_search" in result.output

    def test_tool_run_subcommand(self, tmp_path):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, [
            "run", "summarize_repo",
            "--path", str(tmp_path),
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["tool_name"] == "summarize_repo"

    def test_tool_run_with_args(self, tmp_path):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(tool_cmd, [
            "run", "semantic_search",
            "--arg", "query=helper",
            "--path", str(tmp_path),
            "--json",
        ])
        assert result.exit_code == 0

    def test_tool_run_unknown_tool(self, tmp_path):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, [
            "run", "nonexistent_tool",
            "--path", str(tmp_path),
            "--json",
        ])
        assert result.exit_code == 0  # exits cleanly with error in JSON
        data = json.loads(result.output)
        assert data["success"] is False

    def test_tool_run_invalid_arg_format(self, tmp_path):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, [
            "run", "semantic_search",
            "--arg", "no_equals_sign",
            "--path", str(tmp_path),
        ])
        # Should show error about invalid format
        assert result.exit_code != 0 or "Invalid argument" in result.output

    def test_tool_schema_subcommand(self):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, ["schema", "semantic_search", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "semantic_search"

    def test_tool_schema_text_output(self):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, ["schema", "explain_symbol"])
        assert result.exit_code == 0
        assert "explain_symbol" in result.output

    def test_tool_schema_unknown(self):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, ["schema", "nonexistent"])
        assert result.exit_code == 0
        assert "Unknown tool" in result.output

    def test_tool_run_pipe_mode(self, tmp_path):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd

        runner = CliRunner()
        result = runner.invoke(tool_cmd, [
            "run", "summarize_repo",
            "--path", str(tmp_path),
            "--pipe",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "tool_name" in data


# =========================================================================
# Router registration tests
# =========================================================================


class TestRouterPhase19:
    """Tests for router command registration."""

    def test_command_count_31(self):
        from semantic_code_intelligence.cli.main import cli

        assert len(cli.commands) == 31

    def test_tool_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "tool" in cli.commands


# =========================================================================
# Version tests
# =========================================================================


class TestVersionPhase19:
    """Tests for version 0.19.0."""

    def test_version_string(self):
        from semantic_code_intelligence import __version__

        assert __version__ == "0.19.0"

    def test_pyproject_version(self):
        import tomllib
        pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            assert data["project"]["version"] == "0.19.0"


# =========================================================================
# Documentation generation tests
# =========================================================================


class TestDocGenerationPhase19:
    """Tests for AI_TOOL_PROTOCOL.md documentation generation."""

    def test_generate_ai_tool_protocol_reference(self):
        from semantic_code_intelligence.docs import generate_ai_tool_protocol_reference

        md = generate_ai_tool_protocol_reference()
        assert "# AI Tool Protocol Reference" in md
        assert "ToolInvocation" in md
        assert "ToolExecutionResult" in md
        assert "ToolError" in md

    def test_protocol_reference_lists_tools(self):
        from semantic_code_intelligence.docs import generate_ai_tool_protocol_reference

        md = generate_ai_tool_protocol_reference()
        assert "semantic_search" in md
        assert "explain_symbol" in md

    def test_protocol_reference_lists_endpoints(self):
        from semantic_code_intelligence.docs import generate_ai_tool_protocol_reference

        md = generate_ai_tool_protocol_reference()
        assert "/tools/invoke" in md
        assert "/tools/list" in md
        assert "/tools/stream" in md

    def test_protocol_reference_lists_error_codes(self):
        from semantic_code_intelligence.docs import generate_ai_tool_protocol_reference

        md = generate_ai_tool_protocol_reference()
        assert "unknown_tool" in md
        assert "missing_required_arg" in md

    def test_protocol_reference_cli_usage(self):
        from semantic_code_intelligence.docs import generate_ai_tool_protocol_reference

        md = generate_ai_tool_protocol_reference()
        assert "codex tool list" in md
        assert "codex tool run" in md

    def test_generate_all_docs_includes_protocol(self, tmp_path):
        from semantic_code_intelligence.docs import generate_all_docs

        generated = generate_all_docs(tmp_path)
        assert "AI_TOOL_PROTOCOL.md" in generated
        content = (tmp_path / "AI_TOOL_PROTOCOL.md").read_text(encoding="utf-8")
        assert "AI Tool Protocol" in content

    def test_docs_count(self, tmp_path):
        from semantic_code_intelligence.docs import generate_all_docs

        generated = generate_all_docs(tmp_path)
        # Should be 10 (9 previous + AI_TOOL_PROTOCOL.md)
        assert len(generated) >= 10


# =========================================================================
# Safety guardrails tests
# =========================================================================


class TestSafetyGuardrails:
    """Tests for AI safety guardrails in the tooling protocol."""

    def test_tools_are_readonly(self):
        """Verify no tool definition enables code execution."""
        from semantic_code_intelligence.tools import TOOL_DEFINITIONS

        for tool in TOOL_DEFINITIONS:
            name = tool["name"]
            assert "exec" not in name.lower(), f"Tool {name} may execute code"
            assert "run" not in name.lower() or name == "summarize_repo", f"Tool {name} may run code"

    def test_unknown_tool_rejected(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        executor = ToolExecutor(tmp_path)
        inv = ToolInvocation(tool_name="__import__", arguments={})
        result = executor.execute(inv)
        assert result.success is False

    def test_plugin_cannot_override_builtin(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor

        executor = ToolExecutor(tmp_path)
        with pytest.raises(ValueError):
            executor.register_plugin_tool(
                name="get_context",
                description="override",
                parameters={},
                handler=lambda: {},
            )

    def test_argument_validation_enforced(self, tmp_path):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        from semantic_code_intelligence.tools.protocol import ToolInvocation

        executor = ToolExecutor(tmp_path)
        # find_references requires symbol_name
        inv = ToolInvocation(tool_name="find_references", arguments={})
        result = executor.execute(inv)
        assert result.success is False
        assert result.error.error_code == "missing_required_arg"


# =========================================================================
# Module structure tests
# =========================================================================


class TestModuleStructure:
    """Tests for Phase 19 module structure."""

    def test_tools_protocol_importable(self):
        from semantic_code_intelligence.tools.protocol import (
            ToolError,
            ToolErrorCode,
            ToolExecutionResult,
            ToolInvocation,
        )
        assert ToolInvocation is not None
        assert ToolExecutionResult is not None
        assert ToolError is not None
        assert ToolErrorCode is not None

    def test_tools_executor_importable(self):
        from semantic_code_intelligence.tools.executor import ToolExecutor
        assert ToolExecutor is not None

    def test_tool_cmd_importable(self):
        from semantic_code_intelligence.cli.commands.tool_cmd import tool_cmd
        assert tool_cmd is not None

    def test_docs_function_importable(self):
        from semantic_code_intelligence.docs import generate_ai_tool_protocol_reference
        assert callable(generate_ai_tool_protocol_reference)
