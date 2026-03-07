"""CLI command: workspace — manage multi-repo workspaces."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import click

from semantic_code_intelligence.utils.logging import (
    console,
    get_logger,
    print_error,
    print_info,
    print_success,
    print_warning,
)

logger = get_logger("cli.workspace")


@click.group("workspace")
def workspace_cmd() -> None:
    """Manage multi-repository workspaces."""


@workspace_cmd.command("init")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Workspace root directory.",
)
def workspace_init(path: str) -> None:
    """Initialise a new workspace."""
    from semantic_code_intelligence.workspace import Workspace

    ws = Workspace.load_or_create(Path(path))
    ws.save()
    print_success(f"Workspace initialised at {ws.root}")


@workspace_cmd.command("add")
@click.argument("name")
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Workspace root directory.",
)
def workspace_add(name: str, repo_path: str, path: str) -> None:
    """Register a repository in the workspace."""
    from semantic_code_intelligence.workspace import Workspace

    try:
        ws = Workspace.load(Path(path))
    except FileNotFoundError:
        print_error("Workspace not initialised. Run 'codex workspace init' first.")
        return

    try:
        ws.add_repo(name, Path(repo_path))
        ws.save()
        print_success(f"Added repository '{name}' → {repo_path}")
    except (ValueError, FileNotFoundError) as exc:
        print_error(str(exc))


@workspace_cmd.command("remove")
@click.argument("name")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Workspace root directory.",
)
def workspace_remove(name: str, path: str) -> None:
    """Unregister a repository from the workspace."""
    from semantic_code_intelligence.workspace import Workspace

    try:
        ws = Workspace.load(Path(path))
    except FileNotFoundError:
        print_error("Workspace not initialised.")
        return

    if ws.remove_repo(name):
        ws.save()
        print_success(f"Removed repository '{name}'.")
    else:
        print_warning(f"Repository '{name}' not found in workspace.")


@workspace_cmd.command("list")
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Workspace root directory.",
)
def workspace_list(json_mode: bool, path: str) -> None:
    """List all repositories in the workspace."""
    from semantic_code_intelligence.workspace import Workspace

    try:
        ws = Workspace.load(Path(path))
    except FileNotFoundError:
        print_error("Workspace not initialised.")
        return

    if json_mode:
        click.echo(json_mod.dumps(ws.summary(), indent=2))
    else:
        repos = ws.repos
        if not repos:
            print_info("No repositories registered.")
            return
        from rich.table import Table

        table = Table(title=f"Workspace: {ws.root}")
        table.add_column("Name", style="cyan")
        table.add_column("Path")
        table.add_column("Files", justify="right")
        table.add_column("Vectors", justify="right")
        for r in repos:
            table.add_row(r.name, r.path, str(r.file_count), str(r.vector_count))
        console.print(table)


@workspace_cmd.command("index")
@click.option(
    "--repo",
    "-r",
    default=None,
    help="Index only this repository (by name).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force full re-index.",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Workspace root directory.",
)
def workspace_index(repo: str | None, force: bool, path: str) -> None:
    """Index repositories in the workspace."""
    from semantic_code_intelligence.workspace import Workspace

    try:
        ws = Workspace.load(Path(path))
    except FileNotFoundError:
        print_error("Workspace not initialised.")
        return

    if repo:
        try:
            result = ws.index_repo(repo, force=force)
            ws.save()
            print_success(
                f"[{repo}] Indexed {result.files_indexed} files "
                f"({result.chunks_created} chunks, {result.total_vectors} vectors)"
            )
        except KeyError:
            print_error(f"Repository '{repo}' not registered.")
    else:
        results = ws.index_all(force=force)
        for name, result in results.items():
            print_success(
                f"[{name}] Indexed {result.files_indexed} files "
                f"({result.chunks_created} chunks, {result.total_vectors} vectors)"
            )


@workspace_cmd.command("search")
@click.argument("query")
@click.option("--top-k", "-k", default=10, type=int, help="Number of results.")
@click.option("--threshold", "-t", default=0.3, type=float, help="Minimum score.")
@click.option(
    "--repo",
    "-r",
    multiple=True,
    help="Restrict to specific repos (repeatable).",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output in JSON format.",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Workspace root directory.",
)
def workspace_search(
    query: str,
    top_k: int,
    threshold: float,
    repo: tuple[str, ...],
    json_mode: bool,
    path: str,
) -> None:
    """Search across all workspace repositories."""
    from semantic_code_intelligence.workspace import Workspace

    try:
        ws = Workspace.load(Path(path))
    except FileNotFoundError:
        print_error("Workspace not initialised.")
        return

    repos = list(repo) if repo else None
    results = ws.search(query, top_k=top_k, threshold=threshold, repos=repos)

    if json_mode:
        click.echo(json_mod.dumps(results, indent=2))
    else:
        if not results:
            print_info("No results found.")
            return
        from rich.panel import Panel
        from rich.syntax import Syntax

        for r in results:
            lang = r.get("language", "text")
            syn = Syntax(r["content"], lang, line_numbers=True, start_line=r["start_line"])
            title = f"[{r['repo']}] {r['file_path']}:{r['start_line']}-{r['end_line']}  (score: {r['score']})"
            console.print(Panel(syn, title=title, border_style="green"))
