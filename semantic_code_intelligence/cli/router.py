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
from semantic_code_intelligence.cli.commands.ask_cmd import ask_cmd
from semantic_code_intelligence.cli.commands.review_cmd import review_cmd
from semantic_code_intelligence.cli.commands.refactor_cmd import refactor_cmd
from semantic_code_intelligence.cli.commands.suggest_cmd import suggest_cmd
from semantic_code_intelligence.cli.commands.serve_cmd import serve_cmd
from semantic_code_intelligence.cli.commands.context_cmd import context_cmd
from semantic_code_intelligence.cli.commands.workspace_cmd import workspace_cmd
from semantic_code_intelligence.cli.commands.docs_cmd import docs_cmd
from semantic_code_intelligence.cli.commands.doctor_cmd import doctor_cmd
from semantic_code_intelligence.cli.commands.plugin_cmd import plugin_cmd
from semantic_code_intelligence.cli.commands.web_cmd import web_cmd
from semantic_code_intelligence.cli.commands.viz_cmd import viz_cmd
from semantic_code_intelligence.cli.commands.quality_cmd import quality_cmd
from semantic_code_intelligence.cli.commands.pr_summary_cmd import pr_summary_cmd
from semantic_code_intelligence.cli.commands.ci_gen_cmd import ci_gen_cmd


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
    cli.add_command(ask_cmd)
    cli.add_command(review_cmd)
    cli.add_command(refactor_cmd)
    cli.add_command(suggest_cmd)
    cli.add_command(serve_cmd)
    cli.add_command(context_cmd)
    cli.add_command(workspace_cmd)
    cli.add_command(docs_cmd)
    cli.add_command(doctor_cmd)
    cli.add_command(plugin_cmd)
    cli.add_command(web_cmd)
    cli.add_command(viz_cmd)
    cli.add_command(quality_cmd)
    cli.add_command(pr_summary_cmd)
    cli.add_command(ci_gen_cmd)
