"""Tests for the expanded CLI commands (explain, summary, watch, deps)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from semantic_code_intelligence.cli.main import cli


SAMPLE_PYTHON = """\
import os

def greet(name):
    return f"Hello, {name}!"

class Service:
    def __init__(self, url):
        self.url = url
"""


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal initialized project."""
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "main.py").write_text(SAMPLE_PYTHON, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# explain command
# ---------------------------------------------------------------------------

class TestExplainCmd:
    def test_explain_file(self, runner, project_dir):
        main_py = str(project_dir / "main.py")
        result = runner.invoke(cli, ["explain", ".", "--file", main_py, "-p", str(project_dir)])
        assert result.exit_code == 0

    def test_explain_symbol_in_file(self, runner, project_dir):
        main_py = str(project_dir / "main.py")
        result = runner.invoke(cli, ["explain", "greet", "--file", main_py, "-p", str(project_dir)])
        assert result.exit_code == 0
        assert "greet" in result.output

    def test_explain_symbol_not_found(self, runner, project_dir):
        main_py = str(project_dir / "main.py")
        result = runner.invoke(cli, ["explain", "nonexistent", "--file", main_py, "-p", str(project_dir)])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_explain_json_mode(self, runner, project_dir):
        main_py = str(project_dir / "main.py")
        result = runner.invoke(cli, ["explain", ".", "--file", main_py, "--json", "-p", str(project_dir)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# summary command
# ---------------------------------------------------------------------------

class TestSummaryCmd:
    def test_summary_basic(self, runner, project_dir):
        result = runner.invoke(cli, ["summary", "-p", str(project_dir)])
        assert result.exit_code == 0

    def test_summary_json(self, runner, project_dir):
        result = runner.invoke(cli, ["summary", "--json", "-p", str(project_dir)])
        assert result.exit_code == 0

    def test_summary_empty_project(self, runner, tmp_path):
        config_dir = tmp_path / ".codex"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}", encoding="utf-8")
        result = runner.invoke(cli, ["summary", "-p", str(tmp_path)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# deps command
# ---------------------------------------------------------------------------

class TestDepsCmd:
    def test_deps_single_file(self, runner, project_dir):
        result = runner.invoke(cli, ["deps", "main.py", "-p", str(project_dir)])
        assert result.exit_code == 0

    def test_deps_whole_project(self, runner, project_dir):
        result = runner.invoke(cli, ["deps", ".", "-p", str(project_dir)])
        assert result.exit_code == 0

    def test_deps_json(self, runner, project_dir):
        result = runner.invoke(cli, ["deps", ".", "--json", "-p", str(project_dir)])
        assert result.exit_code == 0

    def test_deps_nonexistent_file(self, runner, project_dir):
        result = runner.invoke(cli, ["deps", "nope.py", "-p", str(project_dir)])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# watch command
# ---------------------------------------------------------------------------

class TestWatchCmd:
    def test_watch_no_init(self, runner, tmp_path):
        result = runner.invoke(cli, ["watch", "-p", str(tmp_path)])
        assert result.exit_code == 0
        assert "not initialized" in result.output.lower()


# ---------------------------------------------------------------------------
# router verification
# ---------------------------------------------------------------------------

class TestRouter:
    def test_all_commands_registered(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "explain" in result.output
        assert "summary" in result.output
        assert "watch" in result.output
        assert "deps" in result.output
        assert "init" in result.output
        assert "index" in result.output
        assert "search" in result.output
