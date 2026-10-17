"""Regression coverage for bandit's optional SARIF formatter noise (issue #21).

Bandit eagerly loads all its formatter entry points via stevedore when
``bandit.core.manager`` is first imported.  The SARIF entry-point module
executes ``import sarif_om`` at module import time, so on installs without
the optional ``sarif_om``/``jschema_to_python`` packages, stevedore logs
``ERROR Could not load 'sarif': No module named 'sarif_om'`` through the
``stevedore.extension`` logger.  Before, that noise leaked into every
``codexa quality`` / ``codexa metrics`` run even though codexa never
requests SARIF output.

``quality`` suppresses exactly that message while bandit machinery is in
use.  These tests lock that behavior in the worst case — a root logging
handler already active (e.g. ``logging.basicConfig()`` in a library
consumer, or pytest's logging handlers) — so deleting the suppression
turns them red.  The noisy scenario is forced deterministically by
blocking ``sarif_om`` via ``sys.modules`` poisoning (independent of
whether the package happens to be installed later) and re-executing the
bandit entry-point loading with a fresh import, restoring module state
afterwards.

Environment awareness: CI installs only ``requirements.txt``, which does
not ship bandit, so tests that re-execute bandit's machinery skip there
(they lock the behavior for environments that DO ship bandit, such as the
project venv, where bandit is a main dependency).  The clean-degradation
contract straight from issue #21 — commands must degrade without an
internal error, silently, at exit 0 — is covered in BOTH environments via
subprocess wrappers that poison ``sys.modules['bandit']``, because the
poison makes the ImportError path deterministic no matter what is
installed.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_SARIF_MARKER = "Could not load 'sarif'"

# CI environments may lack bandit entirely (requirements.txt does not ship
# it); the project venv always does.  Tests that re-execute bandit's
# machinery are meaningful only where bandit is installed; the degraded
# subprocess tests below cover the bandit-less world in both setups.
_HAS_BANDIT_INSTALLED = importlib.util.find_spec("bandit") is not None


# ---------------------------------------------------------------------------
# Fixtures — worst-case noise environment
# ---------------------------------------------------------------------------


class _RecordingHandler(logging.Handler):
    """Capture every record reaching the root logger."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def root_capture():
    """The worst case: a root logging handler active before the import."""
    handler = _RecordingHandler()
    logging.root.addHandler(handler)
    try:
        yield handler
    finally:
        logging.root.removeHandler(handler)


@pytest.fixture
def blocked_sarif_om():
    """Make ``import sarif_om`` fail exactly as if the package were absent.

    Poisoning ``sys.modules`` with ``None`` raises ImportError("import of
    sarif_om halted; None in sys.modules") regardless of whether someone
    later installs ``sarif_om`` into this venv, so the scenario stays
    deterministic.
    """
    was_present = "sarif_om" in sys.modules
    prior = sys.modules.get("sarif_om")
    sys.modules["sarif_om"] = None
    try:
        yield
    finally:
        if was_present:
            sys.modules["sarif_om"] = prior
        else:
            sys.modules.pop("sarif_om", None)


@pytest.fixture
def bandit_reload_sandbox():
    """Remove bandit (and quality, which imports it) from ``sys.modules``.

    Requires bandit to be installed — the skipif guards on the forcing
    tests already ensure they only run where it is; re-executing bandit's
    entry-point machinery (including ``MANAGER = Manager()``) is
    impossible without it.  Original module objects are restored
    afterwards so later tests see the pre-test state.  Yields the
    pre-test ``quality`` module (or ``None`` when quality had not been
    imported yet) as the baseline.
    """
    import semantic_code_intelligence.ci as ci_pkg

    saved = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "bandit" or name.startswith("bandit.")
    }
    saved_quality = sys.modules.get("semantic_code_intelligence.ci.quality")
    pop = list(saved) + (
        ["semantic_code_intelligence.ci.quality"] if saved_quality else []
    )
    for name in pop:
        sys.modules.pop(name, None)
    try:
        yield saved_quality
    finally:
        # Drop everything (re)imported during the test, restore originals.
        for name in [
            n for n in sys.modules if n == "bandit" or n.startswith("bandit.")
        ]:
            sys.modules.pop(name, None)
        for name, mod in saved.items():
            sys.modules[name] = mod
        if saved_quality is not None:
            sys.modules["semantic_code_intelligence.ci.quality"] = saved_quality
            ci_pkg.quality = saved_quality


