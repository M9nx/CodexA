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
    MODEL_PROFILES,
    get_model_info,
    list_models,
    recommend_profile_for_ram,
    resolve_model_name,
    resolve_profile,
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

    Note: after switching models you must re-index (codexa index --reindex).
    """
    resolved = resolve_model_name(model_name)
    info = get_model_info(resolved)
    if info is None:
        print_warning(f"Model '{resolved}' is not in the built-in catalogue — using as custom HF model.")

    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)
    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codexa init' first.")
        raise SystemExit(1)

    config = load_config(root)
    old_model = config.embedding.model_name
    config.embedding.model_name = resolved
    save_config(config, root)
    print_success(f"Switched model: {old_model} → {resolved}")
    print_info("Run 'codexa index --reindex' to rebuild the index with the new model.")


@models_cmd.command("profiles")
@click.option("--json-output", "--json", "json_mode", is_flag=True, help="Output as JSON.")
def models_profiles(json_mode: bool) -> None:
    """Show available model profiles (fast / balanced / precise)."""
    from semantic_code_intelligence.embeddings.generator import _get_available_memory_bytes

    available = _get_available_memory_bytes()
    available_gb = available / (1024 ** 3) if available else None
    recommended = recommend_profile_for_ram(available_gb) if available_gb else None

    if json_mode:
        out = []
        for p in MODEL_PROFILES.values():
            info = get_model_info(p.model_name)
            out.append({
                "profile": p.name,
                "label": p.label,
                "model": p.model_name,
                "dimension": info.dimension if info else 0,
                "min_ram_gb": p.min_ram_gb,
                "description": p.description,
                "recommended": recommended is not None and p.name == recommended.name,
            })
        click.echo(json.dumps(out, indent=2, ensure_ascii=False))
        return

    from rich.table import Table

    table = Table(title="Model Profiles", show_lines=True)
    table.add_column("Profile", style="bold cyan")
    table.add_column("Model", style="dim")
    table.add_column("Dim", justify="right")
    table.add_column("RAM", justify="right")
    table.add_column("Description")
    table.add_column("", justify="center")

    for p in MODEL_PROFILES.values():
        info = get_model_info(p.model_name)
        dim = str(info.dimension) if info else "?"
        ram = f"≥{p.min_ram_gb:.1f} GB"
        is_rec = "⭐" if recommended and p.name == recommended.name else ""
        table.add_row(p.label, p.model_name, dim, ram, p.description, is_rec)

    console.print(table)
    if available_gb:
        print_info(f"Detected RAM: {available_gb:.1f} GB — recommended profile marked with ⭐")
    print_info("Use: codexa init --profile <fast|balanced|precise>")


@models_cmd.command("benchmark")
@click.option("--path", "-p", default=".", type=click.Path(exists=True, file_okay=False, resolve_path=True), help="Project root.")
@click.option("--json-output", "--json", "json_mode", is_flag=True, help="Output as JSON.")
def models_benchmark(path: str, json_mode: bool) -> None:
    """Benchmark embedding models against your codebase.

    Encodes a sample of your code with each built-in model and reports
    speed, dimension, and relative quality indicators.
    """
    import time

    root = Path(path).resolve()

    # Gather a sample of code chunks
    print_info("Collecting code sample from project...")
    sample_texts = _collect_sample_texts(root, max_chunks=50)
    if not sample_texts:
        print_error("No indexable files found. Initialize and index a project first.")
        raise SystemExit(1)

    print_info(f"Benchmarking {len(AVAILABLE_MODELS)} models with {len(sample_texts)} code chunks...\n")

    results = []
    for model_name, info in AVAILABLE_MODELS.items():
        try:
            from semantic_code_intelligence.embeddings.generator import get_model, _model_cache

            # Clear cache for fair timing
            cache_keys = [k for k in _model_cache if k.startswith(model_name)]
            for k in cache_keys:
                del _model_cache[k]

            t0 = time.perf_counter()
            model = get_model(model_name, backend="auto")
            load_time = time.perf_counter() - t0

            t0 = time.perf_counter()
            model.encode(sample_texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
            encode_time = time.perf_counter() - t0

            chunks_per_sec = len(sample_texts) / encode_time if encode_time > 0 else 0
            results.append({
                "model": model_name,
                "display_name": info.display_name,
                "dimension": info.dimension,
                "load_time_s": round(load_time, 2),
                "encode_time_s": round(encode_time, 3),
                "chunks_per_sec": round(chunks_per_sec, 1),
                "size_mb": info.size_mb,
                "status": "ok",
            })
            print_success(f"  {info.display_name}: {chunks_per_sec:.0f} chunks/s, dim={info.dimension}")
        except Exception as exc:
            results.append({
                "model": model_name,
                "display_name": info.display_name,
                "dimension": info.dimension,
                "load_time_s": 0,
                "encode_time_s": 0,
                "chunks_per_sec": 0,
                "size_mb": info.size_mb,
                "status": f"error: {exc}",
            })
            print_warning(f"  {info.display_name}: skipped ({exc})")

    if json_mode:
        click.echo(json.dumps(results, indent=2, ensure_ascii=False))
        return

    from rich.table import Table

    table = Table(title="Model Benchmark Results", show_lines=True)
    table.add_column("Model", style="bold cyan")
    table.add_column("Dim", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Load", justify="right")
    table.add_column("Encode", justify="right")
    table.add_column("Speed", justify="right", style="green")
    table.add_column("Status")

    for r in results:
        table.add_row(
            r["display_name"],
            str(r["dimension"]),
            f"{r['size_mb']} MB",
            f"{r['load_time_s']}s",
            f"{r['encode_time_s']}s",
            f"{r['chunks_per_sec']} c/s" if r["status"] == "ok" else "—",
            "✓" if r["status"] == "ok" else r["status"],
        )

    console.print(table)
    print_info(f"\nBenchmarked with {len(sample_texts)} chunks from {root}")
    print_info("Switch model: codexa models switch <name>")


def _collect_sample_texts(root: Path, max_chunks: int = 50) -> list[str]:
    """Collect a small sample of code text from the project for benchmarking."""
    from semantic_code_intelligence.config.settings import load_config

    config = load_config(root)
    extensions = set(config.index.extensions)
    texts: list[str] = []

    for dirpath, _dirnames, filenames in __import__("os").walk(root):
        dp = Path(dirpath)
        # Skip hidden/ignored dirs
        try:
            rel = dp.relative_to(root)
        except ValueError:
            continue
        if any(part.startswith(".") or part in {"node_modules", "__pycache__", "venv", ".venv"} for part in rel.parts):
            continue
        for fname in filenames:
            fp = dp / fname
            if fp.suffix not in extensions:
                continue
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            # Take first 512 chars as a chunk
            if len(content) > 100:
                texts.append(content[:512])
            if len(texts) >= max_chunks:
                return texts
    return texts
