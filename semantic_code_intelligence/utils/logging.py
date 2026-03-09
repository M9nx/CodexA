"""Logging utilities for Semantic Code Intelligence."""

from __future__ import annotations

import logging
import sys
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Detect whether the console supports Unicode safely
_UNICODE_SAFE = sys.stdout.encoding and sys.stdout.encoding.lower().startswith("utf")

_ICON_SUCCESS = "\u2713" if _UNICODE_SAFE else "OK"
_ICON_ERROR = "\u2717" if _UNICODE_SAFE else "!!"
_ICON_WARNING = "\u26a0" if _UNICODE_SAFE else "!!"
_ICON_INFO = "\u2139" if _UNICODE_SAFE else "--"

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
                markup=False,
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
    console.print(f"[success]{_ICON_SUCCESS}[/success] {message}")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[error]{_ICON_ERROR}[/error] {message}")


def print_warning(message: str) -> None:
    """Print a warning message to the console."""
    console.print(f"[warning]{_ICON_WARNING}[/warning] {message}")


def print_info(message: str) -> None:
    """Print an info message to the console."""
    console.print(f"[info]{_ICON_INFO}[/info] {message}")


def print_separator(title: str = "", style: str = "dim") -> None:
    """Print a visual separator line, optionally with a centered title."""
    if title:
        console.rule(f"[bold]{title}[/bold]", style=style)
    else:
        console.rule(style=style)


def print_header(title: str, subtitle: str = "") -> None:
    """Print a styled section header."""
    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    if subtitle:
        console.print(f"  [dim]{subtitle}[/dim]")
    console.print()