@pytest.fixture
def clean_project(tmp_path: Path) -> Path:
    """A small, clean temporary project for CLI subprocess runs."""
    project = tmp_path / "clean-project"
    (project / "lib").mkdir(parents=True)
    (project / "lib" / "app.py").write_text(
        'def greet(name):\n    return f"Hello, {name}!"\n',
        encoding="utf-8",
    )
    return project


def _messages_with_sarif_noise(handler: _RecordingHandler) -> list[str]:
    return [r.getMessage() for r in handler.records if _SARIF_MARKER in r.getMessage()]


def _assert_capture_is_watching(handler: _RecordingHandler) -> None:
    """Guard against a test passing because the capture saw nothing at all."""
    logging.getLogger("stevedore.extension").error("silence-capture control record")
    assert any(
        "silence-capture control record" in r.getMessage() for r in handler.records
    )


def _codexa_executable() -> Path:
    if sys.platform == "win32":
        return _PROJECT_ROOT / ".venv" / "Scripts" / "codexa.exe"
    return _PROJECT_ROOT / ".venv" / "bin" / "codexa"


def _venv_python() -> Path:
    if sys.platform == "win32":
        return _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    return _PROJECT_ROOT / ".venv" / "bin" / "python"


def _assert_no_residual_sarif_suppression() -> None:
    """No ``_SuppressSarifFilter`` may remain attached anywhere covered."""
    import semantic_code_intelligence.ci.quality as quality_module

    seen_handlers: set[int] = set()
    for name in (*quality_module._SARIF_NOISE_LOGGERS, "stevedore"):
        current: logging.Logger | None = logging.getLogger(name)
        while current is not None:
            for flt in current.filters:
                assert not isinstance(flt, quality_module._SuppressSarifFilter), (
                    f"suppression left on logger {name!r}"
                )
            for handler in current.handlers:
                if id(handler) in seen_handlers:
                    continue
                seen_handlers.add(id(handler))
                for flt in handler.filters:
                    assert not isinstance(
                        flt, quality_module._SuppressSarifFilter
                    ), f"suppression left on handler {handler!r}"
            parent = current.parent
            current = parent if isinstance(parent, logging.Logger) else None


# ---------------------------------------------------------------------------
# a) Worst-case import silence — root handler active, sarif_om absent
# ---------------------------------------------------------------------------


class TestImportScenarioSilence:
    """Importing bandit machinery must not leak sarif load errors."""

    @pytest.mark.unit
    @pytest.mark.skipif(
        not _HAS_BANDIT_INSTALLED,
        reason="bandit not installed in this environment",
    )
    def test_import_quality_and_bandit_manager_without_sarif_noise(
        self,
        root_capture: _RecordingHandler,
        blocked_sarif_om: None,
        bandit_reload_sandbox: None,
    ) -> None:
        baseline_quality = bandit_reload_sandbox
        _assert_capture_is_watching(root_capture)

        # Importing quality re-executes its bandit import chain, including
        # the fresh construction of bandit.core.extension_loader.MANAGER
        # while a root handler is active — the exact leak scenario.
        quality = importlib.import_module("semantic_code_intelligence.ci.quality")
        if baseline_quality is not None:
            assert quality is not baseline_quality, (
                "expected a fresh quality module from the reload sandbox"
            )
        importlib.import_module("bandit.core.manager")

        assert _messages_with_sarif_noise(root_capture) == []
        _assert_no_residual_sarif_suppression()

        # Scenario sanity: the poisoned import really was attempted —
        # bandit's formatter manager was rebuilt without the sarif entry.
        import bandit.core.extension_loader

        assert "sarif" not in bandit.core.extension_loader.MANAGER.formatter_names


# ---------------------------------------------------------------------------
# b) Functional non-regression — bandit still analyzes real code
# ---------------------------------------------------------------------------


