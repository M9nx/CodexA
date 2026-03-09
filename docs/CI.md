# CI/CD Integration Reference

Auto-generated from the CodexA CI module.

## Overview

CodexA provides optional CI/CD integration for contribution safety and
quality assurance.  All outputs are **advisory** — CodexA never modifies
repository code automatically.

## Quality Analyzers

| Analyzer | Description |
|----------|-------------|
| Cyclomatic complexity | Counts decision points per function/method |
| Dead code detection | Identifies unreferenced symbols via call graph |
| Duplicate logic | Trigram Jaccard similarity between function bodies |
| Safety validation | 17 dangerous-pattern checks (existing validator) |

### Quality Report Format (JSON)

```json
{
  "files_analyzed": 42,
  "symbol_count": 180,
  "issue_count": 3,
  "complexity_issues": [{"symbol_name": "...", "complexity": 15, "rating": "high"}],
  "dead_code": [{"symbol_name": "...", "kind": "function", "file_path": "..."}],
  "duplicates": [{"symbol_a": "...", "symbol_b": "...", "similarity": 0.82}],
  "safety": {"safe": true, "issues": []}
}
```

## PR Intelligence

| Feature | Description |
|---------|-------------|
| Change summary | File-level and symbol-level diff analysis |
| Impact analysis | Blast radius via call graph traversal |
| Suggested reviewers | Domain-based reviewer assignment |
| Risk scoring | 0-100 composite risk with level (low/medium/high/critical) |

### Risk Factors

- Changeset size (file count)
- Symbol removals and modifications
- Safety issues in changed code
- Blast radius (affected downstream symbols)

## CI Workflow Templates

Generate with `codex ci-gen <template>`:

| Template | Description |
|----------|-------------|
| `analysis` | Full analysis workflow (quality + PR summary) |
| `safety` | Lightweight safety-only workflow |
| `precommit` | Pre-commit hook configuration |

## Pre-Commit Hooks

CodexA supports optional pre-commit validation:

1. Safety validation — scans for dangerous patterns
2. Plugin hooks — dispatches `CUSTOM_VALIDATION` for user-defined rules

## CLI Commands

- `codex quality [--json] [--safety-only] [--complexity-threshold N] [--pipe]`
- `codex metrics [--json] [--snapshot] [--history N] [--trend] [--pipe]`
- `codex gate [--json] [--strict] [--min-maintainability F] [--max-complexity N] [--pipe]`
- `codex pr-summary [--json] [-f FILE ...] [--pipe]`
- `codex ci-gen {analysis|safety|precommit} [-o FILE] [--python-version VER]`
