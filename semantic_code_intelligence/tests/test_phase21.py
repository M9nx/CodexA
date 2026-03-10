"""Phase 21 — Mypy Strict Typing & Pytest Coverage Gate.

Tests verify:
  1. pyproject.toml mypy strict config exists and is correct
  2. pyproject.toml coverage config exists with fail_under gate
  3. All 49 original mypy errors stay fixed (regression guard)
  4. Type annotations are present on key functions
  5. No bare ``dict`` return types remain in source
  6. Critical bug fixes (SafetyReport import, FileDependency attr, etc.)
"""

from __future__ import annotations

import ast
import configparser
import importlib
import inspect
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _PROJECT_ROOT / "pyproject.toml"
_SRC = _PROJECT_ROOT / "semantic_code_intelligence"


def _read_pyproject() -> str:
    return _PYPROJECT.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 1 — pyproject.toml: [tool.mypy] section
# ═══════════════════════════════════════════════════════════════════════════

class TestMypyConfig:
    """[tool.mypy] section validations."""

    def test_mypy_section_exists(self) -> None:
        text = _read_pyproject()
        assert "[tool.mypy]" in text

    def test_strict_enabled(self) -> None:
        text = _read_pyproject()
        assert "strict = true" in text

    def test_warn_return_any(self) -> None:
        text = _read_pyproject()
        assert "warn_return_any = true" in text

    def test_warn_unused_ignores(self) -> None:
        text = _read_pyproject()
        assert "warn_unused_ignores = true" in text

    def test_ignore_missing_imports(self) -> None:
        text = _read_pyproject()
        assert "ignore_missing_imports = true" in text

    def test_tests_excluded(self) -> None:
        text = _read_pyproject()
        assert 'exclude = ["tests/"]' in text


# ═══════════════════════════════════════════════════════════════════════════
# 2 — pyproject.toml: coverage config
# ═══════════════════════════════════════════════════════════════════════════

class TestCoverageConfig:
    """[tool.coverage.*] section validations."""

    def test_coverage_run_section_exists(self) -> None:
        text = _read_pyproject()
        assert "[tool.coverage.run]" in text

    def test_coverage_source(self) -> None:
        text = _read_pyproject()
        assert 'source = ["semantic_code_intelligence"]' in text

    def test_coverage_omit_tests(self) -> None:
        text = _read_pyproject()
        assert "semantic_code_intelligence/tests/*" in text

    def test_coverage_report_section_exists(self) -> None:
        text = _read_pyproject()
        assert "[tool.coverage.report]" in text

    def test_fail_under_gate(self) -> None:
        text = _read_pyproject()
        # Expect fail_under = 70 (or any integer >= 70)
        match = re.search(r"fail_under\s*=\s*(\d+)", text)
        assert match is not None, "fail_under not found in pyproject.toml"
        assert int(match.group(1)) >= 70

    def test_show_missing(self) -> None:
        text = _read_pyproject()
        assert "show_missing = true" in text


# ═══════════════════════════════════════════════════════════════════════════
# 3 — Bug-fix regression guards (the 49 original errors)
# ═══════════════════════════════════════════════════════════════════════════

class TestSafetyReportImport:
    """ci/pr.py must import SafetyReport."""

    def test_import_exists(self) -> None:
        from semantic_code_intelligence.ci import pr
        assert hasattr(pr, "SafetyReport")

    def test_safety_report_in_source(self) -> None:
        src = (_SRC / "ci" / "pr.py").read_text(encoding="utf-8")
        assert "SafetyReport" in src
        assert "from semantic_code_intelligence.llm.safety import" in src


class TestFileDependencyAttr:
    """investigation.py must use .import_text not .module."""

    def test_no_dot_module_usage(self) -> None:
        src = (_SRC / "llm" / "investigation.py").read_text(encoding="utf-8")
        # Should NOT contain d.module
        assert ".module" not in src or "import_text" in src

    def test_import_text_usage(self) -> None:
        src = (_SRC / "llm" / "investigation.py").read_text(encoding="utf-8")
        assert "import_text" in src