class TestBanditStillFunctional:
    @pytest.mark.unit
    @pytest.mark.skipif(
        not _HAS_BANDIT_INSTALLED,
        reason="bandit not installed in this environment",
    )
    def test_has_bandit_true_with_bandit_installed(self) -> None:
        from semantic_code_intelligence.ci import quality

        assert quality._HAS_BANDIT is True

    @pytest.mark.unit
    @pytest.mark.skipif(
        not _HAS_BANDIT_INSTALLED,
        reason="bandit not installed in this environment",
    )
    def test_run_bandit_scan_returns_real_findings(self, tmp_path: Path) -> None:
        from semantic_code_intelligence.ci import quality

        unsafe = tmp_path / "unsafe.py"
        unsafe.write_text(
            'def f():\n    return eval("1")\n',
            encoding="utf-8",
        )

        issues = quality.run_bandit_scan([str(unsafe)])

        assert issues, "bandit must still report findings on unsafe code"
        assert any(issue.test_id == "B307" for issue in issues), (
            "eval() must map to bandit B307"
        )
        assert all(issue.file_path == str(unsafe) for issue in issues)

    @pytest.mark.unit
    def test_run_bandit_scan_no_python_files_is_empty(self, tmp_path: Path) -> None:
        from semantic_code_intelligence.ci import quality

        text_file = tmp_path / "notes.txt"
        text_file.write_text("not code\n", encoding="utf-8")
        assert quality.run_bandit_scan([str(text_file)]) == []

    @pytest.mark.unit
    def test_analysis_restores_prior_logger_state(self, tmp_path: Path) -> None:
        from semantic_code_intelligence.ci.quality import run_bandit_scan

        scan_file = tmp_path / "stable.py"
        scan_file.write_text("x = 1\n", encoding="utf-8")
        run_bandit_scan([str(scan_file)])

        # After the analysis window the suppression must be fully torn
        # down — no residual filter on covered loggers or handlers along
        # their ancestries.
        _assert_no_residual_sarif_suppression()


# ---------------------------------------------------------------------------
# c) Analysis-window silence — the scan itself must stay covered
# ---------------------------------------------------------------------------


class TestAnalysisWindowSilence:
    @pytest.mark.unit
    def test_scan_window_suppresses_sarif_loader_error(
        self,
        root_capture: _RecordingHandler,
        blocked_sarif_om: None,
    ) -> None:
        """The stevedore ancestry is covered for as long as the scan runs.

        bandit reuses its module-global extension ``MANAGER`` during a
        scan, so the entry-point load (and its failure record) re-executes
        only when the extension machinery is reloaded.  The contract under
        test is the suppression window itself: while it is engaged,
        exactly-matching records from the covered loggers must be dropped,
        unrelated records must still get through, and the prior logger
        state must be restored on exit.
        """
        from semantic_code_intelligence.ci import quality

        _assert_capture_is_watching(root_capture)

        stevedore_log = logging.getLogger("stevedore.extension")
        with quality._suppress_sarif_noise():
            stevedore_log.error(
                "ERROR " + _SARIF_MARKER + ": No module named 'sarif_om'"
            )
            logging.getLogger("bandit").error(
                "ERROR " + _SARIF_MARKER + ": No module named 'sarif_om'"
            )
            stevedore_log.error("scan-window unrelated control record")

        assert _messages_with_sarif_noise(root_capture) == []
        assert any(
            "scan-window unrelated control record" in r.getMessage()
            for r in root_capture.records
        ), "suppression must stay narrow: unrelated records still flow"
        _assert_no_residual_sarif_suppression()

        # After exit, the filter is gone and the marker would flow again.
        stevedore_log.error("ERROR " + _SARIF_MARKER + ": post-window")
        assert any(
            _SARIF_MARKER in r.getMessage() and "post-window" in r.getMessage()
            for r in root_capture.records
        )

    @pytest.mark.unit
    @pytest.mark.skipif(
        not _HAS_BANDIT_INSTALLED,
        reason="bandit not installed in this environment",
    )
    def test_no_surviving_sarif_noise_forced_reload_scan(
        self,
        root_capture: _RecordingHandler,
        blocked_sarif_om: None,
        bandit_reload_sandbox: None,
        tmp_path: Path,
    ) -> None:
        """End-to-end within one process: fresh imports plus a real scan."""
        _assert_capture_is_watching(root_capture)

        quality = importlib.import_module("semantic_code_intelligence.ci.quality")
        importlib.import_module("bandit.core.manager")

        unsafe = tmp_path / "unsafe.py"
        unsafe.write_text('def f():\n    return eval("1")\n', encoding="utf-8")
        issues = quality.run_bandit_scan([str(unsafe)])

        assert _messages_with_sarif_noise(root_capture) == []
        assert issues and any(issue.test_id == "B307" for issue in issues)
        _assert_no_residual_sarif_suppression()


# ---------------------------------------------------------------------------
# d) CLI contract — no sarif noise anywhere in stdout/stderr, exit 0
# ---------------------------------------------------------------------------


