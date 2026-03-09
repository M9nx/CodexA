# Workflow Intelligence Reference

CodexA provides three developer workflow intelligence tools that combine
static analysis, call-graph traversal, dependency mapping, and optional
git history to surface actionable insights about your codebase.

---

## Hotspot Detection (`codex hotspots`)

Identifies high-risk code areas using a weighted multi-factor heuristic.

### Factors

| Factor | Default Weight | Description |
|--------|---------------|-------------|
| Complexity | 0.30 | Cyclomatic complexity of the symbol body |
| Duplication | 0.20 | Duplicate line density in the containing file |
| Fan-in | 0.15 | Number of callers (call graph in-degree) |
| Fan-out | 0.15 | Number of callees (call graph out-degree) |
| Churn | 0.20 | Git change frequency (commits touching the file) |

When git data is unavailable the churn weight is redistributed equally
across the remaining four factors.

### CLI Options

| Option | Description |
|--------|-------------|
| `--path / -p` | Project root (default: `.`) |
| `--top-n / -n` | Number of hotspots to report (default: 20) |
| `--include-git / --no-git` | Toggle git churn analysis |
| `--json` | JSON output |
| `--pipe` | Machine-readable plain text |

### API

| Function | Description |
|----------|-------------|
| `analyze_hotspots(symbols, call_graph, dep_map, root, *, top_n, include_git, weights)` | Run full hotspot analysis |

### Plugin Hooks

| Hook | When |
|------|------|
| `PRE_HOTSPOT_ANALYSIS` | Before hotspot scoring begins |
| `POST_HOTSPOT_ANALYSIS` | After the hotspot report is built |

---

## Impact Analysis (`codex impact <target>`)

Predicts the blast radius of modifying a symbol or file using BFS over
the call graph and dependency map.

### How It Works

1. Resolve the target to symbols or a file path
2. Seed the BFS queue with the target's names and files
3. Walk callers in the call graph (direct → transitive)
4. Walk importers in the dependency map
5. Build dependency chains tracing paths back to the target

### CLI Options

| Option | Description |
|--------|-------------|
| `TARGET` | Symbol name or relative file path |
| `--path / -p` | Project root (default: `.`) |
| `--max-depth / -d` | BFS depth limit (default: 5) |
| `--json` | JSON output |
| `--pipe` | Machine-readable plain text |

### API

| Function | Description |
|----------|-------------|
| `analyze_impact(target, symbols, call_graph, dep_map, root, *, max_depth)` | Run impact analysis |

### Plugin Hooks

| Hook | When |
|------|------|
| `PRE_IMPACT_ANALYSIS` | Before impact BFS begins |
| `POST_IMPACT_ANALYSIS` | After the impact report is built |

---

## Symbol Trace (`codex trace <symbol>`)

Traces execution relationships upstream (callers) and downstream (callees)
to visualise call flow through the codebase.

### How It Works

1. Resolve the target symbol
2. BFS upstream: walk `callers_of` edges to find all transitive callers
3. BFS downstream: walk `callees_of` edges to find all transitive callees
4. Collect trace edges connecting the nodes

### CLI Options

| Option | Description |
|--------|-------------|
| `SYMBOL` | Symbol name to trace |
| `--path / -p` | Project root (default: `.`) |
| `--max-depth / -d` | BFS depth limit (default: 5) |
| `--json` | JSON output |
| `--pipe` | Machine-readable plain text |

### API

| Function | Description |
|----------|-------------|
| `trace_symbol(target, symbols, call_graph, *, max_depth)` | Run symbol trace |

### Plugin Hooks

| Hook | When |
|------|------|
| `PRE_TRACE` | Before trace BFS begins |
| `POST_TRACE` | After the trace result is built |

---

## Output Formats

All three commands support three output modes:

| Flag | Format | Use Case |
|------|--------|----------|
| *(none)* | Rich terminal | Interactive development |
| `--json` | Pretty JSON | Programmatic consumption |
| `--pipe` | Tab-separated text | Shell pipelines and CI |

---

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