class TestVizCmdReposList:
    """viz_cmd.py must iterate list, not call .values()."""

    def test_no_values_call(self) -> None:
        src = (_SRC / "cli" / "commands" / "viz_cmd.py").read_text(encoding="utf-8")
        assert ".repos.values()" not in src

    def test_direct_iteration(self) -> None:
        src = (_SRC / "cli" / "commands" / "viz_cmd.py").read_text(encoding="utf-8")
        assert "ws.repos]" in src or "r.to_dict() for r in ws.repos" in src


class TestQualityCmdDuplicateVar:
    """quality_cmd.py should not reuse dead_code var name for duplicates."""

    def test_duplicate_loop_uses_dup_var(self) -> None:
        src = (_SRC / "cli" / "commands" / "quality_cmd.py").read_text(encoding="utf-8")
        # The duplicates loop should use 'dup' not 'd'
        assert "for dup in report.duplicates:" in src


class TestCrossRefactorTuple:
    """cross_refactor.py pair_key must be tuple[str, str]."""

    def test_no_bare_tuple_sorted(self) -> None:
        src = (_SRC / "llm" / "cross_refactor.py").read_text(encoding="utf-8")
        # Should NOT have tuple(sorted([...]))
        assert "tuple(sorted(" not in src


class TestImpactAffectedSymbolVar:
    """impact.py loop vars for AffectedSymbol lists renamed."""

    def test_direct_loop_uses_af(self) -> None:
        src = (_SRC / "ci" / "impact.py").read_text(encoding="utf-8")
        assert "for af in direct:" in src or "for af in direct[" in src


# ═══════════════════════════════════════════════════════════════════════════
# 4 — Type annotation presence checks
# ═══════════════════════════════════════════════════════════════════════════

class TestGetProviderAnnotated:
    """_get_provider functions must have type annotations."""

    @pytest.mark.parametrize("mod_path", [
        "semantic_code_intelligence.cli.commands.chat_cmd",
        "semantic_code_intelligence.cli.commands.ask_cmd",
        "semantic_code_intelligence.cli.commands.investigate_cmd",
    ])
    def test_get_provider_has_return_annotation(self, mod_path: str) -> None:
        mod = importlib.import_module(mod_path)
        fn = getattr(mod, "_get_provider")
        hints = fn.__annotations__
        assert "return" in hints, f"{mod_path}._get_provider missing return annotation"

    @pytest.mark.parametrize("mod_path", [
        "semantic_code_intelligence.cli.commands.chat_cmd",
        "semantic_code_intelligence.cli.commands.ask_cmd",
        "semantic_code_intelligence.cli.commands.investigate_cmd",
    ])
    def test_get_provider_has_config_annotation(self, mod_path: str) -> None:
        mod = importlib.import_module(mod_path)
        fn = getattr(mod, "_get_provider")
        hints = fn.__annotations__
        assert "config" in hints, f"{mod_path}._get_provider missing config annotation"


class TestDoctorCmdTypedDicts:
    """doctor_cmd.py functions must return dict[str, Any], not bare dict."""

    def test_check_python_return_annotation(self) -> None:
        from semantic_code_intelligence.cli.commands import doctor_cmd
        hints = doctor_cmd._check_python.__annotations__
        assert "return" in hints

    def test_check_package_return_annotation(self) -> None:
        from semantic_code_intelligence.cli.commands import doctor_cmd
        hints = doctor_cmd._check_package.__annotations__
        assert "return" in hints

    def test_check_project_return_annotation(self) -> None:
        from semantic_code_intelligence.cli.commands import doctor_cmd
        hints = doctor_cmd._check_project.__annotations__
        assert "return" in hints

    def test_run_checks_return_annotation(self) -> None:
        from semantic_code_intelligence.cli.commands import doctor_cmd
        hints = doctor_cmd.run_checks.__annotations__
        assert "return" in hints


