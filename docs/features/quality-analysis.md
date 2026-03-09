# Quality Analysis

CodexA provides a full code quality pipeline with metrics tracking,
hotspot detection, impact analysis, and CI-ready quality gates.

## Quality Analysis

Run a comprehensive scan with:

```bash
codex quality src/
codex quality --json            # JSON output
codex quality --safety-only     # Security-only (fast)
```

### What Gets Analyzed

| Category | Tool | Description |
|----------|------|-------------|
| Complexity | Radon | Cyclomatic complexity per function |
| Security | Bandit | Common vulnerability patterns |
| Dead Code | Built-in | Unused functions, unreachable code |
| Duplication | Built-in | Copy-paste detection |
| Maintainability | Built-in | Composite MI score (0–100) |

## Maintainability Index

A per-file and project-wide score (0–100) based on:

- **Lines of code** — penalizes overly large files
- **Cyclomatic complexity** — penalizes deeply nested logic
- **Comment ratio** — rewards well-documented code

| MI Range | Rating |
|----------|--------|
| 65–100 | Good (easy to maintain) |
| 40–64 | Moderate |
| 0–39 | Poor (difficult to maintain) |

## Hotspot Detection

Find the riskiest code in your project:

```bash
codex hotspots
codex hotspots --top-n 10 --json
codex hotspots --no-git       # Skip git churn data
```

### Risk Factors

| Factor | Weight | Source |
|--------|--------|--------|
| Complexity | 0.30 | Cyclomatic complexity |
| Duplication | 0.20 | Duplicate line density |
| Fan-in | 0.15 | Number of callers |
| Fan-out | 0.15 | Number of callees |
| Churn | 0.20 | Git change frequency |

When git data is unavailable, churn weight is redistributed across the other factors.

## Impact Analysis

Predict the blast radius of changes:

```bash
codex impact parse_file          # Analyze a function
codex impact src/parser.py       # Analyze a file
codex impact MyClass --max-depth 3 --json
```

Impact analysis uses BFS over the call graph and dependency map to find:

- **Direct dependents** — Functions that call the target
- **Transitive dependents** — Functions affected indirectly
- **Affected modules** — Files that import the target
- **Dependency chains** — Full paths from target to affected code

## Symbol Trace

Trace execution flow through the codebase:

```bash
codex trace parse_file
codex trace MyClass.process --json
```

Shows upstream callers and downstream callees to map how execution flows.

## Metrics & Trends

Track quality over time:

```bash
codex metrics                  # Current metrics
codex metrics --snapshot       # Save a snapshot
codex metrics --history 10     # Last 10 snapshots
codex metrics --trend          # Direction analysis
```

Trends report: **improving**, **stable**, or **degrading** for each metric.

## Quality Gates

Enforce quality policies in CI:

```bash
codex gate --strict            # Exit code 1 on failure
codex gate --min-maintainability 60 --max-complexity 15
```

| Policy | Default | Description |
|--------|---------|-------------|
| `min_maintainability` | 40.0 | Minimum MI score |
| `max_complexity` | 25 | Maximum cyclomatic complexity |
| `max_issues` | 20 | Maximum total issues |
| `max_dead_code` | 15 | Maximum dead code symbols |
| `max_duplicates` | 10 | Maximum duplicate pairs |
| `require_safety_pass` | true | Safety check must pass |

### CI Integration

Generate CI workflow templates:

```bash
codex ci-gen analysis           # Full analysis workflow
codex ci-gen safety             # Lightweight safety-only
codex ci-gen precommit          # Pre-commit hook config
```

## Plugin Hooks

Quality analysis fires these hooks for customization:

| Hook | When |
|------|------|
| `PRE_HOTSPOT_ANALYSIS` | Before hotspot scoring |
| `POST_HOTSPOT_ANALYSIS` | After hotspot report |
| `PRE_IMPACT_ANALYSIS` | Before impact BFS |
| `POST_IMPACT_ANALYSIS` | After impact report |
| `PRE_TRACE` | Before symbol trace |
| `POST_TRACE` | After trace result |
