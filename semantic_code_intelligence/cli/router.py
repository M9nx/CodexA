"""Command router - registers all CLI commands with the main group."""

from __future__ import annotations

import click

from semantic_code_intelligence.cli.commands.init_cmd import init_cmd
from semantic_code_intelligence.cli.commands.index_cmd import index_cmd
from semantic_code_intelligence.cli.commands.search_cmd import search_cmd


def register_commands(cli: click.Group) -> None:
    """Register all available CLI commands with the main click group.

    Args:
        cli: The root click.Group to attach commands to.
    """
    cli.add_command(init_cmd)
    cli.add_command(index_cmd)
    cli.add_command(search_cmd)
