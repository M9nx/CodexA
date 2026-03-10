"""CLI command: docs — generate project documentation."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_success,
)

logger = get_logger("cli.docs")


@click.command("docs")
@click.option(
    "--output",
    "-o",
    default="docs",
    type=click.Path(file_okay=False),
    help="Output directory for generated docs.",
)
@click.option(
    "--section",
    "-s",
    type=click.Choice(["cli", "plugins", "bridge", "tools", "all"], case_sensitive=False),
    default="all",
    help="Which documentation section to generate.",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output file list as JSON.",
)
def docs_cmd(output: str, section: str, json_mode: bool) -> None:
    """Generate Markdown documentation for CodexA components.

    Produces auto-generated reference docs for CLI commands, plugin hooks,
    bridge protocol, and tool registry.

    Examples:

        codexa docs

        codexa docs --section plugins -o reference/

        codexa docs --json
    """
    import json

    from semantic_code_intelligence.docs import (
        generate_all_docs,
        generate_bridge_reference,
        generate_cli_reference,
        generate_plugin_reference,
        generate_tool_reference,
    )

    out_dir = Path(output).resolve()

    if section == "all":
        generated = generate_all_docs(out_dir)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        generated = []

        if section == "cli":
            from semantic_code_intelligence.cli.main import cli

            md = generate_cli_reference(cli)
            (out_dir / "CLI.md").write_text(md, encoding="utf-8")
            generated.append("CLI.md")
        elif section == "plugins":
            md = generate_plugin_reference()
            (out_dir / "PLUGINS.md").write_text(md, encoding="utf-8")
            generated.append("PLUGINS.md")
        elif section == "bridge":
            md = generate_bridge_reference()
            (out_dir / "BRIDGE.md").write_text(md, encoding="utf-8")
            generated.append("BRIDGE.md")
        elif section == "tools":
            md = generate_tool_reference()
            (out_dir / "TOOLS.md").write_text(md, encoding="utf-8")
            generated.append("TOOLS.md")

    if json_mode:
        click.echo(json.dumps({"output_dir": str(out_dir), "files": generated}))
    else:
        if generated:
            for f in generated:
                print_success(f"Generated {out_dir / f}")
            print_info(f"{len(generated)} doc(s) written to {out_dir}/")
        else:
            print_error("No documentation generated.")
