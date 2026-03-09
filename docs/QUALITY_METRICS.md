# Quality Metrics & Trends Reference

Auto-generated documentation for CodexA's quality metrics, trend tracking,
and quality gate enforcement features.

## Maintainability Index

CodexA computes a per-file and project-wide maintainability index (0-100)
based on a simplified Software Engineering Institute (SEI) formula:

- **Lines of code** — penalises overly large files
- **Cyclomatic complexity** — penalises deeply nested logic
- **Comment ratio** — rewards well-documented code

| MI Range | Rating |
|----------|--------|
| 65-100 | Good (easy to maintain) |
| 40-64 | Moderate |
| 0-39 | Poor (difficult to maintain) |

## Quality Snapshots

Save point-in-time quality metrics via `codex metrics --snapshot`.
Snapshots are stored in `.codex/memory.json` and include:

- Maintainability index
- Lines of code
- Symbol count
- Issue count
- Avg complexity
- Comment ratio
- Timestamp and metadata

## Trend Analysis

Use `codex metrics --trend` to compute directional trends from snapshots:

| Metric Tracked | Higher is Better |
|---------------|-----------------|
| `maintainability_index` | Yes |
| `avg_complexity` | No |
| `issue_count` | No |
| `total_loc` | Yes |

Trend direction: **improving**, **stable**, or **degrading**.

## Quality Gates

Enforce quality policies in CI pipelines with `codex gate`.

| Policy | Default | Description |
|--------|---------|-------------|
| `min_maintainability` | 40.0 | Minimum MI score |
| `max_complexity` | 25 | Maximum cyclomatic complexity |
| `max_issues` | 20 | Maximum total quality issues |
| `max_dead_code` | 15 | Maximum dead code symbols |
| `max_duplicates` | 10 | Maximum duplicate code pairs |
| `require_safety_pass` | true | Safety check must pass |

Use `--strict` to exit with code 1 on failure (for CI).

## CLI Commands

```
codex metrics                          # Current metrics
codex metrics --snapshot --json        # Save snapshot, JSON output
codex metrics --history 10             # Last 10 snapshots
codex metrics --trend                  # Trend analysis
codex gate --strict                    # CI quality gate
codex gate --min-maintainability 60    # Custom threshold
```

## Configuration

Quality settings in `.codex/config.json`:

```json
{
  "quality": {
    "complexity_threshold": 10,
    "min_maintainability": 40.0,
    "max_issues": 20,
    "snapshot_on_index": false,
    "history_limit": 50
  }
}
```
