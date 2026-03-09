"""CLI command: init - Initialize a new project for semantic code intelligence."""

from __future__ import annotations

import json
from pathlib import Path

import click

from semantic_code_intelligence.config.settings import (
    AppConfig,
    init_project,
    load_config,
)
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger("cli.init")


def _generate_vscode_mcp_config(root: Path) -> bool:
    """Create .vscode/settings.json with MCP server config if not present."""
    vscode_dir = root / ".vscode"
    settings_path = vscode_dir / "settings.json"

    mcp_block = {
        "mcp": {
            "servers": {
                "codex": {
                    "command": "codex",
                    "args": ["mcp", "--path", str(root)],
                }
            }
        }
    }

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

        if "mcp" in existing:
            return False  # already configured

        existing.update(mcp_block)
        settings_path.write_text(
            json.dumps(existing, indent=4) + "\n", encoding="utf-8"
        )
        return True

    vscode_dir.mkdir(exist_ok=True)
    settings_path.write_text(
        json.dumps(mcp_block, indent=4) + "\n", encoding="utf-8"
    )
    return True


@click.command("init")
@click.argument(
    "path",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
@click.option(
    "--index",
    "auto_index",
    is_flag=True,
    default=False,
    help="Automatically index the project after initialization.",
)
@click.option(
    "--vscode",
    "setup_vscode",
    is_flag=True,
    default=False,
    help="Generate .vscode/settings.json with MCP server config.",
)
@click.pass_context
def init_cmd(ctx: click.Context, path: str, auto_index: bool, setup_vscode: bool) -> None:
    """Initialize a project for semantic code indexing.

    Creates a .codex/ directory with default configuration and an empty index.

    \b
    Quick start:
        codex init                  # basic setup
        codex init --index          # setup + build index immediately
        codex init --vscode         # setup + configure VS Code MCP
        codex init --index --vscode # full setup in one command
    """
    root = Path(path).resolve()

    # Check if already initialized
    config_dir = AppConfig.config_dir(root)
    if config_dir.exists():
        print_info(f"Project already initialized at {root}")
        print_info(f"Config directory: {config_dir}")
        # Still allow --vscode and --index on existing projects
        if setup_vscode:
            if _generate_vscode_mcp_config(root):
                print_success("VS Code MCP config written to .vscode/settings.json")
            else:
                print_info("VS Code MCP config already exists")
        if auto_index:
            _run_index(root)
        return

    try:
        config, config_path = init_project(root)
        print_success(f"Initialized project at {root}")
        print_info(f"Config file: {config_path}")
        print_info(f"Index directory: {AppConfig.index_dir(root)}")
        logger.debug("Default config: %s", config.model_dump())
    except OSError as e:
        print_error(f"Failed to initialize project: {e}")
        ctx.exit(1)
        return

    if setup_vscode:
        if _generate_vscode_mcp_config(root):
            print_success("VS Code MCP config written to .vscode/settings.json")

    if auto_index:
        _run_index(root)
    else:
        print_info("")
        print_info("Next steps:")
        print_info("  codex index    — Build the search index")
        print_info("  codex search   — Search your code")
        print_info("  codex grep     — Raw file search (no index needed)")


def _run_index(root: Path) -> None:
    """Run indexing as part of init."""
    from semantic_code_intelligence.services.indexing_service import index_project

    print_info("Building search index...")
    try:
        result = index_project(root)
        print_success(
            f"Indexed {result.chunks_stored} chunks from "
            f"{result.files_scanned} files"
        )
    except Exception as e:
        print_warning(f"Indexing failed: {e}")
        print_info("Run 'codex index' manually to build the index.")
