"""CLI command: benchmark — measure indexing speed, search latency, and memory usage."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.utils.logging import (
    get_logger,
    print_error,
    print_info,
    print_success,
    console,
)

logger = get_logger("cli.benchmark")


def _get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import resource  # type: ignore[import-untyped]
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:
        # Windows fallback
        try:
            import psutil  # type: ignore[import-untyped]
            return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds:.2f}s"


def _count_files(root: Path) -> int:
    """Count indexable files without importing heavy modules."""
    config = load_config(root)
    extensions = set(config.index.extensions)
    count = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        if any(part.startswith(".") for part in Path(dirpath).relative_to(root).parts):
            continue
        for f in filenames:
            if Path(f).suffix in extensions:
                count += 1
    return count


@click.command("benchmark")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path to benchmark against.",
)
@click.option(
    "--json-output",
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output results as JSON.",
)
@click.option(
    "--rounds",
    "-r",
    default=3,
    type=int,
    help="Number of search rounds for latency averaging.",
)
@click.option(
    "--profile",
    is_flag=True,
    default=False,
    help="Run cProfile on full indexing and dump top 20 hotspots.",
)
@click.pass_context
def benchmark_cmd(
    ctx: click.Context,
    path: str,
    json_mode: bool,
    rounds: int,
    profile: bool,
) -> None:
    """Benchmark indexing speed, search latency, and memory usage.

    Measures the full indexing pipeline, incremental re-indexing, all
    four search modes (semantic, keyword, regex, hybrid), and reports
    memory consumption and cache hit rates.

    Examples:

    \b
        codexa benchmark
        codexa benchmark --json
        codexa benchmark --rounds 5
    """
    from rich.table import Table

    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codexa init' first.")
        ctx.exit(1)
        return

    index_dir = AppConfig.index_dir(root)
    results: dict[str, object] = {
        "project_root": str(root),
        "rounds": rounds,
    }

    file_count = _count_files(root)
    results["file_count"] = file_count
    print_info(f"Benchmarking {root} ({file_count} indexable files)")

    # --- 1. Full indexing benchmark ---
    print_info("1/5: Full indexing...")
    mem_before = _get_memory_mb()
    t0 = time.perf_counter()
    from semantic_code_intelligence.services.indexing_service import run_indexing

    if profile:
        import cProfile
        import pstats
        import io

        profiler = cProfile.Profile()
        profiler.enable()
        idx_result = run_indexing(root, force=True)
        profiler.disable()
        full_index_time = time.perf_counter() - t0

        # Print profiling results
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative")
        stats.print_stats(20)
        print_info("cProfile top 20 hotspots (by cumulative time):")
        click.echo(stream.getvalue())
    else:
        idx_result = run_indexing(root, force=True)
        full_index_time = time.perf_counter() - t0

    mem_after = _get_memory_mb()

    results["full_index"] = {
        "duration_s": round(full_index_time, 3),
        "files_indexed": idx_result.files_indexed,
        "chunks_created": idx_result.chunks_created,
        "total_vectors": idx_result.total_vectors,
        "symbols_extracted": idx_result.symbols_extracted,
        "files_per_second": round(idx_result.files_indexed / full_index_time, 1) if full_index_time > 0 else 0,
        "memory_delta_mb": round(mem_after - mem_before, 1),
    }
    print_success(f"   Full index: {_format_duration(full_index_time)} "
                  f"({idx_result.files_indexed} files, {idx_result.chunks_created} chunks)")

    # --- 2. Incremental indexing benchmark (no changes → should be fast) ---
    print_info("2/5: Incremental indexing (no changes)...")
    t0 = time.perf_counter()
    inc_result = run_indexing(root, force=False)
    inc_time = time.perf_counter() - t0

    results["incremental_index"] = {
        "duration_s": round(inc_time, 3),
        "files_skipped": inc_result.files_skipped,
        "files_indexed": inc_result.files_indexed,
        "chunks_reused": inc_result.chunks_reused,
        "cache_hit_rate": round(
            100 * inc_result.files_skipped / inc_result.files_scanned, 1
        ) if inc_result.files_scanned > 0 else 100.0,
    }
    print_success(f"   Incremental: {_format_duration(inc_time)} "
                  f"(cache hit {results['incremental_index']['cache_hit_rate']}%)")

    # --- 3. Search latency benchmarks ---
    print_info("3/5: Search latency ({} rounds)...".format(rounds))
    test_queries = [
        "authentication middleware",
        "error handling",
        "database connection",
        "parse configuration",
        "search codebase",
    ]
    from semantic_code_intelligence.services.search_service import search_codebase

    search_results: dict[str, dict[str, float]] = {}
    for mode in ["semantic", "keyword", "regex", "hybrid"]:
        times: list[float] = []
        for _r in range(rounds):
            for query in test_queries:
                q = query if mode != "regex" else r"def\s+\w+"
                t0 = time.perf_counter()
                try:
                    search_codebase(
                        query=q,
                        project_root=root,
                        top_k=10,
                        mode=mode,
                        auto_index=False,
                    )
                except Exception:
                    pass
                times.append(time.perf_counter() - t0)
        avg_ms = (sum(times) / len(times)) * 1000 if times else 0
        p50_ms = sorted(times)[len(times) // 2] * 1000 if times else 0
        p99_ms = sorted(times)[int(len(times) * 0.99)] * 1000 if times else 0
        search_results[mode] = {
            "avg_ms": round(avg_ms, 2),
            "p50_ms": round(p50_ms, 2),
            "p99_ms": round(p99_ms, 2),
            "queries_per_second": round(1000 / avg_ms, 1) if avg_ms > 0 else 0,
        }
        print_success(f"   {mode:>8}: avg={avg_ms:.1f}ms  p50={p50_ms:.1f}ms  p99={p99_ms:.1f}ms")

    results["search_latency"] = search_results

    # --- 4. BM25 index load benchmark ---
    print_info("4/5: BM25 index persistence...")
    from semantic_code_intelligence.search.keyword_search import BM25Index, _bm25_cache
    from semantic_code_intelligence.storage.vector_store import VectorStore

    _bm25_cache.clear()  # force disk load
    store = VectorStore.load(index_dir)

    t0 = time.perf_counter()
    bm25_loaded = BM25Index.load(index_dir, store.metadata)
    bm25_load_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    bm25_fresh = BM25Index(store.metadata)
    bm25_build_time = time.perf_counter() - t0

    results["bm25"] = {
        "load_from_disk_ms": round(bm25_load_time * 1000, 2),
        "build_from_scratch_ms": round(bm25_build_time * 1000, 2),
        "speedup": round(bm25_build_time / bm25_load_time, 1) if bm25_load_time > 0 else 0,
        "loaded_from_cache": bm25_loaded is not None,
    }
    print_success(f"   BM25 load: {bm25_load_time*1000:.1f}ms (vs build: {bm25_build_time*1000:.1f}ms)")

    # --- 5. Memory snapshot ---
    print_info("5/5: Memory usage...")
    peak_mem = _get_memory_mb()
    results["memory"] = {
        "peak_mb": round(peak_mem, 1),
        "index_size_mb": round(
            sum(f.stat().st_size for f in index_dir.iterdir() if f.is_file()) / (1024 * 1024), 2
        ) if index_dir.exists() else 0,
    }
    print_success(f"   Peak memory: {peak_mem:.0f}MB, Index size: {results['memory']['index_size_mb']:.1f}MB")

    # --- Output ---
    if json_mode:
        click.echo(json.dumps(results, indent=2))
    else:
        table = Table(title="CodexA Benchmark Results", show_header=True)
        table.add_column("Metric", style="cyan", min_width=30)
        table.add_column("Value", style="green", min_width=20)

        table.add_row("Project", str(root))
        table.add_row("Indexable files", str(file_count))
        table.add_row("", "")

        fi = results["full_index"]
        table.add_row("Full index time", _format_duration(fi["duration_s"]))
        table.add_row("Files/second", f"{fi['files_per_second']}")
        table.add_row("Total chunks", str(fi["chunks_created"]))
        table.add_row("Total vectors", str(fi["total_vectors"]))
        table.add_row("Symbols extracted", str(fi["symbols_extracted"]))
        table.add_row("", "")

        ii = results["incremental_index"]
        table.add_row("Incremental index time", _format_duration(ii["duration_s"]))
        table.add_row("Cache hit rate", f"{ii['cache_hit_rate']}%")
        table.add_row("", "")

        for mode, stats in search_results.items():
            table.add_row(f"Search ({mode}) avg", f"{stats['avg_ms']:.1f}ms")
            table.add_row(f"Search ({mode}) QPS", f"{stats['queries_per_second']}")

        table.add_row("", "")
        bm25 = results["bm25"]
        table.add_row("BM25 load (disk)", f"{bm25['load_from_disk_ms']:.1f}ms")
        table.add_row("BM25 build (fresh)", f"{bm25['build_from_scratch_ms']:.1f}ms")
        table.add_row("BM25 speedup", f"{bm25['speedup']}x")
        table.add_row("", "")
        table.add_row("Peak memory", f"{results['memory']['peak_mb']:.0f}MB")
        table.add_row("Index size on disk", f"{results['memory']['index_size_mb']:.1f}MB")

        console.print(table)
