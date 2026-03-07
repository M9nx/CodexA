"""Logging utilities for Semantic Code Intelligence."""

from __future__ import annotations

import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Shared console instances
_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "highlight": "bold magenta",
    }
)

console = Console(theme=_theme)
error_console = Console(stderr=True, theme=_theme)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the application logger with Rich formatting.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.

    Returns:
        Configured logger instance.
    """
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=error_console,
                rich_tracebacks=True,
                show_path=verbose,
                markup=True,
            )
        ],
        force=True,
    )

    logger = logging.getLogger("codex")
    logger.setLevel(level)
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a child logger under the 'codex' namespace.

    Args:
        name: Optional sub-logger name. If None, returns the root codex logger.
    """
    base = "codex"
    if name:
        return logging.getLogger(f"{base}.{name}")
    return logging.getLogger(base)


def print_success(message: str) -> None:
    """Print a success message to the console."""
    console.print(f"[success]✓[/success] {message}")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[error]✗[/error] {message}")


def print_warning(message: str) -> None:
    """Print a warning message to the console."""
    console.print(f"[warning]⚠[/warning] {message}")


def print_info(message: str) -> None:
    """Print an info message to the console."""
    console.print(f"[info]ℹ[/info] {message}")
