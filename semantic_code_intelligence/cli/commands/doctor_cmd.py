"""CLI command: doctor — check environment health and dependencies."""

from __future__ import annotations

import importlib
import json as json_mod
import platform
import sys
from pathlib import Path
from typing import Any

import click

from semantic_code_intelligence import __version__
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger("cli.doctor")


def _check_python() -> dict[str, Any]:
    """Check Python version."""
    ver = platform.python_version()
    ok = sys.version_info >= (3, 11)
    return {
        "name": "Python",
        "version": ver,
        "ok": ok,
        "detail": f"Python {ver}" + ("" if ok else " (3.11+ required)"),
    }


def _check_package(pkg_name: str, import_name: str | None = None) -> dict[str, Any]:
    """Check if a Python package is importable."""
    mod_name = import_name or pkg_name
    try:
        importlib.import_module(mod_name)
        # Prefer importlib.metadata to avoid deprecated __version__ attributes
        try:
            from importlib.metadata import version as meta_version
            ver = meta_version(pkg_name)
        except Exception:
            ver = "installed"
        return {"name": pkg_name, "version": str(ver), "ok": True, "detail": f"{pkg_name} {ver}"}
    except ImportError:
        return {"name": pkg_name, "version": None, "ok": False, "detail": f"{pkg_name} not installed"}


def _check_project(path: Path) -> dict[str, Any]:
    """Check if a CodexA project is initialized at the given path."""
    config_dir = path / ".codex"
    if config_dir.is_dir():
        index_dir = config_dir / "index"
        has_index = index_dir.is_dir() and any(index_dir.iterdir()) if index_dir.is_dir() else False
        return {
            "name": "Project",
            "version": None,
            "ok": True,
            "detail": f"Initialized at {path}" + (" (indexed)" if has_index else " (not indexed)"),
        }
    return {
        "name": "Project",
        "version": None,
        "ok": False,
        "detail": f"Not initialized at {path} — run 'codex init'",
    }


def run_checks(path: Path) -> list[dict[str, Any]]:
    """Run all health checks and return results."""
    checks = [
        _check_python(),
        {"name": "CodexA", "version": __version__, "ok": True, "detail": f"CodexA {__version__}"},
        _check_package("click"),
        _check_package("pydantic"),
        _check_package("rich"),
        _check_package("sentence_transformers", "sentence_transformers"),
        _check_package("faiss", "faiss"),
        _check_package("tree_sitter", "tree_sitter"),
        _check_project(path),
    ]
    return checks


@click.command("doctor")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output results in JSON format.",
)
def doctor_cmd(path: str, json_mode: bool) -> None:
    """Check environment health, dependencies, and project status.

    Useful for debugging installation issues or verifying that all
    required packages are available.

    Examples:

        codex doctor

        codex doctor --json

        codex doctor -p /path/to/project
    """
    checks = run_checks(Path(path))

    if json_mode:
        click.echo(json_mod.dumps({"checks": checks}, indent=2))
        return

    from rich.table import Table

    table = Table(title="CodexA Health Check", show_lines=False)
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    all_ok = True
    for c in checks:
        status = "[green]OK[/green]" if c["ok"] else "[red]FAIL[/red]"
        if not c["ok"]:
            all_ok = False
        table.add_row(c["name"], status, c["detail"])

    console.print(table)
    console.print()

    if all_ok:
        print_success("All checks passed.")
    else:
        print_warning("Some checks failed. See details above.")
