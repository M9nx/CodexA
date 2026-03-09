# Workflow Intelligence

CodexA provides three developer workflow intelligence tools that combine
static analysis, call-graph traversal, dependency mapping, and optional
git history to surface actionable insights.

## Hotspot Detection

Identifies high-risk code areas using a weighted multi-factor heuristic.

```bash
codex hotspots
codex hotspots --top-n 10 --json
codex hotspots --no-git --pipe
```

### Risk Factors

| Factor | Default Weight | Description |
|--------|---------------|-------------|
| Complexity | 0.30 | Cyclomatic complexity of the symbol |
| Duplication | 0.20 | Duplicate line density in the file |
| Fan-in | 0.15 | Number of callers (call graph in-degree) |
| Fan-out | 0.15 | Number of callees (call graph out-degree) |
| Churn | 0.20 | Git change frequency |

When git data is unavailable, churn weight is redistributed across the other factors.

## Impact Analysis

Predicts the blast radius of modifying a symbol or file using BFS over
the call graph and dependency map.

```bash
codex impact parse_file
codex impact src/parser.py --json
codex impact MyClass --max-depth 3 --pipe
```

### How It Works

1. Resolve the target to symbols or a file path
2. Seed BFS queue with the target's names and files
3. Walk callers in the call graph (direct → transitive)
4. Walk importers in the dependency map
5. Build dependency chains tracing paths back to the target

## Symbol Trace

Traces execution relationships upstream (callers) and downstream (callees).

```bash
codex trace parse_file
codex trace MyClass.process --json
codex trace build_context --max-depth 3 --pipe
```

### How It Works

1. Resolve the target symbol
2. BFS upstream: walk `callers_of` edges for transitive callers
3. BFS downstream: walk `callees_of` edges for transitive callees
4. Collect trace edges connecting the nodes

## Output Formats

All three commands support three output modes:

| Flag | Format | Use Case |
|------|--------|----------|
| *(none)* | Rich terminal | Interactive development |
| `--json` | Pretty JSON | Programmatic consumption |
| `--pipe` | Tab-separated | Shell pipelines and CI |

## Data Classes

### Hotspots

| Class | Fields |
|-------|--------|
| `HotspotFactor` | `name`, `raw_value`, `normalized`, `weight` |
| `Hotspot` | `name`, `file_path`, `kind`, `risk_score`, `factors` |
| `HotspotReport` | `files_analyzed`, `symbols_analyzed`, `hotspots` |

### Impact

| Class | Fields |
|-------|--------|
| `AffectedSymbol` | `name`, `file_path`, `kind`, `relationship`, `depth` |
| `AffectedModule` | `file_path`, `relationship`, `depth` |
| `DependencyChain` | `path` (list of strings) |
| `ImpactReport` | `target`, `target_kind`, `direct_symbols`, `transitive_symbols`, `affected_modules`, `chains` |

### Trace

| Class | Fields |
|-------|--------|
| `TraceNode` | `name`, `file_path`, `kind`, `depth` |
| `TraceEdge` | `caller`, `callee`, `file_path` |
| `TraceResult` | `target`, `target_file`, `upstream`, `downstream`, `edges` |

## Plugin Hooks

| Hook | When |
|------|------|
| `PRE_HOTSPOT_ANALYSIS` | Before hotspot scoring |
| `POST_HOTSPOT_ANALYSIS` | After hotspot report |
| `PRE_IMPACT_ANALYSIS` | Before impact BFS |
| `POST_IMPACT_ANALYSIS` | After impact report |
| `PRE_TRACE` | Before trace BFS |
| `POST_TRACE` | After trace result |
