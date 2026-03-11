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
    "--hybrid",
    "hybrid_shorthand",
    is_flag=True,
    default=False,
    help="Shorthand for --mode hybrid.",
)
@click.option(
    "--sem",
    "sem_shorthand",
    is_flag=True,
    default=False,
    help="Shorthand for --mode semantic.",
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
@click.option(
    "--scores",
    is_flag=True,
    default=False,
    help="Prefix each result with its relevance score (e.g. [0.847]).",
)
@click.option(
    "--snippet-length",
    type=int,
    default=None,
    help="Truncate snippet content to N characters.",
)
@click.option(
    "--no-snippet",
    is_flag=True,
    default=False,
    help="Omit snippet content — output metadata only.",
)
@click.option(
    "--exclude",
    "exclude_glob",
    default=None,
    type=str,
    help="Exclude files matching this glob pattern from results.",
)
@click.option(
    "--no-ignore",
    is_flag=True,
    default=False,
    help="Include files normally ignored by .gitignore / .codexaignore.",
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
    hybrid_shorthand: bool,
    sem_shorthand: bool,
    full_section: bool,
    no_auto_index: bool,
    case_sensitive: bool,
    context_lines: int,
    files_only: bool,
    files_without_match: bool,
    line_numbers: bool,
    scores: bool,
    snippet_length: int | None,
    no_snippet: bool,
    exclude_glob: str | None,
    no_ignore: bool,
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

    Output control:

    \b
        --scores          prefix each result with [0.847] relevance score
        --snippet-length  truncate snippet to N characters
        --no-snippet      metadata only (no code content)
        --exclude         exclude files matching a glob
        --no-ignore       include ignored files

    Examples:

    \b
        codexa search "jwt verification"
        codexa search "database connection" --mode hybrid
        codexa search "def\\s+authenticate" --mode regex -n
        codexa search "error handling" --mode keyword --full-section
        codexa search "error handling" -k 5 --json
        codexa search "TODO" --mode regex -l
        codexa search "pattern" --jsonl | jq .file_path
        codexa search "login" --scores --snippet-length 200
        codexa search "auth" --no-snippet --jsonl
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(
            f"Project not initialized at {root}. Run 'codexa init' first."
        )
        ctx.exit(1)
        return

    config = load_config(root)
    result_count = top_k or config.search.top_k

    # Apply shorthand flags
    if hybrid_shorthand:
        mode = "hybrid"
    elif sem_shorthand:
        mode = "semantic"

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
                "Search index is empty. Run 'codexa index' to build the index."
            )
        return

    # --- Filter by exclude glob ---
    if exclude_glob:
        import fnmatch
        results = [r for r in results if not fnmatch.fnmatch(r.file_path, exclude_glob)]

    # --- Apply snippet controls ---
    if no_snippet:
        for r in results:
            r.content = ""
    elif snippet_length is not None:
        for r in results:
            if len(r.content) > snippet_length:
                r.content = r.content[:snippet_length]

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
        click.echo(format_results_jsonl(results, scores=scores))
        return

    if json_mode:
        click.echo(format_results_json(query, results, result_count))
        return

    # --- Scores-only text mode ---
    if scores and not line_numbers:
        for r in results:
            prefix = f"[{r.score:.3f}] "
            click.echo(f"{prefix}{r.file_path}:L{r.start_line}-L{r.end_line}")
            if r.content:
                for line in r.content.splitlines()[:5]:
                    click.echo(f"  {line}")
        return

    # --- Rich / grep-style human output ---

    format_results_rich(
        query,
        results,
        line_numbers=line_numbers,
        context_lines=context_lines,
        show_scores=scores,
    )
