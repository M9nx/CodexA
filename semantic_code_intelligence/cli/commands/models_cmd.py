"""CLI command: models — download, list, switch, and inspect embedding models."""

from __future__ import annotations

import json
from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config, save_config
from semantic_code_intelligence.embeddings.model_registry import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    MODEL_ALIASES,
    get_model_info,
    list_models,
    resolve_model_name,
)
from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger("cli.models")


@click.group("models")
def models_cmd() -> None:
    """Manage embedding models — download, list, switch, info."""


@models_cmd.command("list")
@click.option("--json-output", "--json", "json_mode", is_flag=True, help="Output as JSON.")
def models_list(json_mode: bool) -> None:
    """List all available embedding models and their properties."""
    all_models = list_models()

    if json_mode:
        out = [
            {
                "name": m.name,
                "display_name": m.display_name,
                "dimension": m.dimension,
                "description": m.description,
                "recommended_for": m.recommended_for,
                "backend": m.backend,
                "is_default": m.name == DEFAULT_MODEL,
            }
            for m in all_models
        ]
        click.echo(json.dumps(out, indent=2, ensure_ascii=False))
        return

    from rich.table import Table

    table = Table(title="Available Embedding Models", show_lines=True)
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Alias", style="dim")
    table.add_column("Dim", justify="right")
    table.add_column("Description")
    table.add_column("Default", justify="center")

    alias_reverse: dict[str, str] = {}
    for alias, full in MODEL_ALIASES.items():
        alias_reverse.setdefault(full, alias)

    for m in all_models:
        alias = alias_reverse.get(m.name, "—")
        is_default = "✓" if m.name == DEFAULT_MODEL else ""
        table.add_row(m.name, alias, str(m.dimension), m.description, is_default)

    console.print(table)


@models_cmd.command("info")
@click.argument("model_name")
def models_info(model_name: str) -> None:
    """Show detailed information about a specific model."""
    info = get_model_info(model_name)
    if info is None:
        print_error(f"Unknown model: {model_name}")
        raise SystemExit(1)

    from rich.panel import Panel
    from rich.text import Text

    body = Text()
    body.append(f"Name:            ", style="bold")
    body.append(f"{info.name}\n")
    body.append(f"Display name:    ", style="bold")
    body.append(f"{info.display_name}\n")
    body.append(f"Dimension:       ", style="bold")
    body.append(f"{info.dimension}\n")
    body.append(f"Backend:         ", style="bold")
    body.append(f"{info.backend}\n")
    body.append(f"Recommended for: ", style="bold")
    body.append(f"{info.recommended_for}\n")
    body.append(f"Description:     ", style="bold")
    body.append(info.description)

    console.print(Panel(body, title=f"[bold]{info.display_name}[/bold]", border_style="cyan"))


@models_cmd.command("download")
@click.argument("model_name")
@click.option("--backend", type=click.Choice(["auto", "onnx", "torch"]), default="auto")
def models_download(model_name: str, backend: str) -> None:
    """Pre-download a model so it is cached locally for offline use."""
    resolved = resolve_model_name(model_name)
    print_info(f"Downloading model: {resolved} (backend={backend}) ...")

    from semantic_code_intelligence.embeddings.generator import get_model

    try:
        model = get_model(resolved, backend=backend)
        dim = model.get_sentence_embedding_dimension()
        print_success(f"Model '{resolved}' ready — dimension={dim}")
    except Exception as exc:
        print_error(f"Failed to download model: {exc}")
        raise SystemExit(1) from exc


@models_cmd.command("switch")
@click.argument("model_name")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
def models_switch(model_name: str, path: str) -> None:
    """Switch the active embedding model for a project.

    Note: after switching models you must re-index (codex index --reindex).
    """
    resolved = resolve_model_name(model_name)
    info = get_model_info(resolved)
    if info is None:
        print_warning(f"Model '{resolved}' is not in the built-in catalogue — using as custom HF model.")

    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)
    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codex init' first.")
        raise SystemExit(1)

    config = load_config(root)
    old_model = config.embedding.model_name
    config.embedding.model_name = resolved
    save_config(config, root)
    print_success(f"Switched model: {old_model} → {resolved}")
    print_info("Run 'codex index --reindex' to rebuild the index with the new model.")
