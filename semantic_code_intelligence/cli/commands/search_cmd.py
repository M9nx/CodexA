"""CLI command: search - Perform semantic, keyword, regex, or hybrid search."""

from __future__ import annotations

import json
from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.services.search_service import SearchMode, search_codebase
from semantic_code_intelligence.search.formatter import (
    format_results_json,
    format_results_jsonl,
    format_results_rich,
)
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_warning,
    console,
)

logger = get_logger("cli.search")


@click.command("search")
@click.argument("query", type=str)
@click.option(
    "--top-k",
    "-k",
    default=None,
    type=int,
    help="Number of results to return (overrides config).",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output results in JSON format for AI integration.",
)
@click.option(
    "--jsonl",
    "jsonl_mode",
    is_flag=True,
    default=False,
    help="Output one JSON object per line (JSONL), for piping into jq/fzf.",
)
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["semantic", "keyword", "regex", "hybrid"], case_sensitive=False),
    default="semantic",
    help="Search mode: semantic (default), keyword (BM25), regex, or hybrid (RRF).",
)
@click.option(
    "--full-section",
    "--full",
    is_flag=True,
    default=False,
    help="Expand results to show the full enclosing function/class.",
)
@click.option(
    "--no-auto-index",
    is_flag=True,
    default=False,
    help="Disable automatic indexing on first search.",
)
@click.option(
    "--case-sensitive",
    "-s",
    is_flag=True,
    default=False,
    help="Case-sensitive matching (regex mode only).",
)
@click.option(
    "--context-lines",
    "-C",
    default=0,
    type=int,
    help="Show N context lines before/after each match (grep-style).",
)
@click.option(
    "--files-only",
    "-l",
    is_flag=True,
    default=False,
    help="Print only file paths with matches (like grep -l).",
)
@click.option(
    "--files-without-match",
    "-L",
    is_flag=True,
    default=False,
    help="Print file paths without any matches (like grep -L).",
)
@click.option(
    "--line-numbers",
    "-n",
    is_flag=True,
    default=False,
    help="Prefix each output line with its line number (like grep -n).",
)
@click.pass_context
def search_cmd(
    ctx: click.Context,
    query: str,
    top_k: int | None,
    json_mode: bool,
    jsonl_mode: bool,
    path: str,
    mode: str,
    full_section: bool,
    no_auto_index: bool,
    case_sensitive: bool,
    context_lines: int,
    files_only: bool,
    files_without_match: bool,
    line_numbers: bool,
) -> None:
    """Search the indexed codebase using a natural language query.

    Supports four search modes:

    \b
      semantic  — vector similarity (default)
      keyword   — BM25 ranked keyword search
      regex     — grep-compatible regex pattern matching
      hybrid    — fused semantic + BM25 via Reciprocal Rank Fusion

    Grep-compatible flags:

    \b
        -l   show only file paths with matches
        -L   show only file paths without matches
        -n   prefix lines with line numbers
        -C N show N context lines before/after each match

    Examples:

    \b
        codex search "jwt verification"
        codex search "database connection" --mode hybrid
        codex search "def\\s+authenticate" --mode regex -n
        codex search "error handling" --mode keyword --full-section
        codex search "error handling" -k 5 --json
        codex search "TODO" --mode regex -l
        codex search "pattern" --jsonl | jq .file_path
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(
            f"Project not initialized at {root}. Run 'codex init' first."
        )
        ctx.exit(1)
        return

    config = load_config(root)
    result_count = top_k or config.search.top_k

    try:
        results = search_codebase(
            query=query,
            project_root=root,
            top_k=result_count,
            mode=mode,  # type: ignore[arg-type]
            full_section=full_section,
            auto_index=not no_auto_index,
            case_insensitive=not case_sensitive,
        )
    except FileNotFoundError:
        if json_mode:
            click.echo(format_results_json(query, [], result_count))
        elif jsonl_mode:
            pass  # no output for JSONL with no results
        else:
            print_warning(
                "Search index is empty. Run 'codex index' to build the index."
            )
        return

    # --- Grep-style output modes ---

    if files_without_match:
        # Show all indexed files NOT in the results
        matched_files = {r.file_path for r in results}
        from semantic_code_intelligence.storage.vector_store import VectorStore
        index_dir = AppConfig.index_dir(root)
        try:
            store = VectorStore.load(index_dir)
            all_files = sorted({m.file_path for m in store.metadata})
        except FileNotFoundError:
            all_files = []
        for fp in all_files:
            if fp not in matched_files:
                click.echo(fp)
        return

    if files_only:
        seen: set[str] = set()
        for r in results:
            if r.file_path not in seen:
                seen.add(r.file_path)
                click.echo(r.file_path)
        return

    # --- Machine-readable output ---

    if jsonl_mode:
        click.echo(format_results_jsonl(results))
        return

    if json_mode:
        click.echo(format_results_json(query, results, result_count))
        return

    # --- Rich / grep-style human output ---

    format_results_rich(
        query,
        results,
        line_numbers=line_numbers,
        context_lines=context_lines,
    )
