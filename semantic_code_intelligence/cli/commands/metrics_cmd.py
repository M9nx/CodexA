"""CLI command: metrics — code quality metrics, snapshots, and trends."""

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
)

logger = get_logger("cli.metrics")


@click.command("metrics")
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
@click.option(
    "--pipe",
    is_flag=True,
    default=False,
    help="Plain text output for piping / CI.",
)
@click.option(
    "--snapshot",
    is_flag=True,
    default=False,
    help="Save a quality snapshot after computing metrics.",
)
@click.option(
    "--history",
    type=int,
    default=0,
    help="Show last N snapshots (0 = skip history).",
)
@click.option(
    "--trend",
    is_flag=True,
    default=False,
    help="Show trend analysis from historical snapshots.",
)
@click.pass_context
def metrics_cmd(
    ctx: click.Context,
    path: str,
    json_mode: bool,
    pipe: bool,
    snapshot: bool,
    history: int,
    trend: bool,
) -> None:
    """Compute code quality metrics, save snapshots, and track trends.

    Calculates maintainability index, LOC, complexity, and comment ratios.
    Supports saving metric snapshots for historical trend analysis.

    Examples:

        codex metrics

        codex metrics --snapshot --json

        codex metrics --history 10

        codex metrics --trend
    """
    from semantic_code_intelligence.ci.metrics import (
        compute_project_metrics,
        compute_trend,
        load_snapshots,
        save_snapshot,
    )
    from semantic_code_intelligence.ci.quality import analyze_project

    root = Path(path).resolve()

    # ── History-only mode ────────────────────────────────────────
    if history > 0 and not trend:
        snaps = load_snapshots(root, limit=history)
        if json_mode:
            click.echo(json_mod.dumps(
                {"snapshots": [s.to_dict() for s in snaps]},
                indent=2,
            ))
        elif pipe:
            for s in snaps:
                click.echo(
                    f"  {s.timestamp:.0f}  MI={s.maintainability_index:.1f}  "
                    f"LOC={s.total_loc}  issues={s.issue_count}"
                )
        else:
            if not snaps:
                print_info("No snapshots found — run with --snapshot to save one.")
                return
            console.print(f"\n[bold cyan]Quality Snapshots[/bold cyan] (last {len(snaps)})\n")
            for s in snaps:
                import datetime
                ts = datetime.datetime.fromtimestamp(s.timestamp).strftime("%Y-%m-%d %H:%M")
                console.print(
                    f"  {ts}  MI=[bold]{s.maintainability_index:.1f}[/bold]  "
                    f"LOC={s.total_loc}  issues={s.issue_count}"
                )
        return

    # ── Trend-only mode ──────────────────────────────────────────
    if trend:
        limit = history if history > 0 else 50
        snaps = load_snapshots(root, limit=limit)
        if len(snaps) < 2:
            print_info("Need at least 2 snapshots for trend — run with --snapshot first.")
            return

        metrics_to_track = [
            ("maintainability_index", True),
            ("avg_complexity", False),
            ("issue_count", False),
            ("total_loc", True),
        ]
        results = []
        for metric, higher in metrics_to_track:
            t = compute_trend(snaps, metric, higher_is_better=higher)
            results.append(t)

        if json_mode:
            click.echo(json_mod.dumps(
                {"trends": [t.to_dict() for t in results]},
                indent=2,
            ))
        elif pipe:
            for t in results:
                click.echo(
                    f"  TREND  {t.metric_name}  {t.direction}  "
                    f"oldest={t.oldest_value:.2f}  newest={t.newest_value:.2f}  "
                    f"delta={t.delta:+.2f}"
                )
        else:
            console.print(f"\n[bold cyan]Quality Trends[/bold cyan] ({len(snaps)} snapshots)\n")
            for t in results:
                color = {"improving": "green", "degrading": "red", "stable": "yellow"}.get(t.direction, "white")
                console.print(
                    f"  {t.metric_name:<30} [{color}]{t.direction:>10}[/{color}]  "
                    f"{t.oldest_value:.1f} -> {t.newest_value:.1f}  ({t.delta:+.1f})"
                )
        return

    # ── Compute current metrics ──────────────────────────────────
    pm = compute_project_metrics(root)

    # Optionally save snapshot
    saved = None
    if snapshot:
        report = analyze_project(root)
        saved = save_snapshot(root, pm, report)

    if json_mode:
        payload = pm.to_dict()
        if saved:
            payload["snapshot"] = saved.to_dict()
        click.echo(json_mod.dumps(payload, indent=2))
        return

    if pipe:
        click.echo(
            f"Files: {pm.files_analyzed}  LOC: {pm.total_loc}  "
            f"MI: {pm.maintainability_index:.1f}  "
            f"AvgCC: {pm.avg_complexity:.1f}  MaxCC: {pm.max_complexity}"
        )
        if saved:
            click.echo(f"Snapshot saved at {saved.timestamp:.0f}")
        return

    # Rich output
    console.print(f"\n[bold cyan]Quality Metrics[/bold cyan] — {root}\n")
    console.print(f"  Files analyzed:       {pm.files_analyzed}")
    console.print(f"  Lines of code:        {pm.total_loc}")
    console.print(f"  Comment lines:        {pm.total_comment_lines}")
    console.print(f"  Comment ratio:        {pm.comment_ratio:.1%}")
    console.print(f"  Symbols:              {pm.total_symbols}")
    console.print(f"  Avg complexity:       {pm.avg_complexity:.1f}")
    console.print(f"  Max complexity:       {pm.max_complexity}")
    console.print(f"  Maintainability index: [bold]{pm.maintainability_index:.1f}[/bold]")

    if saved:
        print_success("Snapshot saved")

    if pm.file_metrics:
        console.print(f"\n[bold]Per-File Maintainability:[/bold]")
        # Sort worst-first
        ranked = sorted(pm.file_metrics, key=lambda f: f.maintainability_index)
        for fm in ranked[:10]:
            mi = fm.maintainability_index
            color = "green" if mi >= 65 else ("yellow" if mi >= 40 else "red")
            name = Path(fm.file_path).name
            console.print(f"  [{color}]{mi:5.1f}[/{color}]  {name}  (LOC={fm.lines_of_code}, CC={fm.avg_complexity:.1f})")
