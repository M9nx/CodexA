"""CLI command: init - Initialize a new project for semantic code intelligence."""

from __future__ import annotations

import json
from pathlib import Path

import click

from semantic_code_intelligence.config.settings import (
    AppConfig,
    init_project,
    load_config,
    save_config,
)
from semantic_code_intelligence.embeddings.model_registry import (
    MODEL_PROFILES,
    recommend_profile_for_ram,
    resolve_profile,
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
                "codexa": {
                    "command": "codexa",
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
@click.option(
    "--profile",
    "profile_name",
    type=click.Choice(["fast", "balanced", "precise"], case_sensitive=False),
    default=None,
    help="Embedding model profile: fast (tiny, low RAM), balanced (default), precise (code-optimised).",
)
@click.pass_context
def init_cmd(ctx: click.Context, path: str, auto_index: bool, setup_vscode: bool, profile_name: str | None) -> None:
    """Initialize a project for semantic code indexing.

    Creates a .codexa/ directory with default configuration and an empty index.

    \b
    Quick start:
        codexa init                  # basic setup
        codexa init --index          # setup + build index immediately
        codexa init --vscode         # setup + configure VS Code MCP
        codexa init --index --vscode # full setup in one command
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

    # Apply model profile (explicit or RAM-auto-detected)
    profile = None
    if profile_name:
        profile = resolve_profile(profile_name)
    else:
        # Auto-detect RAM and recommend
        from semantic_code_intelligence.embeddings.generator import _get_available_memory_bytes
        available = _get_available_memory_bytes()
        if available is not None:
            available_gb = available / (1024 ** 3)
            profile = recommend_profile_for_ram(available_gb)
            print_info(f"Detected {available_gb:.1f} GB available RAM → using '{profile.name}' profile ({profile.label})")

    if profile:
        config.embedding.model_name = profile.model_name
        save_config(config, root)
        print_success(f"Model profile: {profile.label} → {profile.model_name}")
        info = profile
        print_info(f"  {profile.description}")

    if setup_vscode:
        if _generate_vscode_mcp_config(root):
            print_success("VS Code MCP config written to .vscode/settings.json")

    if auto_index:
        _run_index(root)
    else:
        print_info("")
        print_info("Next steps:")
        print_info("  pip install 'codexa[ml]'  — Enable semantic indexing and vector search")
        print_info("  codexa index    — Build the search index")
        print_info("  codexa search   — Search your code")
        print_info("  codexa grep     — Raw file search (no index needed)")
        print_info("  .codexaignore   — Exclude secrets or generated files from indexing")


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
    except MemoryError as e:
        print_warning(f"Indexing failed: {e}")
        print_info("Tip: install 'codexa[ml]' for semantic indexing and use a machine with at least 2 GB available RAM, or prefer the ONNX backend.")
    except Exception as e:
        print_warning(f"Indexing failed: {e}")
        print_info("Run 'codexa index' manually to build the index.")