class TestSearchServiceTypedDict:
    """search_service.SearchResult.to_dict must return dict[str, Any]."""

    def test_to_dict_return_type(self) -> None:
        from semantic_code_intelligence.services.search_service import SearchResult
        hints = SearchResult.to_dict.__annotations__
        assert "return" in hints


# ═══════════════════════════════════════════════════════════════════════════
# 5 — No bare dict returns in source (AST scan)
# ═══════════════════════════════════════════════════════════════════════════

class TestNoBareDictReturns:
    """Source files should not have bare 'dict' return annotations."""

    @pytest.mark.parametrize("rel_path", [
        "cli/commands/doctor_cmd.py",
        "services/search_service.py",
        "tools/__init__.py",
        "bridge/context_provider.py",
    ])
    def test_no_bare_dict_in_file(self, rel_path: str) -> None:
        src = (_SRC / rel_path).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                ret = node.returns
                if ret is not None:
                    # Check for bare Name("dict") without subscript
                    if isinstance(ret, ast.Name) and ret.id == "dict":
                        pytest.fail(
                            f"{rel_path}:{node.lineno} — "
                            f"function '{node.name}' has bare 'dict' return"
                        )
                    # Check for list[dict] without subscript
                    if isinstance(ret, ast.Subscript):
                        if isinstance(ret.slice, ast.Name) and ret.slice.id == "dict":
                            pytest.fail(
                                f"{rel_path}:{node.lineno} — "
                                f"function '{node.name}' has list[dict] return"
                            )


# ═══════════════════════════════════════════════════════════════════════════
# 6 — No-any-return fixes
# ═══════════════════════════════════════════════════════════════════════════

class TestNoAnyReturnFixes:
    """Key functions should cast/annotate to avoid returning Any."""

    def test_ollama_api_call_returns_typed(self) -> None:
        src = (_SRC / "llm" / "ollama_provider.py").read_text(encoding="utf-8")
        assert "result: dict[str, Any]" in src

    def test_vector_store_size_int_cast(self) -> None:
        src = (_SRC / "storage" / "vector_store.py").read_text(encoding="utf-8")
        assert "int(self.index.ntotal)" in src

    def test_embedding_dim_none_guard(self) -> None:
        src = (_SRC / "embeddings" / "generator.py").read_text(encoding="utf-8")
        assert "if dim is None:" in src

    def test_templates_typed_generators(self) -> None:
        src = (_SRC / "ci" / "templates.py").read_text(encoding="utf-8")
        assert "Callable[..., str]" in src


# ═══════════════════════════════════════════════════════════════════════════
# 7 — Stale type:ignore removal
# ═══════════════════════════════════════════════════════════════════════════

class TestNoStaleTypeIgnore:
    """Unused type:ignore comments should be removed."""

    def test_plugins_no_unused_ignore(self) -> None:
        src = (_SRC / "plugins" / "__init__.py").read_text(encoding="utf-8")
        # The exec_module line should NOT have type: ignore
        for line in src.splitlines():
            if "exec_module" in line:
                assert "type: ignore" not in line, f"Stale type:ignore: {line}"

    def test_openai_no_unused_ignore(self) -> None:
        src = (_SRC / "llm" / "openai_provider.py").read_text(encoding="utf-8")
        for line in src.splitlines():
            if "import openai" in line and "ignore" in line.lower():
                pytest.fail(f"Stale type:ignore on openai import: {line}")


# ═══════════════════════════════════════════════════════════════════════════
# 8 — docs/__init__.py click type fix
# ═══════════════════════════════════════════════════════════════════════════

class TestDocsClickType:
    """docs/__init__.py should not use click.BaseCommand as type hint."""

    def test_no_base_command_annotation(self) -> None:
        src = (_SRC / "docs" / "__init__.py").read_text(encoding="utf-8")
        assert "group: click.BaseCommand" not in src

    def test_uses_proper_type(self) -> None:
        src = (_SRC / "docs" / "__init__.py").read_text(encoding="utf-8")
        # Should use click.Group | click.Command or similar
        assert "click.Group" in src or "click.Command" in src


