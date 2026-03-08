"""Commit manager — handles git add / commit / revert for evolution patches.

All git operations run as subprocesses against the project root.
The manager only commits files that the evolution loop explicitly touched.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("evolution.commit_manager")


class CommitManager:
    """Thin wrapper around git for safe commit/revert cycles."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def git_diff(self, staged: bool = False) -> str:
        """Return the current ``git diff`` output (unstaged by default)."""
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--staged")
        return self._run(cmd)

    def git_diff_stat(self) -> str:
        """Return the ``--stat`` summary of uncommitted changes."""
        return self._run(["git", "diff", "--stat"])

    def has_changes(self) -> bool:
        """Return ``True`` if there are uncommitted changes."""
        output = self._run(["git", "status", "--porcelain"])
        return bool(output.strip())

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    def stage_files(self, paths: list[str]) -> None:
        """``git add`` a list of relative file paths."""
        if not paths:
            return
        self._run(["git", "add", "--"] + paths)

    def commit(self, message: str) -> str:
        """Create a commit with the given message.  Returns the short SHA."""
        self._run(["git", "commit", "-m", message])
        sha = self._run(["git", "rev-parse", "--short", "HEAD"]).strip()
        logger.info("Committed %s: %s", sha, message)
        return sha

    def revert_files(self, paths: list[str]) -> None:
        """Restore files to their last committed state."""
        if not paths:
            return
        self._run(["git", "checkout", "--"] + paths)
        logger.info("Reverted %d file(s).", len(paths))

    def stash_push(self, message: str = "evolution-wip") -> None:
        """Stash current changes."""
        self._run(["git", "stash", "push", "-m", message])

    def stash_pop(self) -> None:
        """Pop the most recent stash."""
        self._run(["git", "stash", "pop"])

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _run(self, cmd: list[str]) -> str:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self._root),
        )
        if proc.returncode != 0 and "nothing to commit" not in proc.stdout:
            logger.debug("git stderr: %s", proc.stderr.strip())
        return proc.stdout
