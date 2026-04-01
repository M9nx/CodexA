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
    CLI_PROFILE_CHOICES,
    MODEL_PROFILES,
    ModelProfile,
    recommend_profile_for_ram,
    resolve_profile,
)
from semantic_code_intelligence.embeddings.generator import (
    BYTES_PER_GB,
    _get_available_memory_bytes,
    _get_cpu_count,
    recommend_batch_size,
)
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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
    type=click.Choice(CLI_PROFILE_CHOICES, case_sensitive=False),
    default=None,
    help=(
        "Embedding model profile: fast (low RAM), balanced (default), or precise (code-optimized). "
        "Size aliases (small/base/large) and named aliases (default/quality/code) are supported."
    ),
)
@click.option(
    "--interactive/--no-interactive",
    "interactive",
    default=False,
    help="Launch the interactive installer to choose the embedding model and batch size.",
)
@click.pass_context
def init_cmd(ctx: click.Context, path: str, auto_index: bool, setup_vscode: bool, profile_name: str | None, interactive: bool) -> None:
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
    config_path = AppConfig.config_path(root)
    if config_dir.exists() and not interactive:
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
        if config_dir.exists():
            config = load_config(root)
            print_info(f"Project already initialized at {root}")
            print_info(f"Launching interactive installer to update configuration.")
        else:
            config, config_path = init_project(root)
            print_success(f"Initialized project at {root}")
            print_info(f"Config file: {config_path}")
            print_info(f"Index directory: {AppConfig.index_dir(root)}")
            logger.debug("Default config: %s", config.model_dump())
    except OSError as e:
        print_error(f"Failed to initialize project: {e}")
        ctx.exit(1)
        return

    available_memory = _get_available_memory_bytes()
    logical_cpu_count = _get_cpu_count()
    available_gb = (
        available_memory / BYTES_PER_GB if available_memory is not None else None
    )

    recommended_profile = None
    if profile_name:
        recommended_profile = resolve_profile(profile_name)
    elif available_gb is not None:
        recommended_profile = recommend_profile_for_ram(available_gb)

    recommended_batch_size = recommend_batch_size(available_memory, logical_cpu_count)

    if interactive:
        profile_changed, batch_changed = _run_interactive_installer(
            config=config,
            available_gb=available_gb,
            cpu_count=logical_cpu_count,
            default_profile=recommended_profile or MODEL_PROFILES["balanced"],
            recommended_batch_size=recommended_batch_size,
        )
        should_save = profile_changed or batch_changed
    else:
        # Apply model profile (explicit or RAM-auto-detected)
        profile = recommended_profile
        profile_changed = False
        if profile:
            if profile_name is None and available_gb is not None:
                print_info(f"Detected {available_gb:.1f} GB available RAM → using '{profile.name}' profile ({profile.label})")

            if config.embedding.model_name != profile.model_name:
                config.embedding.model_name = profile.model_name
                profile_changed = True
            print_success(f"Model profile: {profile.label} → {profile.model_name}")
            print_info(f"  {profile.description}")

        batch_changed = recommended_batch_size != config.embedding.batch_size
        if batch_changed:
            config.embedding.batch_size = recommended_batch_size

        resource_parts: list[str] = []
        if available_gb is not None:
            resource_parts.append(f"{available_gb:.1f} GB RAM")
        if logical_cpu_count is not None:
            core_label = "CPU core" if logical_cpu_count == 1 else "CPU cores"
            resource_parts.append(f"{logical_cpu_count} {core_label}")

        batch_message_prefix = (
            f"Embedding batch size {'updated' if batch_changed else 'kept'} "
            f"at {config.embedding.batch_size}"
        )
        if resource_parts:
            print_info(
                f"{batch_message_prefix} (based on {', '.join(resource_parts)})"
            )
        else:
            print_info(
                f"{batch_message_prefix} (using default recommendation)"
            )

        should_save = profile_changed or batch_changed

    if should_save:
        save_config(config, root)

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


def _run_interactive_installer(
    config: AppConfig,
    available_gb: float | None,
    cpu_count: int | None,
    default_profile: ModelProfile,
    recommended_batch_size: int,
) -> tuple[bool, bool]:
    """Launch a text-based interactive installer for model and batch settings."""
    console = Console()
    console.print()
    console.print(Panel.fit("[bold cyan]CodexA Interactive Installer[/bold cyan]\nConfigure embedding defaults for your project.", border_style="cyan"))

    # Resource summary and suggestions
    resource_lines: list[str] = []
    if available_gb is not None:
        resource_lines.append(f"[green]{available_gb:.1f} GB[/green] available RAM detected")
    if cpu_count is not None:
        resource_lines.append(f"[green]{cpu_count} CPU cores[/green] detected")
    if resource_lines:
        console.print(" • ".join(resource_lines))
        console.print(f"Suggested profile: [bold]{default_profile.label}[/bold]")
        console.print(f"Suggested batch size: [bold]{recommended_batch_size}[/bold]")
    else:
        console.print("System resources could not be detected; keeping safe defaults.")

    # Show model options
    table = Table(title="Embedding Profiles", show_lines=True)
    table.add_column("Key", justify="center", style="cyan", no_wrap=True)
    table.add_column("Label")
    table.add_column("Model")
    table.add_column("Description")
    table.add_column("Min RAM (GB)", justify="right")
    for key in ["fast", "balanced", "precise"]:
        profile = MODEL_PROFILES[key]
        table.add_row(
            profile.name,
            profile.label,
            profile.model_name,
            profile.description,
            f"{profile.min_ram_gb:.1f}",
        )
    console.print(table)

    chosen_profile_key = click.prompt(
        "Select embedding profile",
        type=click.Choice(["fast", "balanced", "precise"], case_sensitive=False),
        default=default_profile.name,
        show_choices=False,
    )
    chosen_profile = resolve_profile(chosen_profile_key) or default_profile

    profile_changed = False
    if config.embedding.model_name != chosen_profile.model_name:
        config.embedding.model_name = chosen_profile.model_name
        profile_changed = True

    console.print()
    console.print(
        Panel.fit(
            f"[bold]Batch size[/bold] controls how many chunks are embedded at once.\n"
            f"Recommended: [cyan]{recommended_batch_size}[/cyan] (based on detection).",
            border_style="cyan",
        )
    )

    batch_input = click.prompt(
        "Embedding batch size",
        default=recommended_batch_size,
        type=int,
        show_default=True,
    )
    if batch_input < 1:
        batch_input = 1
    batch_changed = batch_input != config.embedding.batch_size
    config.embedding.batch_size = batch_input

    console.print()
    console.print(
        Panel.fit(
            f"Using profile [green]{chosen_profile.label}[/green] ({chosen_profile.model_name}) "
            f"with batch size [green]{config.embedding.batch_size}[/green].",
            border_style="green",
        )
    )

    return profile_changed, batch_changed


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
