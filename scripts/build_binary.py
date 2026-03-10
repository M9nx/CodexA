"""Build a standalone ``codexa`` binary using PyInstaller.

Usage::

    pip install pyinstaller
    python build.py          # produces  dist/codexa[.exe]
    python build.py --onedir # produces  dist/codexa/  (directory mode)

The resulting binary is fully self-contained and does not require a
Python installation on the target machine.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "semantic_code_intelligence" / "cli" / "main.py"
NAME = "codexa"
ICON = ROOT / "assets" / "icon.ico"  # optional — silently skipped if missing


def build(onedir: bool = False) -> None:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        NAME,
        "--noconfirm",
        "--clean",
    ]

    if onedir:
        cmd.append("--onedir")
    else:
        cmd.append("--onefile")

    # Include package data automatically
    cmd += [
        "--collect-all",
        "semantic_code_intelligence",
        "--collect-all",
        "sentence_transformers",
        "--hidden-import",
        "faiss",
        "--hidden-import",
        "tree_sitter",
    ]

    if ICON.exists():
        cmd += ["--icon", str(ICON)]

    cmd.append(str(ENTRY))

    print(f"[build] Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    print(f"[build] Done — output in {ROOT / 'dist'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build standalone codexa binary")
    parser.add_argument("--onedir", action="store_true", help="Directory mode instead of single file")
    args = parser.parse_args()
    build(onedir=args.onedir)


if __name__ == "__main__":
    main()
