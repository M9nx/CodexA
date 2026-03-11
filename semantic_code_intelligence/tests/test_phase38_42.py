"""Tests for Phases 38-42.

Phase 38: Incremental Embedding Models & Model Hub
Phase 39: Pre-built Wheels & Platform Distribution
Phase 40: Code Editor Compatibility
Phase 41: Multi-Agent Orchestration & IDE v2
Phase 42: Cross-Language Intelligence
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
    """Write a small project for testing."""
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "core.py").write_text(
        "def helper():\n    return 42\n\ndef compute(x):\n    return helper() + x\n",
        encoding="utf-8",
    )
    (src / "utils.js").write_text(
        "function format(val) { return String(val); }\n"
        "export { format };\n",
        encoding="utf-8",
    )
    config_dir = root / ".codexa"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({"project_root": str(root), "embedding": {"model_name": "all-MiniLM-L6-v2"}}),
        encoding="utf-8",
    )


# =========================================================================
# Phase 38: Incremental Embedding Models & Model Hub
# =========================================================================

class TestPhase38ModelRegistry:
    """Model registry extensions for Phase 38."""

    def test_model_index_subdir_default(self) -> None:
        from semantic_code_intelligence.embeddings.model_registry import model_index_subdir
        result = model_index_subdir("all-MiniLM-L6-v2")
        assert result == "vectors_all-MiniLM-L6-v2"

    def test_model_index_subdir_with_slash(self) -> None:
        from semantic_code_intelligence.embeddings.model_registry import model_index_subdir
        result = model_index_subdir("BAAI/bge-small-en-v1.5")
        assert result == "vectors_BAAI--bge-small-en-v1.5"

    def test_model_index_subdir_alias(self) -> None:
        from semantic_code_intelligence.embeddings.model_registry import model_index_subdir
        result = model_index_subdir("jina-code")
        assert "jina" in result

    def test_verify_model_integrity_missing(self) -> None:
        from semantic_code_intelligence.embeddings.model_registry import verify_model_integrity
        # A model that almost certainly isn't cached
        result = verify_model_integrity("nonexistent/model-xyz-999")
        assert result is False

    def test_model_checksums_dict_exists(self) -> None:
        from semantic_code_intelligence.embeddings.model_registry import MODEL_CHECKSUMS
        assert len(MODEL_CHECKSUMS) == 5
        assert "all-MiniLM-L6-v2" in MODEL_CHECKSUMS

    def test_resolve_model_name_unchanged(self) -> None:
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        assert resolve_model_name("all-MiniLM-L6-v2") == "all-MiniLM-L6-v2"

    def test_resolve_model_alias(self) -> None:
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        assert resolve_model_name("minilm") == "all-MiniLM-L6-v2"

    def test_resolve_model_custom(self) -> None:
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        assert resolve_model_name("my-org/custom-model") == "my-org/custom-model"


class TestPhase38IndexSwitchModel:
    """--switch-model flag on the index command."""

    def test_switch_model_updates_config(self, tmp_path: Path) -> None:
        _write_sample_project(tmp_path)
        from semantic_code_intelligence.config.settings import load_config, save_config
        config = load_config(tmp_path)
        assert config.embedding.model_name == "all-MiniLM-L6-v2"

        # Simulate what --switch-model does
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name
        resolved = resolve_model_name("jina-code")
        config.embedding.model_name = resolved
        save_config(config, tmp_path)

        reloaded = load_config(tmp_path)
        assert reloaded.embedding.model_name == "jinaai/jina-embeddings-v2-base-code"

    def test_index_cmd_has_switch_model_option(self) -> None:
        from semantic_code_intelligence.cli.commands.index_cmd import index_cmd
        param_names = [p.name for p in index_cmd.params]
        assert "switch_model" in param_names


class TestPhase38BenchmarkMemory:
    """Benchmark command includes memory metrics."""

    def test_benchmark_command_exists(self) -> None:
        from semantic_code_intelligence.cli.commands.models_cmd import models_cmd
        subcommands = {c.name for c in models_cmd.commands.values()}
        assert "benchmark" in subcommands

    def test_download_command_has_verify(self) -> None:
        from semantic_code_intelligence.cli.commands.models_cmd import models_cmd
        download_cmd = models_cmd.commands["download"]
        param_names = [p.name for p in download_cmd.params]
        assert "verify" in param_names


# =========================================================================
# Phase 39: Pre-built Wheels & Platform Distribution
# =========================================================================

class TestPhase39Distribution:
    """CI workflows, packages, and Docker."""

    def test_build_wheels_workflow_exists(self) -> None:
        workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "build-wheels.yml"
        assert workflow.exists(), f"Missing: {workflow}"

    def test_scoop_manifest_exists(self) -> None:
        manifest = Path(__file__).resolve().parents[2] / "packaging" / "scoop" / "codexa.json"
        assert manifest.exists()
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["version"] == "0.5.0"
        assert "64bit" in data["architecture"]

    def test_chocolatey_nuspec_exists(self) -> None:
        nuspec = Path(__file__).resolve().parents[2] / "packaging" / "chocolatey" / "codexa.nuspec"
        assert nuspec.exists()
        content = nuspec.read_text(encoding="utf-8")
        assert "<id>codexa</id>" in content

    def test_dockerfile_version_updated(self) -> None:
        dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text(encoding="utf-8")
        assert 'version="0.5.0"' in content

    def test_build_wheels_workflow_valid_yaml(self) -> None:
        workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "build-wheels.yml"
        content = workflow.read_text(encoding="utf-8")
        assert "maturin-action" in content
        assert "manylinux" in content
        assert "windows-latest" in content
        assert "macos-latest" in content


# =========================================================================
# Phase 40: Code Editor Compatibility
# =========================================================================

class TestPhase40EditorPlugins:
    """Editor integration files exist and are well-formed."""

    _editors_root = Path(__file__).resolve().parents[2] / "editors"

    def test_editors_readme(self) -> None:
        assert (self._editors_root / "README.md").exists()

    def test_zed_extension(self) -> None:
        zed = self._editors_root / "zed" / "extension.json"
        assert zed.exists()
        data = json.loads(zed.read_text(encoding="utf-8"))
        assert data["id"] == "codexa"
        assert "context_servers" in data

    def test_jetbrains_plugin_xml(self) -> None:
        plugin_xml = self._editors_root / "jetbrains" / "src" / "main" / "resources" / "META-INF" / "plugin.xml"
        assert plugin_xml.exists()
        content = plugin_xml.read_text(encoding="utf-8")
        assert "com.codexa.intellij" in content

    def test_jetbrains_kotlin_source(self) -> None:
        kt = self._editors_root / "jetbrains" / "src" / "main" / "kotlin" / "com" / "codexa" / "intellij" / "CodexaToolWindowFactory.kt"
        assert kt.exists()
        content = kt.read_text(encoding="utf-8")
        assert "bridgeSearch" in content

    def test_jetbrains_gradle(self) -> None:
        gradle = self._editors_root / "jetbrains" / "build.gradle.kts"
        assert gradle.exists()

    def test_neovim_plugin(self) -> None:
        lua = self._editors_root / "neovim" / "lua" / "codexa" / "init.lua"
        assert lua.exists()
        content = lua.read_text(encoding="utf-8")
        assert "semantic_search" in content
        assert "telescope" in content

    def test_vim_plugin(self) -> None:
        vim = self._editors_root / "vim" / "plugin" / "codexa.vim"
        assert vim.exists()
        content = vim.read_text(encoding="utf-8")
        assert "CodexaSearch" in content

    def test_sublime_plugin(self) -> None:
        sublime = self._editors_root / "sublime" / "codexa.py"
        assert sublime.exists()
        content = sublime.read_text(encoding="utf-8")
        assert "CodexaSearchCommand" in content

    def test_emacs_package(self) -> None:
        el = self._editors_root / "emacs" / "codexa.el"
        assert el.exists()
        content = el.read_text(encoding="utf-8")
        assert "codexa-search" in content
        assert "provide" in content

    def test_helix_readme(self) -> None:
        readme = self._editors_root / "helix" / "README.md"
        assert readme.exists()
        content = readme.read_text(encoding="utf-8")
        assert "languages.toml" in content

    def test_eclipse_plugin_xml(self) -> None:
        plugin = self._editors_root / "eclipse" / "plugin.xml"
        assert plugin.exists()
        content = plugin.read_text(encoding="utf-8")
        assert "com.codexa.eclipse" in content


# =========================================================================
# Phase 41: Multi-Agent Orchestration & IDE v2
# =========================================================================

class TestPhase41SessionManager:
    """Session manager for concurrent agents."""

    def test_create_session(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        session = mgr.create_session("copilot")
        assert session.session_id
        assert session.agent_name == "copilot"
        assert mgr.active_count == 1

    def test_get_session(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        s = mgr.create_session("cursor")
        retrieved = mgr.get_session(s.session_id)
        assert retrieved is not None
        assert retrieved.agent_name == "cursor"

    def test_get_session_not_found(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        assert mgr.get_session("nonexistent") is None

    def test_close_session(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        s = mgr.create_session()
        assert mgr.close_session(s.session_id) is True
        assert mgr.active_count == 0
        assert mgr.close_session(s.session_id) is False

    def test_multiple_sessions(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        s1 = mgr.create_session("agent-a")
        s2 = mgr.create_session("agent-b")
        assert mgr.active_count == 2
        assert s1.session_id != s2.session_id

    def test_session_search_history(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        s = mgr.create_session()
        s.add_search("find auth", 5)
        s.add_search("login handler", 3)
        assert len(s.search_history) == 2
        assert s.search_history[0]["query"] == "find auth"

    def test_shared_discoveries(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        s1 = mgr.create_session("agent-a")
        s2 = mgr.create_session("agent-b")
        mgr.share_discovery(s1.session_id, "auth_module", {"file": "auth.py"})
        # s2 should see s1's discoveries
        discoveries = mgr.get_shared_discoveries(exclude_session=s2.session_id)
        assert len(discoveries) == 1
        assert discoveries[0]["key"] == "auth_module"

    def test_session_to_dict(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        s = mgr.create_session("test-agent")
        d = s.to_dict()
        assert d["agent_name"] == "test-agent"
        assert "session_id" in d
        assert "created_at" in d

    def test_list_sessions(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        mgr.create_session("a")
        mgr.create_session("b")
        sessions = mgr.list_sessions()
        assert len(sessions) == 2

    def test_get_or_create_existing(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        s = mgr.create_session("test")
        s2 = mgr.get_or_create(s.session_id)
        assert s2.session_id == s.session_id

    def test_get_or_create_new(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager()
        s = mgr.get_or_create(None, "new-agent")
        assert s.agent_name == "new-agent"
        assert mgr.active_count == 1

    def test_expired_session_cleanup(self) -> None:
        from semantic_code_intelligence.sessions import SessionManager
        mgr = SessionManager(ttl_seconds=0)  # instant expiry
        s = mgr.create_session()
        s.last_active = time.time() - 1  # force expired
        mgr._cleanup_expired()
        assert mgr.active_count == 0


class TestPhase41SemanticDiff:
    """Semantic diff — AST-level structural comparison."""

    def test_added_symbol(self) -> None:
        from semantic_code_intelligence.analysis.semantic_diff import diff_symbols, ChangeKind
        from semantic_code_intelligence.parsing.parser import Symbol
        old = [Symbol(name="foo", kind="function", body="def foo(): pass", start_line=1, end_line=1, start_col=0, end_col=0, file_path="a.py")]
        new = old + [Symbol(name="bar", kind="function", body="def bar(): pass", start_line=3, end_line=3, start_col=0, end_col=0, file_path="a.py")]
        result = diff_symbols(old, new, "a.py")
        added = [c for c in result.changes if c.kind == ChangeKind.ADDED]
        assert len(added) == 1
        assert added[0].symbol_name == "bar"

    def test_removed_symbol(self) -> None:
        from semantic_code_intelligence.analysis.semantic_diff import diff_symbols, ChangeKind
        from semantic_code_intelligence.parsing.parser import Symbol
        old = [
            Symbol(name="foo", kind="function", body="def foo(): pass", start_line=1, end_line=1, start_col=0, end_col=0, file_path="a.py"),
            Symbol(name="bar", kind="function", body="def bar(): pass", start_line=3, end_line=3, start_col=0, end_col=0, file_path="a.py"),
        ]
        new = [old[0]]
        result = diff_symbols(old, new, "a.py")
        removed = [c for c in result.changes if c.kind == ChangeKind.REMOVED]
        assert len(removed) == 1
        assert removed[0].symbol_name == "bar"

    def test_renamed_symbol(self) -> None:
        """Rename detection: same normalized body (excluding the def line)."""
        from semantic_code_intelligence.analysis.semantic_diff import diff_symbols, ChangeKind
        from semantic_code_intelligence.parsing.parser import Symbol
        # For rename detection the normalized body must match — use identical bodies
        old = [Symbol(name="old_name", kind="function", body="return 42", start_line=1, end_line=2, start_col=0, end_col=0, file_path="a.py")]
        new = [Symbol(name="new_name", kind="function", body="return 42", start_line=1, end_line=2, start_col=0, end_col=0, file_path="a.py")]
        result = diff_symbols(old, new, "a.py")
        renames = [c for c in result.changes if c.kind == ChangeKind.RENAMED]
        assert len(renames) == 1
        assert renames[0].old_name == "old_name"
        assert renames[0].symbol_name == "new_name"

    def test_body_changed(self) -> None:
        from semantic_code_intelligence.analysis.semantic_diff import diff_symbols, ChangeKind
        from semantic_code_intelligence.parsing.parser import Symbol
        old = [Symbol(name="foo", kind="function", body="def foo():\n    return 1", start_line=1, end_line=2, start_col=0, end_col=0, file_path="a.py")]
        new = [Symbol(name="foo", kind="function", body="def foo():\n    return 2", start_line=1, end_line=2, start_col=0, end_col=0, file_path="a.py")]
        result = diff_symbols(old, new, "a.py")
        body_changes = [c for c in result.changes if c.kind == ChangeKind.BODY_CHANGED]
        assert len(body_changes) == 1

    def test_cosmetic_change(self) -> None:
        from semantic_code_intelligence.analysis.semantic_diff import diff_symbols, ChangeKind
        from semantic_code_intelligence.parsing.parser import Symbol
        old = [Symbol(name="foo", kind="function", body="def foo():\n    return 1", start_line=1, end_line=2, start_col=0, end_col=0, file_path="a.py")]
        new = [Symbol(name="foo", kind="function", body="def foo():\n    return 1  ", start_line=1, end_line=2, start_col=0, end_col=0, file_path="a.py")]
        result = diff_symbols(old, new, "a.py")
        cosmetic = [c for c in result.changes if c.kind == ChangeKind.COSMETIC]
        assert len(cosmetic) == 1

    def test_signature_changed(self) -> None:
        from semantic_code_intelligence.analysis.semantic_diff import diff_symbols, ChangeKind
        from semantic_code_intelligence.parsing.parser import Symbol
        old = [Symbol(name="foo", kind="function", body="def foo(x):\n    return x", start_line=1, end_line=2, start_col=0, end_col=0, file_path="a.py")]
        new = [Symbol(name="foo", kind="function", body="def foo(x, y):\n    return x", start_line=1, end_line=2, start_col=0, end_col=0, file_path="a.py")]
        result = diff_symbols(old, new, "a.py")
        sig_changes = [c for c in result.changes if c.kind == ChangeKind.SIGNATURE_CHANGED]
        assert len(sig_changes) == 1

    def test_diff_result_to_dict(self) -> None:
        from semantic_code_intelligence.analysis.semantic_diff import SemanticDiffResult
        result = SemanticDiffResult()
        d = result.to_dict()
        assert d["total_changes"] == 0
        assert d["structural_changes"] == 0

    def test_no_changes(self) -> None:
        from semantic_code_intelligence.analysis.semantic_diff import diff_symbols
        from semantic_code_intelligence.parsing.parser import Symbol
        sym = Symbol(name="foo", kind="function", body="def foo(): pass", start_line=1, end_line=1, start_col=0, end_col=0, file_path="a.py")
        result = diff_symbols([sym], [sym], "a.py")
        assert len(result.changes) == 0


class TestPhase41CodeGen:
    """Code generation module structure."""

    def test_codegen_request_to_dict(self) -> None:
        from semantic_code_intelligence.analysis.codegen import CodeGenRequest
        req = CodeGenRequest(prompt="Create a login function", kind="scaffold")
        d = req.to_dict()
        assert d["prompt"] == "Create a login function"
        assert d["kind"] == "scaffold"

    def test_codegen_result_to_dict(self) -> None:
        from semantic_code_intelligence.analysis.codegen import CodeGenResult
        res = CodeGenResult(generated_code="def login(): pass", success=True)
        d = res.to_dict()
        assert d["success"] is True
        assert "login" in d["generated_code"]


# =========================================================================
# Phase 42: Cross-Language Intelligence
# =========================================================================

class TestPhase42CrossLanguage:
    """Cross-language resolution and polyglot graphs."""

    def test_cross_language_edge_to_dict(self) -> None:
        from semantic_code_intelligence.analysis.cross_language import CrossLanguageEdge
        edge = CrossLanguageEdge(
            source_symbol="py_func",
            source_language="python",
            source_file="main.py",
            target_symbol="rs_func",
            target_language="rust",
            binding_type="ffi",
        )
        d = edge.to_dict()
        assert d["source_language"] == "python"
        assert d["target_language"] == "rust"
        assert d["binding_type"] == "ffi"

    def test_polyglot_dependency_to_dict(self) -> None:
        from semantic_code_intelligence.analysis.cross_language import PolyglotDependency
        dep = PolyglotDependency(
            source_file="main.py",
            source_language="python",
            target_module="codexa_core",
            target_language="rust",
            import_text="import codexa_core",
            line=1,
        )
        d = dep.to_dict()
        assert d["target_language"] == "rust"

    def test_resolver_index_file(self, tmp_path: Path) -> None:
        from semantic_code_intelligence.analysis.cross_language import CrossLanguageResolver
        py = tmp_path / "hello.py"
        py.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")
        resolver = CrossLanguageResolver()
        resolver.index_file(str(py))
        assert "python" in resolver._symbols_by_lang
        assert "greet" in resolver._symbols_by_lang["python"]

    def test_resolver_unknown_ext_skipped(self, tmp_path: Path) -> None:
        from semantic_code_intelligence.analysis.cross_language import CrossLanguageResolver
        txt = tmp_path / "notes.txt"
        txt.write_text("not code", encoding="utf-8")
        resolver = CrossLanguageResolver()
        resolver.index_file(str(txt))
        assert len(resolver._symbols_by_lang) == 0

    def test_boost_search_by_language(self) -> None:
        from semantic_code_intelligence.analysis.cross_language import boost_search_by_language
        results = [
            {"file_path": "app.py", "score": 0.8},
            {"file_path": "app.js", "score": 0.9},
            {"file_path": "utils.py", "score": 0.7},
        ]
        boosted = boost_search_by_language(results, "python", boost_factor=2.0)
        # Python files should be boosted
        assert boosted[0]["file_path"] == "app.py"  # 0.8 * 2.0 = 1.6
        assert boosted[0].get("boosted") is True

    def test_boost_no_context_language(self) -> None:
        from semantic_code_intelligence.analysis.cross_language import boost_search_by_language
        results = [{"file_path": "a.py", "score": 0.5}]
        result = boost_search_by_language(results, None)
        assert result[0]["score"] == 0.5  # unchanged

    def test_ffi_patterns_exist(self) -> None:
        from semantic_code_intelligence.analysis.cross_language import FFI_PATTERNS
        assert "python_rust" in FFI_PATTERNS
        assert "python_c" in FFI_PATTERNS
        assert "js_wasm" in FFI_PATTERNS

    def test_resolver_to_dict(self) -> None:
        from semantic_code_intelligence.analysis.cross_language import CrossLanguageResolver
        resolver = CrossLanguageResolver()
        d = resolver.to_dict()
        assert d["total_symbols"] == 0
        assert "languages" in d

    def test_resolver_index_multiple_languages(self, tmp_path: Path) -> None:
        from semantic_code_intelligence.analysis.cross_language import CrossLanguageResolver
        py = tmp_path / "main.py"
        py.write_text("def process():\n    pass\n", encoding="utf-8")
        js = tmp_path / "app.js"
        js.write_text("function render() { return null; }\n", encoding="utf-8")
        resolver = CrossLanguageResolver()
        resolver.index_file(str(py))
        resolver.index_file(str(js))
        assert "python" in resolver._symbols_by_lang
        assert "javascript" in resolver._symbols_by_lang


# =========================================================================
# Integration: Bridge server session endpoints
# =========================================================================

class TestPhase41BridgeSessionEndpoints:
    """Bridge server exposes session management endpoints."""

    def test_bridge_handler_has_session_manager(self) -> None:
        from semantic_code_intelligence.bridge.server import _BridgeHandler
        assert hasattr(_BridgeHandler, "session_manager")

    def test_bridge_server_initializes_session_manager(self, tmp_path: Path) -> None:
        _write_sample_project(tmp_path)
        from semantic_code_intelligence.bridge.server import BridgeServer
        server = BridgeServer(tmp_path)
        assert server._session_manager is not None
        assert server._session_manager.active_count == 0
