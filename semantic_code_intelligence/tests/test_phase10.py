"""Tests for Phase 10 — Multi-Repository Workspace Intelligence.

Covers: RepoEntry, WorkspaceManifest, Workspace model (persistence,
repo management, summary), and CLI workspace subcommands.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest

from semantic_code_intelligence.workspace import (
    RepoEntry,
    Workspace,
    WorkspaceManifest,
    WORKSPACE_FILE,
)
from semantic_code_intelligence.cli.commands.workspace_cmd import workspace_cmd


# =========================================================================
# RepoEntry tests
# =========================================================================


class TestRepoEntry:
    def test_to_dict(self):
        entry = RepoEntry(name="backend", path="/repos/backend", last_indexed=1000.0, file_count=42, vector_count=100)
        d = entry.to_dict()
        assert d["name"] == "backend"
        assert d["path"] == "/repos/backend"
        assert d["last_indexed"] == 1000.0
        assert d["file_count"] == 42
        assert d["vector_count"] == 100

    def test_from_dict_full(self):
        data = {"name": "api", "path": "/code/api", "last_indexed": 999.0, "file_count": 5, "vector_count": 20}
        entry = RepoEntry.from_dict(data)
        assert entry.name == "api"
        assert entry.path == "/code/api"
        assert entry.last_indexed == 999.0

    def test_from_dict_defaults(self):
        data = {"name": "lib", "path": "/code/lib"}
        entry = RepoEntry.from_dict(data)
        assert entry.last_indexed == 0.0
        assert entry.file_count == 0
        assert entry.vector_count == 0

    def test_roundtrip(self):
        entry = RepoEntry(name="x", path="/x", last_indexed=1.5, file_count=3, vector_count=7)
        reconstructed = RepoEntry.from_dict(entry.to_dict())
        assert reconstructed.name == entry.name
        assert reconstructed.path == entry.path
        assert reconstructed.last_indexed == entry.last_indexed
        assert reconstructed.file_count == entry.file_count
        assert reconstructed.vector_count == entry.vector_count


# =========================================================================
# WorkspaceManifest tests
# =========================================================================


class TestWorkspaceManifest:
    def test_empty_manifest(self):
        m = WorkspaceManifest()
        assert m.version == "1.0.0"
        assert m.repos == []

    def test_to_dict(self):
        m = WorkspaceManifest(repos=[
            RepoEntry(name="a", path="/a"),
            RepoEntry(name="b", path="/b"),
        ])
        d = m.to_dict()
        assert d["version"] == "1.0.0"
        assert len(d["repos"]) == 2
        assert d["repos"][0]["name"] == "a"

    def test_from_dict(self):
        data = {"version": "2.0.0", "repos": [{"name": "z", "path": "/z"}]}
        m = WorkspaceManifest.from_dict(data)
        assert m.version == "2.0.0"
        assert len(m.repos) == 1
        assert m.repos[0].name == "z"

    def test_from_dict_defaults(self):
        m = WorkspaceManifest.from_dict({})
        assert m.version == "1.0.0"
        assert m.repos == []

    def test_roundtrip(self):
        original = WorkspaceManifest(repos=[
            RepoEntry(name="core", path="/core", file_count=10),
        ])
        restored = WorkspaceManifest.from_dict(original.to_dict())
        assert restored.version == original.version
        assert len(restored.repos) == 1
        assert restored.repos[0].name == "core"
        assert restored.repos[0].file_count == 10


# =========================================================================
# Workspace model tests
# =========================================================================


class TestWorkspaceProperties:
    def test_root_and_directories(self, tmp_path):
        ws = Workspace(tmp_path)
        assert ws.root == tmp_path.resolve()
        assert ws.config_dir == tmp_path.resolve() / ".codex"
        assert ws.repos_dir == tmp_path.resolve() / ".codex" / "repos"
        assert ws.manifest_path == tmp_path.resolve() / ".codex" / WORKSPACE_FILE

    def test_repos_empty(self, tmp_path):
        ws = Workspace(tmp_path)
        assert ws.repos == []

    def test_repo_index_dir(self, tmp_path):
        ws = Workspace(tmp_path)
        assert ws.repo_index_dir("myrepo") == ws.repos_dir / "myrepo"


class TestWorkspacePersistence:
    def test_save_creates_files(self, tmp_path):
        ws = Workspace(tmp_path)
        result_path = ws.save()
        assert result_path.exists()
        assert ws.config_dir.exists()
        assert ws.repos_dir.exists()
        data = json.loads(result_path.read_text())
        assert data["version"] == "1.0.0"
        assert data["repos"] == []

    def test_load_roundtrip(self, tmp_path):
        ws = Workspace(tmp_path)
        repo_dir = tmp_path / "myrepo"
        repo_dir.mkdir()
        ws.add_repo("myrepo", repo_dir)
        ws.save()

        loaded = Workspace.load(tmp_path)
        assert len(loaded.repos) == 1
        assert loaded.repos[0].name == "myrepo"

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No workspace found"):
            Workspace.load(tmp_path / "nope")

    def test_load_or_create_new(self, tmp_path):
        ws = Workspace.load_or_create(tmp_path)
        assert ws.manifest_path.exists()
        assert ws.repos == []

    def test_load_or_create_existing(self, tmp_path):
        ws = Workspace(tmp_path)
        repo_dir = tmp_path / "r"
        repo_dir.mkdir()
        ws.add_repo("r", repo_dir)
        ws.save()

        ws2 = Workspace.load_or_create(tmp_path)
        assert len(ws2.repos) == 1


class TestWorkspaceRepoManagement:
    def test_add_repo(self, tmp_path):
        ws = Workspace(tmp_path)
        repo_dir = tmp_path / "repo_a"
        repo_dir.mkdir()
        entry = ws.add_repo("repo_a", repo_dir)
        assert entry.name == "repo_a"
        assert entry.path == str(repo_dir.resolve())
        assert len(ws.repos) == 1

    def test_add_duplicate_raises(self, tmp_path):
        ws = Workspace(tmp_path)
        repo_dir = tmp_path / "d"
        repo_dir.mkdir()
        ws.add_repo("d", repo_dir)
        with pytest.raises(ValueError, match="already registered"):
            ws.add_repo("d", repo_dir)

    def test_add_nonexistent_dir_raises(self, tmp_path):
        ws = Workspace(tmp_path)
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            ws.add_repo("missing", tmp_path / "nope")

    def test_remove_repo(self, tmp_path):
        ws = Workspace(tmp_path)
        repo_dir = tmp_path / "rem"
        repo_dir.mkdir()
        ws.add_repo("rem", repo_dir)
        assert ws.remove_repo("rem") is True
        assert len(ws.repos) == 0

    def test_remove_nonexistent(self, tmp_path):
        ws = Workspace(tmp_path)
        assert ws.remove_repo("ghost") is False

    def test_get_repo(self, tmp_path):
        ws = Workspace(tmp_path)
        repo_dir = tmp_path / "g"
        repo_dir.mkdir()
        ws.add_repo("g", repo_dir)
        assert ws.get_repo("g") is not None
        assert ws.get_repo("g").name == "g"
        assert ws.get_repo("nope") is None

    def test_multiple_repos(self, tmp_path):
        ws = Workspace(tmp_path)
        for name in ["a", "b", "c"]:
            d = tmp_path / name
            d.mkdir()
            ws.add_repo(name, d)
        assert len(ws.repos) == 3
        names = {r.name for r in ws.repos}
        assert names == {"a", "b", "c"}


class TestWorkspaceSummary:
    def test_summary_structure(self, tmp_path):
        ws = Workspace(tmp_path)
        repo_dir = tmp_path / "s"
        repo_dir.mkdir()
        ws.add_repo("s", repo_dir)
        info = ws.summary()
        assert info["root"] == str(tmp_path.resolve())
        assert info["repo_count"] == 1
        assert info["version"] == "1.0.0"
        assert len(info["repos"]) == 1
        assert info["repos"][0]["name"] == "s"


class TestWorkspaceIndexing:
    def test_index_repo_not_registered(self, tmp_path):
        ws = Workspace(tmp_path)
        with pytest.raises(KeyError, match="not registered"):
            ws.index_repo("nope")

    @patch("semantic_code_intelligence.workspace.generate_embeddings")
    @patch("semantic_code_intelligence.workspace.scan_repository")
    def test_index_repo_empty(self, mock_scan, mock_embed, tmp_path):
        """Indexing a repo with no files produces zero vectors."""
        mock_scan.return_value = []
        ws = Workspace(tmp_path)
        repo_dir = tmp_path / "empty_repo"
        repo_dir.mkdir()
        ws.add_repo("empty_repo", repo_dir)
        ws.save()
        result = ws.index_repo("empty_repo")
        assert result.files_indexed == 0
        assert result.chunks_created == 0


class TestWorkspaceSearch:
    def test_search_no_repos(self, tmp_path):
        """Searching with no repos returns empty list."""
        ws = Workspace(tmp_path)
        ws.save()
        with patch("semantic_code_intelligence.workspace.generate_embeddings") as mock_embed:
            import numpy as np
            mock_embed.return_value = np.zeros((1, 384))
            results = ws.search("hello")
        assert results == []


# =========================================================================
# CLI command tests
# =========================================================================


class TestWorkspaceCLI:
    def test_command_group_name(self):
        assert workspace_cmd.name == "workspace"

    def test_subcommands_exist(self):
        names = list(workspace_cmd.commands.keys())
        assert "init" in names
        assert "add" in names
        assert "remove" in names
        assert "list" in names
        assert "index" in names
        assert "search" in names

    def test_subcommand_count(self):
        assert len(workspace_cmd.commands) == 6

    def test_init_creates_workspace(self, tmp_path):
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(workspace_cmd, ["init", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".codex" / WORKSPACE_FILE).exists()

    def test_add_without_init_fails(self, tmp_path):
        from click.testing import CliRunner
        runner = CliRunner()
        repo = tmp_path / "repo"
        repo.mkdir()
        result = runner.invoke(workspace_cmd, ["add", "myrepo", str(repo), "--path", str(tmp_path)])
        assert result.exit_code == 0  # click still exits 0 but prints error
        assert "not initialised" in result.output.lower() or "error" in result.output.lower()

    def test_add_and_list(self, tmp_path):
        from click.testing import CliRunner
        runner = CliRunner()
        # Init
        runner.invoke(workspace_cmd, ["init", "--path", str(tmp_path)])
        # Add
        repo = tmp_path / "backend"
        repo.mkdir()
        result = runner.invoke(workspace_cmd, ["add", "backend", str(repo), "--path", str(tmp_path)])
        assert result.exit_code == 0
        # List JSON
        result = runner.invoke(workspace_cmd, ["list", "--json", "--path", str(tmp_path)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["repo_count"] == 1

    def test_remove_repo(self, tmp_path):
        from click.testing import CliRunner
        runner = CliRunner()
        runner.invoke(workspace_cmd, ["init", "--path", str(tmp_path)])
        repo = tmp_path / "api"
        repo.mkdir()
        runner.invoke(workspace_cmd, ["add", "api", str(repo), "--path", str(tmp_path)])
        result = runner.invoke(workspace_cmd, ["remove", "api", "--path", str(tmp_path)])
        assert result.exit_code == 0
        # Verify removed
        result = runner.invoke(workspace_cmd, ["list", "--json", "--path", str(tmp_path)])
        data = json.loads(result.output)
        assert data["repo_count"] == 0

    def test_remove_nonexistent_warns(self, tmp_path):
        from click.testing import CliRunner
        runner = CliRunner()
        runner.invoke(workspace_cmd, ["init", "--path", str(tmp_path)])
        result = runner.invoke(workspace_cmd, ["remove", "ghost", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestRouterIncludesWorkspace:
    def test_workspace_command_registered(self):
        from semantic_code_intelligence.cli.router import register_commands
        group = click.Group(name="test")
        register_commands(group)
        assert "workspace" in group.commands
