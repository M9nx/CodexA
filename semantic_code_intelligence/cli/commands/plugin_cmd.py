"""CLI command: plugin — manage and scaffold plugins."""

from __future__ import annotations

import json as json_mod
import textwrap
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
    print_success,
)

logger = get_logger("cli.plugin")


PLUGIN_TEMPLATE = textwrap.dedent('''\
    """CodexA plugin: {name}

    {description}
    """

    from __future__ import annotations

    from typing import Any

    from semantic_code_intelligence.plugins import PluginBase, PluginHook, PluginMetadata


    class {class_name}(PluginBase):
        """Plugin implementation for {name}."""

        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                name="{name}",
                version="0.1.0",
                description="{description}",
                author="{author}",
                hooks=[{hooks}],
            )

        def activate(self, context: dict[str, Any]) -> None:
            """Called when the plugin is activated."""

        def deactivate(self) -> None:
            """Called when the plugin is deactivated."""

        def on_hook(self, hook: PluginHook, data: dict[str, Any]) -> dict[str, Any]:
            """Process hook events.

            Args:
                hook: The hook that fired.
                data: Hook-specific data. Modify and return.
            """
            # Add your logic here
            return data


    def create_plugin() -> {class_name}:
        """Factory function for plugin discovery."""
        return {class_name}()
''')


@click.group("plugin")
def plugin_cmd() -> None:
    """Manage CodexA plugins."""


@plugin_cmd.command("new")
@click.argument("name")
@click.option(
    "--description",
    "-d",
    default="A CodexA plugin",
    help="Plugin description.",
)
@click.option(
    "--author",
    "-a",
    default="",
    help="Plugin author name.",
)
@click.option(
    "--hooks",
    "-H",
    default="POST_SEARCH",
    help="Comma-separated hook names (e.g. POST_SEARCH,POST_AI).",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(file_okay=False),
    help="Output directory (default: .codex/plugins/).",
)
def plugin_new(name: str, description: str, author: str, hooks: str, output: str | None) -> None:
    """Scaffold a new plugin from template.

    Creates a ready-to-use plugin file with the correct structure.

    Examples:

        codex plugin new my-formatter

        codex plugin new lint-checker --hooks CUSTOM_VALIDATION,POST_AI

        codex plugin new metrics -o ./plugins/ -a "Your Name"
    """
    # Validate hook names
    from semantic_code_intelligence.plugins import PluginHook

    hook_names = [h.strip().upper() for h in hooks.split(",") if h.strip()]
    valid_hooks = {h.name for h in PluginHook}
    for h in hook_names:
        if h not in valid_hooks:
            print_error(f"Unknown hook: {h}. Valid hooks: {', '.join(sorted(valid_hooks))}")
            return

    hook_refs = ", ".join(f"PluginHook.{h}" for h in hook_names)

    # Build class name from plugin name
    class_name = "".join(part.capitalize() for part in name.replace("-", "_").split("_")) + "Plugin"

    content = PLUGIN_TEMPLATE.format(
        name=name,
        description=description,
        author=author,
        class_name=class_name,
        hooks=hook_refs,
    )

    # Determine output path
    if output:
        out_dir = Path(output).resolve()
    else:
        out_dir = Path(".codex/plugins").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = name.replace("-", "_") + ".py"
    filepath = out_dir / filename

    if filepath.exists():
        print_error(f"File already exists: {filepath}")
        return

    filepath.write_text(content, encoding="utf-8")
    print_success(f"Created plugin: {filepath}")
    print_info(f"Register it by placing it in .codex/plugins/ or calling PluginManager.register()")


@plugin_cmd.command("list")
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
def plugin_list(path: str, json_mode: bool) -> None:
    """List available plugins in the project.

    Scans .codex/plugins/ for discoverable plugin files.

    Examples:

        codex plugin list

        codex plugin list --json
    """
    from semantic_code_intelligence.plugins import PluginManager

    plugin_dir = Path(path) / ".codex" / "plugins"
    mgr = PluginManager()

    if plugin_dir.is_dir():
        count = mgr.discover_from_directory(plugin_dir)
    else:
        count = 0

    plugins = []
    for name in mgr.registered_plugins:
        info = mgr.get_plugin_info(name)
        if info:
            plugins.append(info)

    if json_mode:
        click.echo(json_mod.dumps({"plugins": plugins, "count": len(plugins)}, indent=2))
        return

    if not plugins:
        print_info(f"No plugins found in {plugin_dir}/")
        print_info("Create one with: codex plugin new <name>")
        return

    from rich.table import Table

    table = Table(title="Discovered Plugins")
    table.add_column("Name", style="bold")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Hooks")

    for p in plugins:
        table.add_row(
            p["name"],
            p["version"],
            p["description"],
            ", ".join(p.get("hooks", [])),
        )

    console.print(table)


@plugin_cmd.command("info")
@click.argument("name")
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
    help="Output in JSON format.",
)
def plugin_info(name: str, path: str, json_mode: bool) -> None:
    """Show details about a specific plugin.

    Examples:

        codex plugin info my-formatter
    """
    from semantic_code_intelligence.plugins import PluginManager

    plugin_dir = Path(path) / ".codex" / "plugins"
    mgr = PluginManager()

    if plugin_dir.is_dir():
        mgr.discover_from_directory(plugin_dir)

    info = mgr.get_plugin_info(name)
    if info is None:
        print_error(f"Plugin '{name}' not found.")
        return

    if json_mode:
        click.echo(json_mod.dumps(info, indent=2))
        return

    console.print(f"[bold]{info['name']}[/bold] v{info['version']}")
    if info.get("description"):
        console.print(f"  {info['description']}")
    if info.get("author"):
        console.print(f"  Author: {info['author']}")
    console.print(f"  Hooks: {', '.join(info.get('hooks', []))}")
    console.print(f"  Active: {info.get('active', False)}")
