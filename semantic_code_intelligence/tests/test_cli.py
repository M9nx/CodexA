"""Tests for CLI commands and routing."""

from __future__ import annotations

import errno
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from semantic_code_intelligence.config.settings import load_config

from semantic_code_intelligence.cli.main import cli
from semantic_code_intelligence.embeddings.generator import BYTES_PER_GB
from semantic_code_intelligence.embeddings.model_registry import MODEL_PROFILES


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click test runner."""
    return CliRunner()


@pytest.fixture
def initialized_project(tmp_path: Path) -> Path:
    """Create an initialized project directory."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        project = Path(td)
        runner.invoke(cli, ["init", str(project)])
        yield project


class TestCLIMain:
    """Tests for the main CLI group."""

    def test_cli_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Codex" in result.output

    def test_cli_version(self, runner: CliRunner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.5.0" in result.output

    def test_cli_verbose_flag(self, runner: CliRunner):
        result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_project(self, runner: CliRunner, tmp_path: Path):
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".codexa").is_dir()
        assert (tmp_path / ".codexa" / "config.json").exists()
        assert (tmp_path / ".codexa" / "index").is_dir()

    def test_init_already_initialized(self, runner: CliRunner, tmp_path: Path):
        # First init
        runner.invoke(cli, ["init", str(tmp_path)])
        # Second init should detect existing
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "already initialized" in result.output

    def test_init_default_path(self, runner: CliRunner):
        with runner.isolated_filesystem() as td:
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            assert Path(td, ".codexa").is_dir()

    def test_init_profile_aliases(self, runner: CliRunner, tmp_path: Path):
        cases = [
            ("small", "fast"),
            ("base", "balanced"),
            ("large", "precise"),
        ]

        for alias, expected_profile in cases:
            proj = tmp_path / alias
            proj.mkdir()
            result = runner.invoke(cli, ["init", str(proj), "--profile", alias])
            assert result.exit_code == 0
            assert "Model profile" in result.output
            assert MODEL_PROFILES[expected_profile].label in result.output

            cfg = load_config(proj)
            assert cfg.embedding.model_name == MODEL_PROFILES[expected_profile].model_name

    def test_init_saves_recommended_batch_size(self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        # Force deterministic resource detection so recommendations are stable in tests
        monkeypatch.setattr(
            "semantic_code_intelligence.cli.commands.init_cmd._get_available_memory_bytes",
            lambda: 3 * BYTES_PER_GB,
        )
        monkeypatch.setattr(
            "semantic_code_intelligence.cli.commands.init_cmd._get_cpu_count",
            lambda: 8,
        )

        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0

        config = json.loads((tmp_path / ".codexa" / "config.json").read_text(encoding="utf-8"))
        assert config["embedding"]["batch_size"] == 32
        # Profile for ~3GB RAM should be precise according to registry thresholds
        assert config["embedding"]["model_name"] == "jinaai/jina-embeddings-v2-base-code"

    def test_init_interactive_applies_selections(self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        # Provide stable detection so defaults are deterministic
        monkeypatch.setattr(
            "semantic_code_intelligence.cli.commands.init_cmd._get_available_memory_bytes",
            lambda: 5 * BYTES_PER_GB,
        )
        monkeypatch.setattr(
            "semantic_code_intelligence.cli.commands.init_cmd._get_cpu_count",
            lambda: 4,
        )

        result = runner.invoke(
            cli,
            ["init", str(tmp_path), "--interactive"],
            input="fast\n24\n",
        )
        assert result.exit_code == 0
        output = result.output.lower()
        assert "interactive installer" in output

        config = json.loads((tmp_path / ".codexa" / "config.json").read_text(encoding="utf-8"))
        assert config["embedding"]["model_name"] == MODEL_PROFILES["fast"].model_name
        assert config["embedding"]["batch_size"] == 24

    def test_init_interactive_updates_existing_project(self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        # Initial setup with defaults
        monkeypatch.setattr(
            "semantic_code_intelligence.cli.commands.init_cmd._get_available_memory_bytes",
            lambda: 2 * BYTES_PER_GB,
        )
        monkeypatch.setattr(
            "semantic_code_intelligence.cli.commands.init_cmd._get_cpu_count",
            lambda: 2,
        )
        runner.invoke(cli, ["init", str(tmp_path)])

        # Run interactive to change profile/batch
        result = runner.invoke(
            cli,
            ["init", str(tmp_path), "--interactive"],
            input="precise\n16\n",
        )
        assert result.exit_code == 0

        config = json.loads((tmp_path / ".codexa" / "config.json").read_text(encoding="utf-8"))
        assert config["embedding"]["model_name"] == MODEL_PROFILES["precise"].model_name
        assert config["embedding"]["batch_size"] == 16

    def test_init_interactive_invalid_config(self, runner: CliRunner, tmp_path: Path):
        runner.invoke(cli, ["init", str(tmp_path)])
        config_path = tmp_path / ".codexa" / "config.json"
        config_path.write_text("{ invalid json", encoding="utf-8")

        result = runner.invoke(cli, ["init", str(tmp_path), "--interactive"])

        assert result.exit_code != 0
        assert "failed to read existing .codexa/config.json" in result.output.lower()

    def test_init_interactive_config_permission_error(self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        runner.invoke(cli, ["init", str(tmp_path)])

        def raise_permission_error(*args, **kwargs):
            raise OSError(errno.EACCES, "permission denied")

        monkeypatch.setattr(
            "semantic_code_intelligence.cli.commands.init_cmd.load_config",
            raise_permission_error,
        )

        result = runner.invoke(cli, ["init", str(tmp_path), "--interactive"])

        assert result.exit_code != 0
        assert "failed to read existing .codexa/config.json" in result.output.lower()


class TestIndexCommand:
    """Tests for the index command."""

    def test_index_without_init_fails(self, runner: CliRunner, tmp_path: Path):
        result = runner.invoke(cli, ["index", str(tmp_path)])
        assert result.exit_code != 0 or "not initialized" in result.output.lower()

    def test_index_initialized_project(self, runner: CliRunner, tmp_path: Path):
        # Initialize first
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(cli, ["index", str(tmp_path)])
        assert result.exit_code == 0
        assert "Indexing" in result.output or "index" in result.output.lower()

    def test_index_with_python_files(self, runner: CliRunner, tmp_path: Path):
        # Create some Python files
        (tmp_path / "main.py").write_text("def hello(): pass", encoding="utf-8")
        (tmp_path / "utils.py").write_text("def helper(): pass", encoding="utf-8")

        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(cli, ["index", str(tmp_path)])
        assert result.exit_code == 0
        # Should find 2 py files (not counting files in .codexa)
        assert "2 files" in result.output

    def test_index_ignores_excluded_dirs(self, runner: CliRunner, tmp_path: Path):
        # Create files in ignored directories
        (tmp_path / "main.py").write_text("def hello(): pass", encoding="utf-8")
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "pkg.js").write_text("function f(){}", encoding="utf-8")

        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(cli, ["index", str(tmp_path)])
        assert result.exit_code == 0
        assert "1 files" in result.output

    def test_index_force_flag(self, runner: CliRunner, tmp_path: Path):
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(cli, ["index", str(tmp_path), "--force"])
        assert result.exit_code == 0

    def test_index_batch_size_override(self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        project = tmp_path
        (project / "sample.py").write_text("def foo():\n    return 1\n", encoding="utf-8")

        captured: dict[str, int] = {}

        class DummyResult:
            files_scanned = 1
            files_indexed = 1
            files_skipped = 0
            chunks_created = 1
            total_vectors = 1

        def fake_run_indexing(project_root, force=False):
            cfg = load_config(project_root)
            captured["batch_size"] = cfg.embedding.batch_size
            return DummyResult()

        monkeypatch.setattr(
            "semantic_code_intelligence.cli.commands.index_cmd.run_indexing",
            fake_run_indexing,
        )

        runner.invoke(cli, ["init", str(project)])
        result = runner.invoke(cli, ["index", str(project), "--batch-size", "8"])
        assert result.exit_code == 0

        config = json.loads((project / ".codexa" / "config.json").read_text(encoding="utf-8"))
        assert config["embedding"]["batch_size"] == 8
        assert captured["batch_size"] == 8

    def test_index_network_oserror_is_nonfatal(self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        runner.invoke(cli, ["init", str(tmp_path)])

        def raise_network(*args, **kwargs):
            raise OSError(errno.ENETUNREACH, "network unreachable")

        monkeypatch.setattr("semantic_code_intelligence.cli.commands.index_cmd.run_indexing", raise_network)
        result = runner.invoke(cli, ["index", str(tmp_path)])
        assert result.exit_code == 0
        assert "network issue" in result.output.lower()

    def test_index_non_network_oserror_fails(self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        runner.invoke(cli, ["init", str(tmp_path)])

        def raise_perm(*args, **kwargs):
            raise OSError(errno.EPERM, "permission denied")

        monkeypatch.setattr("semantic_code_intelligence.cli.commands.index_cmd.run_indexing", raise_perm)
        result = runner.invoke(cli, ["index", str(tmp_path)])
        assert result.exit_code != 0


class TestSearchCommand:
    """Tests for the search command."""

    def test_search_without_init_fails(self, runner: CliRunner, tmp_path: Path):
        result = runner.invoke(cli, ["search", "test query", "--path", str(tmp_path)])
        assert result.exit_code != 0 or "not initialized" in result.output.lower()

    def test_search_human_readable(self, runner: CliRunner, tmp_path: Path):
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(
            cli, ["search", "test query", "--path", str(tmp_path)]
        )
        assert result.exit_code == 0
        # Without an index, shows empty index warning
        assert "empty" in result.output.lower() or "no results" in result.output.lower()

    def test_search_json_output(self, runner: CliRunner, tmp_path: Path):
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(
            cli, ["search", "jwt verification", "--json", "--no-auto-index", "--path", str(tmp_path)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"] == "jwt verification"
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_custom_top_k(self, runner: CliRunner, tmp_path: Path):
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(
            cli,
            ["search", "query", "-k", "5", "--json", "--no-auto-index", "--path", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["top_k"] == 5

    def test_search_default_top_k_from_config(self, runner: CliRunner, tmp_path: Path):
        runner.invoke(cli, ["init", str(tmp_path)])
        result = runner.invoke(
            cli,
            ["search", "query", "--json", "--no-auto-index", "--path", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["top_k"] == 10  # default from config


class TestCommandRouting:
    """Tests that all commands are properly registered and routable."""

    def test_all_commands_registered(self, runner: CliRunner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # All Phase 1 commands should appear in help
        for cmd_name in ["init", "index", "search"]:
            assert cmd_name in result.output

    def test_init_command_accessible(self, runner: CliRunner):
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0

    def test_index_command_accessible(self, runner: CliRunner):
        result = runner.invoke(cli, ["index", "--help"])
        assert result.exit_code == 0

    def test_search_command_accessible(self, runner: CliRunner):
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0

    def test_unknown_command_fails(self, runner: CliRunner):
        result = runner.invoke(cli, ["nonexistent"])
        assert result.exit_code != 0
