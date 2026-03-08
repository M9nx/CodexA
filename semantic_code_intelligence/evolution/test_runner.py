"""Test runner — executes pytest and returns structured results.

Runs ``pytest`` as a subprocess to avoid polluting the current process
with imported test modules.  Returns a structured ``TestResult`` that
the engine can use to decide whether to commit or revert.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("evolution.test_runner")


@dataclass
class TestResult:
    """Structured test-run result."""

    __test__ = False  # prevent pytest collection

    passed: bool = False
    total: int = 0
    failures: int = 0
    errors: int = 0
    output: str = ""
    return_code: int = -1

    def summary_line(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.total} tests, {self.failures} failures, {self.errors} errors"


class TestRunner:
    """Runs the project test suite via ``pytest``."""

    __test__ = False  # prevent pytest collection

    def __init__(self, project_root: Path, timeout: int = 120) -> None:
        self._root = project_root.resolve()
        self._timeout = timeout

    def run(self, extra_args: list[str] | None = None) -> TestResult:
        """Run pytest and return a :class:`TestResult`.

        Parameters
        ----------
        extra_args
            Additional pytest CLI arguments (e.g. ``["-x", "--tb=short"]``).
        """
        cmd = [
            sys.executable, "-m", "pytest",
            str(self._root / "semantic_code_intelligence" / "tests"),
            "-q", "--tb=line", "--no-header",
        ]
        if extra_args:
            cmd.extend(extra_args)

        logger.info("Running: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(self._root),
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                passed=False,
                output=f"pytest timed out after {self._timeout}s",
                return_code=-1,
            )

        result = TestResult(
            passed=proc.returncode == 0,
            output=proc.stdout + proc.stderr,
            return_code=proc.returncode,
        )

        # Parse summary line like "2258 passed, 3 warnings in 20.05s"
        result.total, result.failures, result.errors = _parse_summary(result.output)
        return result


def _parse_summary(output: str) -> tuple[int, int, int]:
    """Extract passed/failed/error counts from pytest output."""
    total = 0
    failures = 0
    errors = 0
    for line in reversed(output.splitlines()):
        line_lower = line.strip().lower()
        if "passed" in line_lower or "failed" in line_lower or "error" in line_lower:
            import re
            m_passed = re.search(r"(\d+)\s+passed", line_lower)
            m_failed = re.search(r"(\d+)\s+failed", line_lower)
            m_error = re.search(r"(\d+)\s+error", line_lower)
            if m_passed:
                total += int(m_passed.group(1))
            if m_failed:
                failures = int(m_failed.group(1))
                total += failures
            if m_error:
                errors = int(m_error.group(1))
                total += errors
            break
    return total, failures, errors
