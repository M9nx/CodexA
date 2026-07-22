## Evidence Collection Record

All evidence collected during the CodexA audit.

### Index

| File | Command | Exit Code | Category |
|------|---------|-----------|----------|
| git/git-status.txt | `git status --short` | 1 (dirty — build artefacts) | git |
| git/git-log.txt | `git log -1 --format=...` | 0 | git |
| environment/versions.txt | version commands | various | environment |
| python/pytest-summary.txt | `uv run pytest --cov` | 0 | python |
| python/bandit-production.txt | `uv run bandit -r ... -x tests` | 1 (issues found) | python |
| python/radon-cc.txt | `uv run radon cc -a -na` | 0 | python |
| python/mypy-baseline.txt | `uv run mypy ... --ignore-missing-imports` | 1 (99 errors) | python |
| python/pip-audit.txt | `pip-audit --requirement requirements.txt` | 1 (found 0 vulns — exit 1 = advisory found; actual result: no known vulns) | security |
| rust/cargo-fmt-check.txt | `cargo fmt --check` | 1 (differences) | rust |
| rust/cargo-test.txt | `cargo test` | 1 (linker error — environment blocked) | rust |
| node/npm-audit-pre-fix.txt | `npm audit` (before fix) | 1 | node |
| node/npm-audit-after-fix.txt | `npm audit` (after fix) | 1 (6 remaining) | node |
| node/npm-audit-omit-dev.txt | `npm audit --omit=dev` | 0 | node |
| node/npm-compile.txt | `npm run compile` | 0 | node |
| node/npm-outdated.txt | `npm outdated` | 1 (outdated found) | node |

### Blocked Evidence (not collected)

| Evidence | Reason |
|----------|--------|
| `cargo audit` | `cargo-audit` not installed in this environment |
| `cargo test` (Rust unit tests) | Windows MinGW cannot find `lpython313` — environment defect |
| `mypy` (before this session) | `mypy` was not installed before this audit session |
| `npm run lint` | Missing `.eslintrc`; ESLint aborts before any analysis |
| VS Code live extension test | Requires running VS Code host; not available in audit environment |
| LLM provider integration tests | Requires API keys |
| Performance benchmarks | Not established |

### Methodology Note

Evidence files written in this session were collected during the audit. Claims about commands run in previous sessions (before the checkpoint) were read from retained report files (`bandit_report.txt`, `cargo_fmt_report.txt`, etc.). Those files are noted as prior-session evidence.
