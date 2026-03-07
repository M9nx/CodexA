"""Command router - registers all CLI commands with the main group."""

from __future__ import annotations

import click

from semantic_code_intelligence.cli.commands.init_cmd import init_cmd
from semantic_code_intelligence.cli.commands.index_cmd import index_cmd
from semantic_code_intelligence.cli.commands.search_cmd import search_cmd
from semantic_code_intelligence.cli.commands.explain_cmd import explain_cmd
from semantic_code_intelligence.cli.commands.summary_cmd import summary_cmd
from semantic_code_intelligence.cli.commands.watch_cmd import watch_cmd
from semantic_code_intelligence.cli.commands.deps_cmd import deps_cmd


def register_commands(cli: click.Group) -> None:
    """Register all available CLI commands with the main click group.

    Args:
        cli: The root click.Group to attach commands to.
    """
    cli.add_command(init_cmd)
    cli.add_command(index_cmd)
    cli.add_command(search_cmd)
    cli.add_command(explain_cmd)
    cli.add_command(summary_cmd)
    cli.add_command(watch_cmd)
    cli.add_command(deps_cmd)
