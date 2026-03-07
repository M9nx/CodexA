"""Tests for Phase 9 — External AI Cooperation Layer.

Covers: bridge protocol, context provider, HTTP bridge server, VSCode
extension bridge, and CLI commands (serve, context).
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# =========================================================================
# Protocol tests
# =========================================================================

from semantic_code_intelligence.bridge.protocol import (
    AgentRequest,
    AgentResponse,
    BridgeCapabilities,
    RequestKind,
)


class TestRequestKind:
    def test_all_values(self):
        kinds = [k.value for k in RequestKind]
        assert "semantic_search" in kinds
        assert "explain_symbol" in kinds
        assert "explain_file" in kinds
        assert "get_context" in kinds
        assert "get_dependencies" in kinds
        assert "get_call_graph" in kinds
        assert "summarize_repo" in kinds
        assert "find_references" in kinds
        assert "validate_code" in kinds
        assert "list_capabilities" in kinds

    def test_count(self):
        assert len(RequestKind) == 10

    def test_string_enum(self):
        assert RequestKind.SEMANTIC_SEARCH == "semantic_search"
        assert isinstance(RequestKind.SEMANTIC_SEARCH, str)


class TestAgentRequest:
    def test_create(self):
        req = AgentRequest(kind="semantic_search", params={"query": "auth"})
        assert req.kind == "semantic_search"
        assert req.params["query"] == "auth"
        assert req.request_id == ""
        assert req.source == ""

    def test_to_dict(self):
        req = AgentRequest(
            kind="explain_symbol",
            params={"symbol_name": "foo"},
            request_id="r1",
            source="copilot",
        )
        d = req.to_dict()
        assert d["kind"] == "explain_symbol"
        assert d["params"]["symbol_name"] == "foo"
        assert d["request_id"] == "r1"
        assert d["source"] == "copilot"

    def test_to_json(self):
        req = AgentRequest(kind="validate_code", params={"code": "print(1)"})
        j = req.to_json()
        parsed = json.loads(j)
        assert parsed["kind"] == "validate_code"

    def test_from_dict(self):
        d = {"kind": "semantic_search", "params": {"query": "hello"}, "request_id": "x"}
        req = AgentRequest.from_dict(d)
        assert req.kind == "semantic_search"
        assert req.params["query"] == "hello"
        assert req.request_id == "x"

    def test_from_json(self):
        j = json.dumps({"kind": "explain_file", "params": {"file_path": "a.py"}})
        req = AgentRequest.from_json(j)
        assert req.kind == "explain_file"
        assert req.params["file_path"] == "a.py"

    def test_from_dict_defaults(self):
        d = {"kind": "list_capabilities"}
        req = AgentRequest.from_dict(d)
        assert req.params == {}
        assert req.request_id == ""
        assert req.source == ""

    def test_roundtrip(self):
        original = AgentRequest(
            kind="get_dependencies",
            params={"file_path": "src/main.py"},
            request_id="abc-123",
            source="cursor",
        )
        rebuilt = AgentRequest.from_json(original.to_json())
        assert rebuilt.kind == original.kind
        assert rebuilt.params == original.params
        assert rebuilt.request_id == original.request_id
        assert rebuilt.source == original.source


class TestAgentResponse:
    def test_success(self):
        resp = AgentResponse(success=True, data={"count": 5})
        assert resp.success is True
        d = resp.to_dict()
        assert "data" in d
        assert "error" not in d

    def test_failure(self):
        resp = AgentResponse(success=False, error="not found")
        d = resp.to_dict()
        assert d["success"] is False
        assert "error" in d
        assert "data" not in d

    def test_elapsed(self):
        resp = AgentResponse(success=True, data={}, elapsed_ms=12.345)
        d = resp.to_dict()
        assert d["elapsed_ms"] == 12.35

    def test_to_json(self):
        resp = AgentResponse(success=True, data={"key": "val"}, request_id="r1")
        parsed = json.loads(resp.to_json())
        assert parsed["success"] is True
        assert parsed["request_id"] == "r1"

    def test_to_json_indented(self):
        resp = AgentResponse(success=True, data={})
        text = resp.to_json(indent=2)
        assert "\n" in text


class TestBridgeCapabilities:
    def test_defaults(self):
        cap = BridgeCapabilities()
        assert cap.version == "0.9.0"
        assert cap.name == "CodexA Bridge"
        assert "semantic_search" in cap.supported_requests
        assert len(cap.supported_requests) == 10

    def test_to_dict(self):
        cap = BridgeCapabilities()
        d = cap.to_dict()
        assert d["version"] == "0.9.0"
        assert isinstance(d["supported_requests"], list)

    def test_to_json(self):
        cap = BridgeCapabilities()
        parsed = json.loads(cap.to_json())
        assert parsed["name"] == "CodexA Bridge"


# =========================================================================
# ContextProvider tests (with mocked subsystems)
# =========================================================================

from semantic_code_intelligence.bridge.context_provider import ContextProvider


class TestContextProvider:
    @pytest.fixture
    def provider(self, tmp_path: Path) -> ContextProvider:
        return ContextProvider(tmp_path)

    def test_init(self, provider: ContextProvider):
        assert provider._indexed is False
        assert provider._builder is None
        assert provider._validator is not None

    def test_validate_code_safe(self, provider: ContextProvider):
        report = provider.validate_code("x = 1 + 2")
        assert isinstance(report, dict)
        assert "safe" in report

    def test_validate_code_unsafe(self, provider: ContextProvider):
        report = provider.validate_code("eval(input())")
        assert isinstance(report, dict)
        # Should flag the eval
        assert report.get("is_safe") is False or len(report.get("issues", [])) > 0

    @patch("semantic_code_intelligence.bridge.context_provider.search_codebase")
    def test_context_for_query_empty(self, mock_search, provider):
        mock_search.return_value = []
        result = provider.context_for_query(query="test")
        assert result["query"] == "test"
        assert result["snippet_count"] == 0

    @patch("semantic_code_intelligence.bridge.context_provider.search_codebase")
    def test_context_for_query_with_results(self, mock_search, provider):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"file": "a.py", "score": 0.9}
        mock_search.return_value = [mock_result]
        result = provider.context_for_query(query="auth")
        assert result["snippet_count"] == 1
        assert result["snippets"][0]["file"] == "a.py"

    @patch("semantic_code_intelligence.bridge.context_provider.search_codebase")
    def test_context_for_query_exception(self, mock_search, provider):
        mock_search.side_effect = Exception("oops")
        result = provider.context_for_query(query="fail")
        assert result["snippet_count"] == 0

    def test_context_for_symbol_not_found(self, provider):
        """Symbol not found returns found=False."""
        with patch.object(provider, "_ensure_indexed") as mock_idx:
            mock_builder = MagicMock()
            mock_builder.find_symbol.return_value = []
            mock_idx.return_value = mock_builder
            result = provider.context_for_symbol("nonexistent")
            assert result["found"] is False

    def test_context_for_repo(self, provider):
        """Repo summary delegates to summarize_repository."""
        with patch.object(provider, "_ensure_indexed") as mock_idx:
            mock_builder = MagicMock()
            mock_idx.return_value = mock_builder
            with patch(
                "semantic_code_intelligence.bridge.context_provider.summarize_repository"
            ) as mock_sum:
                mock_summary = MagicMock()
                mock_summary.to_dict.return_value = {"total_files": 10}
                mock_sum.return_value = mock_summary
                result = provider.context_for_repo()
                assert result["total_files"] == 10

    def test_get_dependencies(self, provider):
        """get_dependencies returns dict with expected keys."""
        with patch.object(provider, "_ensure_indexed") as mock_idx:
            mock_builder = MagicMock()
            mock_builder._file_contents = {}
            mock_idx.return_value = mock_builder
            result = provider.get_dependencies("missing.py")
            assert "file_path" in result
            assert "dependencies" in result

    def test_get_call_graph(self, provider):
        """get_call_graph returns expected structure."""
        with patch.object(provider, "_ensure_indexed") as mock_idx:
            mock_builder = MagicMock()
            mock_builder.get_all_symbols.return_value = []
            mock_idx.return_value = mock_builder
            result = provider.get_call_graph("some_func")
            assert result["symbol_name"] == "some_func"
            assert "callers" in result
            assert "callees" in result

    def test_find_references(self, provider):
        """find_references returns expected structure."""
        with patch.object(provider, "_ensure_indexed") as mock_idx:
            mock_builder = MagicMock()
            mock_builder.get_all_symbols.return_value = []
            mock_idx.return_value = mock_builder
            result = provider.find_references("some_func")
            assert result["symbol_name"] == "some_func"
            assert result["reference_count"] == 0


# =========================================================================
# BridgeServer tests
# =========================================================================

from semantic_code_intelligence.bridge.server import BridgeServer, _dispatch


class TestDispatch:
    """Direct dispatch (no HTTP round-trip)."""

    @pytest.fixture
    def provider(self, tmp_path: Path):
        return ContextProvider(tmp_path)

    @pytest.fixture
    def caps(self):
        return BridgeCapabilities()

    def test_list_capabilities(self, provider, caps):
        req = AgentRequest(kind=RequestKind.LIST_CAPABILITIES)
        resp = _dispatch(req, provider, caps)
        assert resp.success is True
        assert "supported_requests" in resp.data

    def test_validate_code(self, provider, caps):
        req = AgentRequest(
            kind=RequestKind.VALIDATE_CODE,
            params={"code": "x = 1"},
        )
        resp = _dispatch(req, provider, caps)
        assert resp.success is True
        assert "safe" in resp.data

    @patch("semantic_code_intelligence.bridge.context_provider.search_codebase")
    def test_semantic_search(self, mock_search, provider, caps):
        mock_search.return_value = []
        req = AgentRequest(
            kind=RequestKind.SEMANTIC_SEARCH,
            params={"query": "test"},
        )
        resp = _dispatch(req, provider, caps)
        assert resp.success is True
        assert resp.data["query"] == "test"

    def test_unknown_kind(self, provider, caps):
        req = AgentRequest(kind="totally_unknown")
        resp = _dispatch(req, provider, caps)
        assert resp.success is False
        assert "Unknown" in resp.error


class TestBridgeServer:
    """BridgeServer lifecycle and direct dispatch."""

    def test_init(self, tmp_path: Path):
        server = BridgeServer(tmp_path)
        assert server.url == "http://127.0.0.1:24842"

    def test_custom_host_port(self, tmp_path: Path):
        server = BridgeServer(tmp_path, host="0.0.0.0", port=9999)
        assert server.url == "http://0.0.0.0:9999"

    def test_direct_dispatch(self, tmp_path: Path):
        server = BridgeServer(tmp_path)
        req = AgentRequest(
            kind=RequestKind.LIST_CAPABILITIES,
            request_id="test-1",
        )
        resp = server.dispatch(req)
        assert resp.success is True
        assert resp.request_id == "test-1"
        assert resp.elapsed_ms >= 0

    def test_direct_dispatch_validate(self, tmp_path: Path):
        server = BridgeServer(tmp_path)
        req = AgentRequest(
            kind=RequestKind.VALIDATE_CODE,
            params={"code": "print('hello')"},
        )
        resp = server.dispatch(req)
        assert resp.success is True

    def test_background_start_stop(self, tmp_path: Path):
        """Start, query, and stop a background server."""
        server = BridgeServer(tmp_path, port=0)
        # port=0 will fail because HTTPServer needs a real port, pick a high one
        server = BridgeServer(tmp_path, port=39871)
        server.start_background()
        try:
            time.sleep(0.3)  # let the server thread start
            # Health check
            url = f"{server.url}/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                assert data["status"] == "ok"

            # Capabilities
            url2 = f"{server.url}/"
            req2 = urllib.request.Request(url2)
            with urllib.request.urlopen(req2, timeout=2) as resp2:
                data2 = json.loads(resp2.read())
                assert data2["name"] == "CodexA Bridge"

            # POST /request — list_capabilities
            post_data = json.dumps({
                "kind": "list_capabilities",
                "params": {},
                "request_id": "live-1",
            }).encode()
            req3 = urllib.request.Request(
                f"{server.url}/request",
                data=post_data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req3, timeout=2) as resp3:
                data3 = json.loads(resp3.read())
                assert data3["success"] is True
                assert data3["request_id"] == "live-1"
        finally:
            server.stop()

    def test_background_post_invalid_json(self, tmp_path: Path):
        server = BridgeServer(tmp_path, port=39872)
        server.start_background()
        try:
            time.sleep(0.3)
            post_data = b"this is not json"
            req = urllib.request.Request(
                f"{server.url}/request",
                data=post_data,
                headers={"Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(req, timeout=2)
                assert False, "Should have raised"
            except urllib.error.HTTPError as e:
                assert e.code == 400
        finally:
            server.stop()

    def test_background_404(self, tmp_path: Path):
        server = BridgeServer(tmp_path, port=39873)
        server.start_background()
        try:
            time.sleep(0.3)
            req = urllib.request.Request(f"{server.url}/nonexistent")
            try:
                urllib.request.urlopen(req, timeout=2)
                assert False, "Should have raised"
            except urllib.error.HTTPError as e:
                assert e.code == 404
        finally:
            server.stop()


# =========================================================================
# VSCodeBridge tests
# =========================================================================

from semantic_code_intelligence.bridge.vscode import (
    VSCodeBridge,
    generate_extension_manifest,
    _to_diagnostic,
    _to_hover,
    _to_completion_items,
)


class TestVSCodeHelpers:
    def test_to_diagnostic(self):
        issue = {"severity": "high", "description": "eval usage", "line": 5}
        d = _to_diagnostic(issue)
        assert d["severity"] == 1
        assert d["source"] == "CodexA"
        assert d["range"]["start"]["line"] == 5

    def test_to_diagnostic_default_severity(self):
        issue = {"description": "minor issue"}
        d = _to_diagnostic(issue)
        assert d["severity"] == 2  # medium default

    def test_to_hover_full(self):
        ctx = {
            "explanation": "Authenticates a user",
            "type": "function",
            "file": "auth.py",
            "callers": ["login", "signup", "reset"],
        }
        h = _to_hover(ctx)
        value = h["contents"]["value"]
        assert "Authenticates a user" in value
        assert "function" in value
        assert "auth.py" in value
        assert "login" in value

    def test_to_hover_empty(self):
        h = _to_hover({})
        assert h["contents"]["value"] == ""

    def test_to_completion_items(self):
        results = [
            {"symbol": "auth_check", "explanation": "checks auth", "snippet": "def auth_check():"},
            {"file": "utils.py"},
        ]
        items = _to_completion_items(results)
        assert len(items) == 2
        assert items[0]["label"] == "auth_check"
        assert items[1]["label"] == "utils.py"

    def test_to_completion_items_limit(self):
        results = [{"symbol": f"sym_{i}"} for i in range(30)]
        items = _to_completion_items(results)
        assert len(items) == 20  # capped at 20


class TestVSCodeBridge:
    @pytest.fixture
    def bridge(self, tmp_path: Path) -> VSCodeBridge:
        provider = ContextProvider(tmp_path)
        return VSCodeBridge(provider=provider)

    def test_diagnostics_safe(self, bridge):
        diags = bridge.diagnostics("x = 1")
        assert isinstance(diags, list)

    def test_diagnostics_unsafe(self, bridge):
        diags = bridge.diagnostics("eval(input())")
        assert len(diags) > 0
        assert diags[0]["source"] == "CodexA"

    @patch("semantic_code_intelligence.bridge.context_provider.search_codebase")
    def test_completions(self, mock_search, bridge):
        mock_search.return_value = []
        items = bridge.completions("auth")
        assert isinstance(items, list)

    def test_code_actions_safe(self, bridge):
        actions = bridge.code_actions("x = 1")
        assert isinstance(actions, list)

    def test_code_actions_unsafe(self, bridge):
        actions = bridge.code_actions("eval(input())")
        assert len(actions) > 0
        assert "CodexA" in actions[0]["title"]

    def test_hover_not_found(self, bridge):
        with patch.object(bridge.provider, "_ensure_indexed") as mock_idx:
            mock_builder = MagicMock()
            mock_builder.find_symbol.return_value = []
            mock_idx.return_value = mock_builder
            h = bridge.hover("nonexistent")
            # Should still return contents (possibly empty)
            assert "contents" in h


class TestExtensionManifest:
    def test_default_manifest(self):
        m = generate_extension_manifest()
        assert m["name"] == "codexa-bridge"
        assert m["version"] == "0.9.0"
        assert m["engines"]["vscode"] == "^1.85.0"
        assert len(m["contributes"]["commands"]) == 4

    def test_custom_port(self):
        m = generate_extension_manifest(server_port=8080)
        port_conf = m["contributes"]["configuration"]["properties"]["codexa.bridge.port"]
        assert port_conf["default"] == 8080

    def test_custom_name(self):
        m = generate_extension_manifest(extension_name="my-ext", display_name="My Ext")
        assert m["name"] == "my-ext"
        assert m["displayName"] == "My Ext"

    def test_json_serialisable(self):
        m = generate_extension_manifest()
        j = json.dumps(m)
        assert "codexa-bridge" in j


# =========================================================================
# CLI command tests (serve & context)
# =========================================================================

from click.testing import CliRunner


class TestServeCLI:
    def test_serve_help(self):
        from semantic_code_intelligence.cli.commands.serve_cmd import serve_cmd
        runner = CliRunner()
        result = runner.invoke(serve_cmd, ["--help"])
        assert result.exit_code == 0
        assert "bridge server" in result.output.lower()

    def test_serve_options(self):
        from semantic_code_intelligence.cli.commands.serve_cmd import serve_cmd
        runner = CliRunner()
        result = runner.invoke(serve_cmd, ["--help"])
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--path" in result.output


class TestContextCLI:
    def test_context_help(self):
        from semantic_code_intelligence.cli.commands.context_cmd import context_cmd
        runner = CliRunner()
        result = runner.invoke(context_cmd, ["--help"])
        assert result.exit_code == 0
        assert "query" in result.output
        assert "symbol" in result.output
        assert "file" in result.output
        assert "repo" in result.output

    def test_context_options(self):
        from semantic_code_intelligence.cli.commands.context_cmd import context_cmd
        runner = CliRunner()
        result = runner.invoke(context_cmd, ["--help"])
        assert "--top-k" in result.output
        assert "--json" in result.output

    @patch("semantic_code_intelligence.bridge.context_provider.search_codebase")
    def test_context_query_json(self, mock_search, tmp_path):
        mock_search.return_value = []
        from semantic_code_intelligence.cli.commands.context_cmd import context_cmd
        runner = CliRunner()
        result = runner.invoke(
            context_cmd,
            ["query", "test", "--json", "--path", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"] == "test"

    def test_context_repo_json(self, tmp_path):
        from semantic_code_intelligence.cli.commands.context_cmd import context_cmd
        runner = CliRunner()
        with patch(
            "semantic_code_intelligence.bridge.context_provider.ContextProvider.context_for_repo"
        ) as mock_repo:
            mock_repo.return_value = {"total_files": 5}
            result = runner.invoke(
                context_cmd,
                ["repo", "--json", "--path", str(tmp_path)],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["total_files"] == 5


# =========================================================================
# Bridge __init__ imports
# =========================================================================


class TestBridgeImports:
    def test_all_exports(self):
        from semantic_code_intelligence.bridge import (
            AgentRequest,
            AgentResponse,
            BridgeCapabilities,
            ContextProvider,
            BridgeServer,
            VSCodeBridge,
        )
        assert AgentRequest is not None
        assert AgentResponse is not None
        assert BridgeCapabilities is not None
        assert ContextProvider is not None
        assert BridgeServer is not None
        assert VSCodeBridge is not None