class TestCliSilenceContract:
    @pytest.fixture(autouse=True)
    def _require_cli(self) -> None:
        if not _codexa_executable().exists():
            pytest.skip("venv codexa entry point not installed")

    def _run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(_codexa_executable()), *args],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(cwd),
        )

    @pytest.mark.integration
    def test_quality_safety_pipe_is_silent_and_zero_exit(
        self, clean_project: Path
    ) -> None:
        result = self._run(
            ["quality", "--path", str(clean_project), "--safety-only", "--pipe"],
            cwd=clean_project,
        )
        assert result.returncode == 0, (
            f"quality exit {result.returncode}\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        output = result.stdout + result.stderr
        assert _SARIF_MARKER not in output
        assert "No module named 'sarif_om'" not in output

    @pytest.mark.integration
    def test_metrics_history_pipe_is_silent_and_zero_exit(
        self, clean_project: Path
    ) -> None:
        result = self._run(
            ["metrics", "--path", str(clean_project), "--history", "1", "--pipe"],
            cwd=clean_project,
        )
        assert result.returncode == 0, (
            f"metrics exit {result.returncode}\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        output = result.stdout + result.stderr
        assert _SARIF_MARKER not in output
        assert "No module named 'sarif_om'" not in output


# ---------------------------------------------------------------------------
# e) Degraded contract — no bandit installed anywhere in the chain
# ---------------------------------------------------------------------------

_NO_BANDIT_WRAPPER = """\
import sys

# Poison the import system: any `import bandit` / `bandit.*` now raises
# ImportError (ModuleNotFoundError messages never appear either way).
sys.modules["bandit"] = None

sys.argv = {argv!r}

from semantic_code_intelligence.cli.main import main

sys.exit(main())
"""


def _assert_clean_degradation(result: subprocess.CompletedProcess[str], label: str) -> None:
    """Issue #21 contract: degrade cleanly without an internal error."""
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"{label} exit {result.returncode}\nstdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "Traceback" not in combined, f"{label} leaked a traceback:\n{combined}"
    assert "ModuleNotFoundError" not in combined, (
        f"{label} leaked a module error:\n{combined}"
    )
    assert _SARIF_MARKER not in combined, f"{label} leaked sarif noise:\n{combined}"
    assert "No module named 'sarif_om'" not in combined, (
        f"{label} leaked sarif noise:\n{combined}"
    )


class TestCliDegradedNoBanditContract:
    """Commands must degrade cleanly when bandit is absent — in both worlds.

    CI installs only ``requirements.txt`` (no bandit); the project venv
    ships bandit as a main dependency.  The ``sys.modules['bandit']``
    poison in the wrapper makes the ImportError degradation path of
    ``quality`` deterministic in either environment, so this proves —
    everywhere — that with bandit unavailable the commands still exit 0,
    print no traceback/module error, and stay free of sarif noise.
    """

    @pytest.fixture(autouse=True)
    def _require_venv_python(self) -> None:
        if not _venv_python().exists():
            pytest.skip("venv interpreter not available")

    def _run_degraded(
        self, project: Path, args: list[str], tmp_path: Path
    ) -> subprocess.CompletedProcess[str]:
        # Keep the wrapper OUTSIDE the project so the safety scan under
        # test only sees the clean fixture files.
        wrapper = tmp_path / "_no_bandit_wrapper.py"
        wrapper.write_text(
            _NO_BANDIT_WRAPPER.format(argv=["codexa", *args]),
            encoding="utf-8",
        )
        return subprocess.run(
            [str(_venv_python()), str(wrapper)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project),
        )

    @pytest.mark.integration
    def test_quality_degrades_cleanly_without_bandit(
        self, clean_project: Path, tmp_path: Path
    ) -> None:
        result = self._run_degraded(
            clean_project,
            ["quality", "--path", str(clean_project), "--safety-only", "--pipe"],
            tmp_path,
        )
        _assert_clean_degradation(result, "quality")
        # Positive evidence the command really ran and scanned the project.
        assert "PASS" in result.stdout and "1 files scanned" in result.stdout

    @pytest.mark.integration
    def test_metrics_degrades_cleanly_without_bandit(
        self, clean_project: Path, tmp_path: Path
    ) -> None:
        result = self._run_degraded(
            clean_project,
            ["metrics", "--path", str(clean_project), "--history", "1", "--pipe"],
            tmp_path,
        )
        _assert_clean_degradation(result, "metrics")