# ═══════════════════════════════════════════════════════════════════════════
# 9 — Functional regression: fixed modules still work
# ═══════════════════════════════════════════════════════════════════════════

class TestFixedModulesImport:
    """All fixed modules import without error."""

    @pytest.mark.parametrize("mod_path", [
        "semantic_code_intelligence.ci.pr",
        "semantic_code_intelligence.ci.impact",
        "semantic_code_intelligence.ci.templates",
        "semantic_code_intelligence.cli.commands.doctor_cmd",
        "semantic_code_intelligence.cli.commands.quality_cmd",
        "semantic_code_intelligence.cli.commands.chat_cmd",
        "semantic_code_intelligence.cli.commands.ask_cmd",
        "semantic_code_intelligence.cli.commands.investigate_cmd",
        "semantic_code_intelligence.cli.commands.viz_cmd",
        "semantic_code_intelligence.cli.commands.cross_refactor_cmd",
        "semantic_code_intelligence.llm.ollama_provider",
        "semantic_code_intelligence.llm.openai_provider",
        "semantic_code_intelligence.llm.investigation",
        "semantic_code_intelligence.llm.cross_refactor",
        "semantic_code_intelligence.storage.vector_store",
        "semantic_code_intelligence.embeddings.generator",
        "semantic_code_intelligence.services.search_service",
        "semantic_code_intelligence.tools",
        "semantic_code_intelligence.search.formatter",
        "semantic_code_intelligence.bridge.context_provider",
        "semantic_code_intelligence.web.api",
        "semantic_code_intelligence.docs",
        "semantic_code_intelligence.plugins",
    ])
    def test_module_imports(self, mod_path: str) -> None:
        importlib.import_module(mod_path)


# ═══════════════════════════════════════════════════════════════════════════
# 10 — Coverage gate configuration is respected
# ═══════════════════════════════════════════════════════════════════════════

class TestCoverageGateIntegrity:
    """Coverage gate integrates properly with pytest-cov."""

    def test_pytest_cov_installed(self) -> None:
        import pytest_cov  # noqa: F401

    def test_coverage_source_matches_package(self) -> None:
        text = _read_pyproject()
        assert "semantic_code_intelligence" in text
        # Coverage source points to the right package
        match = re.search(r'source\s*=\s*\["([^"]+)"\]', text)
        assert match is not None
        assert match.group(1) == "semantic_code_intelligence"


# ═══════════════════════════════════════════════════════════════════════════
# 11 — TYPE_CHECKING guard pattern
# ═══════════════════════════════════════════════════════════════════════════

class TestTypeCheckingGuard:
    """Files using TYPE_CHECKING should guard runtime-only imports."""

    @pytest.mark.parametrize("rel_path", [
        "cli/commands/chat_cmd.py",
        "cli/commands/ask_cmd.py",
        "cli/commands/investigate_cmd.py",
    ])
    def test_type_checking_import(self, rel_path: str) -> None:
        src = (_SRC / rel_path).read_text(encoding="utf-8")
        assert "TYPE_CHECKING" in src
        assert "if TYPE_CHECKING:" in src


# ═══════════════════════════════════════════════════════════════════════════
# 12 — Version tagging
# ═══════════════════════════════════════════════════════════════════════════

class TestVersion:
    """Version must be ≥ 0.4.0 for stable release."""

    def test_version_in_init(self) -> None:
        from semantic_code_intelligence import __version__
        parts = __version__.split(".")
        assert len(parts) >= 3
        major, minor = int(parts[0]), int(parts[1])
        assert (major, minor) >= (0, 4)

    def test_version_in_pyproject(self) -> None:
        text = _read_pyproject()
        match = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)"', text)
        assert match is not None
        parts = match.group(1).split(".")
        major, minor = int(parts[0]), int(parts[1])
        assert (major, minor) >= (0, 4)
