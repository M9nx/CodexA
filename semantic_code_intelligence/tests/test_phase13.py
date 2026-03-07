"""Tests for Phase 13 — Open Source Readiness & Developer Experience.

Covers: auto-documentation generator, CLI commands (docs, doctor, plugin),
pipeline mode, plugin templates, OSS files, and pyproject.toml metadata.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

# =========================================================================
# Documentation Generator Tests
# =========================================================================

from semantic_code_intelligence.docs import (
    generate_bridge_reference,
    generate_cli_reference,
    generate_plugin_reference,
    generate_tool_reference,
    generate_all_docs,
)


class TestCLIReferenceGenerator:
    """Tests for CLI documentation generation."""

    def _make_group(self) -> click.Group:
        @click.group()
        def grp():
            """Test group."""

        @grp.command("search")
        @click.argument("query")
        @click.option("--top-k", "-k", default=10, type=int, help="Number of results.")
        @click.option("--json", "json_mode", is_flag=True, help="JSON output.")
        def search_cmd(query, top_k, json_mode):
            """Search the codebase."""

        @grp.command("init")
        @click.option("--path", "-p", default=".", help="Project root.")
        def init_cmd(path):
            """Initialize project."""

        return grp

    def test_generates_markdown(self):
        md = generate_cli_reference(self._make_group())
        assert "# CLI Reference" in md

    def test_includes_commands(self):
        md = generate_cli_reference(self._make_group())
        assert "## `codex init`" in md
        assert "## `codex search`" in md

    def test_includes_arguments(self):
        md = generate_cli_reference(self._make_group())
        assert "**Arguments:**" in md
        assert "`query`" in md

    def test_includes_options_table(self):
        md = generate_cli_reference(self._make_group())
        assert "**Options:**" in md
        assert "| Flag |" in md
        assert "`--top-k, -k`" in md

    def test_includes_help_text(self):
        md = generate_cli_reference(self._make_group())
        assert "Search the codebase." in md
        assert "Initialize project." in md

    def test_nested_group(self):
        @click.group()
        def root():
            pass

        @root.group("workspace")
        def ws():
            """Workspace management."""

        @ws.command("add")
        @click.argument("name")
        def ws_add(name):
            """Add a repo."""

        md = generate_cli_reference(root)
        assert "## `codex workspace`" in md
        assert "## `codex workspace add`" in md


class TestPluginReferenceGenerator:
    """Tests for plugin documentation generation."""

    def test_generates_markdown(self):
        md = generate_plugin_reference()
        assert "# Plugin SDK Reference" in md

    def test_includes_all_hooks(self):
        from semantic_code_intelligence.plugins import PluginHook
        md = generate_plugin_reference()
        for hook in PluginHook:
            assert hook.name in md

    def test_includes_hook_count(self):
        from semantic_code_intelligence.plugins import PluginHook
        md = generate_plugin_reference()
        assert f"**{len(PluginHook)}**" in md

    def test_includes_categories(self):
        md = generate_plugin_reference()
        assert "Indexing" in md
        assert "Search" in md
        assert "Streaming" in md
        assert "Validation" in md

    def test_includes_base_class_docs(self):
        md = generate_plugin_reference()
        assert "PluginBase" in md
        assert "PluginMetadata" in md
        assert "create_plugin()" in md

    def test_includes_lifecycle(self):
        md = generate_plugin_reference()
        assert "Register" in md
        assert "Activate" in md
        assert "Dispatch" in md
        assert "Deactivate" in md


class TestBridgeReferenceGenerator:
    """Tests for bridge protocol documentation generation."""

    def test_generates_markdown(self):
        md = generate_bridge_reference()
        assert "# Bridge Protocol Reference" in md

    def test_includes_endpoints(self):
        md = generate_bridge_reference()
        assert "/health" in md
        assert "/request" in md
        assert "GET" in md
        assert "POST" in md

    def test_includes_request_kinds(self):
        from semantic_code_intelligence.bridge.protocol import RequestKind
        md = generate_bridge_reference()
        for kind in RequestKind:
            assert kind.name in md

    def test_includes_request_response_schemas(self):
        md = generate_bridge_reference()
        assert "AgentRequest" in md
        assert "AgentResponse" in md
        assert "request_id" in md
        assert "elapsed_ms" in md

    def test_includes_example_json(self):
        md = generate_bridge_reference()
        assert '"kind"' in md
        assert '"semantic_search"' in md


class TestToolReferenceGenerator:
    """Tests for tool registry documentation generation."""

    def test_generates_markdown(self):
        md = generate_tool_reference()
        assert "# Tool Registry Reference" in md

    def test_includes_tools(self):
        md = generate_tool_reference()
        assert "semantic_search" in md
        assert "explain_symbol" in md
        assert "summarize_repo" in md

    def test_includes_tool_count(self):
        from semantic_code_intelligence.tools import TOOL_DEFINITIONS
        md = generate_tool_reference()
        assert f"**{len(TOOL_DEFINITIONS)} tools" in md

    def test_includes_usage_example(self):
        md = generate_tool_reference()
        assert "ToolRegistry" in md
        assert "to_json()" in md


class TestGenerateAllDocs:
    """Tests for the combined documentation generator."""

    def test_creates_output_directory(self, tmp_path):
        out = tmp_path / "docs"
        generated = generate_all_docs(out)
        assert out.is_dir()
        assert len(generated) >= 3

    def test_generates_plugin_md(self, tmp_path):
        out = tmp_path / "docs"
        generated = generate_all_docs(out)
        assert "PLUGINS.md" in generated
        assert (out / "PLUGINS.md").is_file()

    def test_generates_bridge_md(self, tmp_path):
        out = tmp_path / "docs"
        generated = generate_all_docs(out)
        assert "BRIDGE.md" in generated
        content = (out / "BRIDGE.md").read_text()
        assert "Bridge Protocol" in content

    def test_generates_tools_md(self, tmp_path):
        out = tmp_path / "docs"
        generated = generate_all_docs(out)
        assert "TOOLS.md" in generated

    def test_generates_cli_md(self, tmp_path):
        out = tmp_path / "docs"
        generated = generate_all_docs(out)
        assert "CLI.md" in generated
        content = (out / "CLI.md").read_text()
        assert "CLI Reference" in content


# =========================================================================
# Doctor Command Tests
# =========================================================================

from semantic_code_intelligence.cli.commands.doctor_cmd import run_checks, doctor_cmd


class TestDoctorChecks:
    """Tests for the doctor health check system."""

    def test_returns_list(self, tmp_path):
        checks = run_checks(tmp_path)
        assert isinstance(checks, list)
        assert len(checks) > 0

    def test_python_check(self, tmp_path):
        checks = run_checks(tmp_path)
        py_check = next(c for c in checks if c["name"] == "Python")
        assert py_check["ok"] is True
        assert "3." in py_check["version"]

    def test_codex_version_check(self, tmp_path):
        from semantic_code_intelligence import __version__
        checks = run_checks(tmp_path)
        codex_check = next(c for c in checks if c["name"] == "CodexA")
        assert codex_check["ok"] is True
        assert codex_check["version"] == __version__

    def test_click_check(self, tmp_path):
        checks = run_checks(tmp_path)
        click_check = next(c for c in checks if c["name"] == "click")
        assert click_check["ok"] is True

    def test_project_not_initialized(self, tmp_path):
        checks = run_checks(tmp_path)
        proj = next(c for c in checks if c["name"] == "Project")
        assert proj["ok"] is False
        assert "Not initialized" in proj["detail"]

    def test_project_initialized(self, tmp_path):
        (tmp_path / ".codex").mkdir()
        checks = run_checks(tmp_path)
        proj = next(c for c in checks if c["name"] == "Project")
        assert proj["ok"] is True

    def test_project_indexed(self, tmp_path):
        idx = tmp_path / ".codex" / "index"
        idx.mkdir(parents=True)
        (idx / "vectors.faiss").write_text("dummy")
        checks = run_checks(tmp_path)
        proj = next(c for c in checks if c["name"] == "Project")
        assert "indexed" in proj["detail"]


class TestDoctorCLI:
    """Tests for the doctor CLI command."""

    def test_runs_successfully(self):
        runner = CliRunner()
        result = runner.invoke(doctor_cmd, ["--path", "."])
        assert result.exit_code == 0

    def test_json_output(self):
        runner = CliRunner()
        result = runner.invoke(doctor_cmd, ["--json", "--path", "."])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "checks" in data
        assert len(data["checks"]) > 0

    def test_json_has_check_fields(self):
        runner = CliRunner()
        result = runner.invoke(doctor_cmd, ["--json", "--path", "."])
        data = json.loads(result.output)
        for check in data["checks"]:
            assert "name" in check
            assert "ok" in check
            assert "detail" in check


# =========================================================================
# Docs Command Tests
# =========================================================================

from semantic_code_intelligence.cli.commands.docs_cmd import docs_cmd


class TestDocsCLI:
    """Tests for the docs CLI command."""

    def test_generates_all_docs(self, tmp_path):
        runner = CliRunner()
        out = str(tmp_path / "docs")
        result = runner.invoke(docs_cmd, ["--output", out])
        assert result.exit_code == 0

    def test_generates_specific_section(self, tmp_path):
        runner = CliRunner()
        out = str(tmp_path / "docs")
        result = runner.invoke(docs_cmd, ["--output", out, "--section", "plugins"])
        assert result.exit_code == 0
        assert (tmp_path / "docs" / "PLUGINS.md").is_file()

    def test_json_output(self, tmp_path):
        runner = CliRunner()
        out = str(tmp_path / "docs")
        result = runner.invoke(docs_cmd, ["--output", out, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "output_dir" in data
        assert "files" in data
        assert len(data["files"]) > 0

    def test_section_cli(self, tmp_path):
        runner = CliRunner()
        out = str(tmp_path / "docs")
        result = runner.invoke(docs_cmd, ["--output", out, "--section", "cli"])
        assert result.exit_code == 0
        assert (tmp_path / "docs" / "CLI.md").is_file()

    def test_section_bridge(self, tmp_path):
        runner = CliRunner()
        out = str(tmp_path / "docs")
        result = runner.invoke(docs_cmd, ["--output", out, "--section", "bridge"])
        assert result.exit_code == 0
        assert (tmp_path / "docs" / "BRIDGE.md").is_file()

    def test_section_tools(self, tmp_path):
        runner = CliRunner()
        out = str(tmp_path / "docs")
        result = runner.invoke(docs_cmd, ["--output", out, "--section", "tools"])
        assert result.exit_code == 0
        assert (tmp_path / "docs" / "TOOLS.md").is_file()


# =========================================================================
# Plugin Command Tests
# =========================================================================

from semantic_code_intelligence.cli.commands.plugin_cmd import plugin_cmd


class TestPluginNewCLI:
    """Tests for the plugin scaffold command."""

    def test_creates_plugin_file(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(plugin_cmd, ["new", "my-test", "--output", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "my_test.py").is_file()

    def test_plugin_file_content(self, tmp_path):
        runner = CliRunner()
        runner.invoke(plugin_cmd, ["new", "my-test", "--output", str(tmp_path)])
        content = (tmp_path / "my_test.py").read_text()
        assert "class MyTestPlugin(PluginBase)" in content
        assert "def create_plugin()" in content
        assert "def metadata(self)" in content

    def test_custom_hooks(self, tmp_path):
        runner = CliRunner()
        runner.invoke(plugin_cmd, [
            "new", "validator",
            "--hooks", "CUSTOM_VALIDATION,POST_AI",
            "--output", str(tmp_path),
        ])
        content = (tmp_path / "validator.py").read_text()
        assert "PluginHook.CUSTOM_VALIDATION" in content
        assert "PluginHook.POST_AI" in content

    def test_custom_description(self, tmp_path):
        runner = CliRunner()
        runner.invoke(plugin_cmd, [
            "new", "fmt",
            "--description", "Formats code output",
            "--output", str(tmp_path),
        ])
        content = (tmp_path / "fmt.py").read_text()
        assert "Formats code output" in content

    def test_custom_author(self, tmp_path):
        runner = CliRunner()
        runner.invoke(plugin_cmd, [
            "new", "fmt",
            "--author", "Test Author",
            "--output", str(tmp_path),
        ])
        content = (tmp_path / "fmt.py").read_text()
        assert "Test Author" in content

    def test_rejects_invalid_hooks(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(plugin_cmd, [
            "new", "bad",
            "--hooks", "NONEXISTENT_HOOK",
            "--output", str(tmp_path),
        ])
        assert "Unknown hook" in result.output

    def test_rejects_existing_file(self, tmp_path):
        # Create file first
        (tmp_path / "dup.py").write_text("existing")
        runner = CliRunner()
        result = runner.invoke(plugin_cmd, ["new", "dup", "--output", str(tmp_path)])
        assert "already exists" in result.output

    def test_generated_plugin_is_importable(self, tmp_path):
        """Generated plugin scaffolds should be valid Python."""
        runner = CliRunner()
        runner.invoke(plugin_cmd, ["new", "importable", "--output", str(tmp_path)])
        filepath = tmp_path / "importable.py"
        content = filepath.read_text()
        # Compile to check syntax validity
        compile(content, str(filepath), "exec")


class TestPluginListCLI:
    """Tests for the plugin list command."""

    def test_no_plugins(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(plugin_cmd, ["list", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "No plugins found" in result.output

    def test_json_no_plugins(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(plugin_cmd, ["list", "--path", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0
        assert data["plugins"] == []


class TestPluginInfoCLI:
    """Tests for the plugin info command."""

    def test_unknown_plugin(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(plugin_cmd, ["info", "nonexistent", "--path", str(tmp_path)])
        assert "not found" in result.output


# =========================================================================
# Pipeline Mode Tests
# =========================================================================

from semantic_code_intelligence.cli.main import cli


class TestPipelineMode:
    """Tests for the --pipe global flag."""

    def test_pipe_flag_exists(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "--pipe" in result.output

    def test_pipe_flag_sets_context(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--pipe", "--help"])
        assert result.exit_code == 0

    def test_version_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert "0.17.0" in result.output


# =========================================================================
# Router Tests
# =========================================================================

class TestRouterRegistration:
    """Tests for new command registration in the router."""

    def test_docs_command_registered(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["docs", "--help"])
        assert result.exit_code == 0
        assert "documentation" in result.output.lower() or "docs" in result.output.lower()

    def test_doctor_command_registered(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower() or "environment" in result.output.lower()

    def test_plugin_command_registered(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["plugin", "--help"])
        assert result.exit_code == 0
        assert "new" in result.output
        assert "list" in result.output

    def test_total_command_count(self):
        """Verify we now have 17 top-level commands."""
        assert len(cli.commands) == 27


# =========================================================================
# Sample Plugin Tests
# =========================================================================

class TestSearchAnnotatorPlugin:
    """Tests for the sample search annotator plugin."""

    def test_plugin_imports(self):
        from semantic_code_intelligence.plugins.examples.search_annotator import (
            SearchAnnotatorPlugin,
            create_plugin,
        )
        plugin = create_plugin()
        assert plugin is not None

    def test_metadata(self):
        from semantic_code_intelligence.plugins.examples.search_annotator import create_plugin
        plugin = create_plugin()
        meta = plugin.metadata()
        assert meta.name == "search-annotator"
        assert meta.version == "0.1.0"

    def test_post_search_hook(self):
        from semantic_code_intelligence.plugins.examples.search_annotator import create_plugin
        from semantic_code_intelligence.plugins import PluginHook
        plugin = create_plugin()
        plugin.activate({})
        data = {"results": [{"file": "a.py"}, {"file": "b.py"}], "query": "test"}
        result = plugin.on_hook(PluginHook.POST_SEARCH, data)
        assert result["annotation_count"] == 2
        assert result["results"][0]["annotated_by"] == "search-annotator"


class TestCodeQualityPlugin:
    """Tests for the sample code quality plugin."""

    def test_plugin_imports(self):
        from semantic_code_intelligence.plugins.examples.code_quality import (
            CodeQualityPlugin,
            create_plugin,
        )
        plugin = create_plugin()
        assert plugin is not None

    def test_detects_todo(self):
        from semantic_code_intelligence.plugins.examples.code_quality import create_plugin
        from semantic_code_intelligence.plugins import PluginHook
        plugin = create_plugin()
        data = {"code": "x = 1  # TODO fix later", "issues": []}
        result = plugin.on_hook(PluginHook.CUSTOM_VALIDATION, data)
        assert len(result["issues"]) >= 1
        assert any("TODO" in i["description"] for i in result["issues"])

    def test_detects_print(self):
        from semantic_code_intelligence.plugins.examples.code_quality import create_plugin
        from semantic_code_intelligence.plugins import PluginHook
        plugin = create_plugin()
        data = {"code": 'print("hello world")', "issues": []}
        result = plugin.on_hook(PluginHook.CUSTOM_VALIDATION, data)
        assert any("logging" in i["description"] for i in result["issues"])

    def test_clean_code(self):
        from semantic_code_intelligence.plugins.examples.code_quality import create_plugin
        from semantic_code_intelligence.plugins import PluginHook
        plugin = create_plugin()
        data = {"code": "x = 1\ny = 2\n", "issues": []}
        result = plugin.on_hook(PluginHook.CUSTOM_VALIDATION, data)
        assert len(result["issues"]) == 0


# =========================================================================
# OSS Files Tests
# =========================================================================

class TestOSSFiles:
    """Tests that required open-source files exist and have content."""

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    def test_license_exists(self):
        assert (self._project_root() / "LICENSE").is_file()

    def test_license_is_mit(self):
        content = (self._project_root() / "LICENSE").read_text()
        assert "MIT License" in content

    def test_contributing_exists(self):
        assert (self._project_root() / "CONTRIBUTING.md").is_file()

    def test_contributing_has_content(self):
        content = (self._project_root() / "CONTRIBUTING.md").read_text()
        assert "Contributing" in content
        assert "pytest" in content

    def test_security_exists(self):
        assert (self._project_root() / "SECURITY.md").is_file()

    def test_ci_workflow_exists(self):
        assert (self._project_root() / ".github" / "workflows" / "ci.yml").is_file()

    def test_bug_report_template_exists(self):
        assert (self._project_root() / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").is_file()

    def test_feature_request_template_exists(self):
        assert (self._project_root() / ".github" / "ISSUE_TEMPLATE" / "feature_request.md").is_file()

    def test_pr_template_exists(self):
        assert (self._project_root() / ".github" / "PULL_REQUEST_TEMPLATE.md").is_file()


# =========================================================================
# Version and Metadata Tests
# =========================================================================

class TestProjectMetadata:
    """Tests for project version and metadata consistency."""

    def test_version_format(self):
        from semantic_code_intelligence import __version__
        parts = __version__.split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts)

    def test_version_is_0_13(self):
        from semantic_code_intelligence import __version__
        assert __version__ == "0.17.0"

    def test_app_name(self):
        from semantic_code_intelligence import __app_name__
        assert __app_name__ == "codex"

    def test_pyproject_exists(self):
        root = Path(__file__).resolve().parent.parent.parent
        assert (root / "pyproject.toml").is_file()
