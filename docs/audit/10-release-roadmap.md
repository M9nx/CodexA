# 10 — Release Roadmap (Corrected v3)

**Correction date:** 2026-07-22  
**Changes from v1/v2:**
- F-21 remediation removed (false positive)
- Phased findings (F-41, F-08, F-23, F-28, F-31) explicitly split into A/B/C sub-tasks to ensure 1:1 mapping with Release Priorities.
- Untracked R3/R4 items formally assigned RM-01 through RM-08 finding IDs.
- `requirements.txt` instructions corrected to forbid shell commands.
- SEC-10 explicitly marked as partially completed.

---

## Release 1 — Stabilization and Trustworthy Gates (v0.5.1)

**Objective:** Close all confirmed security weaknesses, fix broken tooling, establish trustworthy CI evidence, run missing dependency audits, correct documentation, establish mypy baseline, and document the Rust build environment.

**What this release does NOT include:** Feature development. Any finding not listed below is deferred.

---

### Release 1 Work Items

| Work Item | Finding IDs | Component | Priority | Effort | Dependencies | Acceptance Criteria | Status |
|-----------|-------------|-----------|----------|--------|--------------|---------------------|--------|
| Add workspace trust check to `codexBin()` | F-01 / SEC-02 | Extension | P1 | XS | None | `vscode.workspace.isTrusted` checked; error surfaced | Completed |
| Add CSP `<meta>` to all 4 webviews | F-02 / SEC-01 | Extension | P1 | S | None | Each webview HTML has nonce-based CSP | Completed |
| Add `mypy` to `pyproject.toml` dev deps | F-03A | Python | P1 | XS | None | `uv run mypy` resolves | Completed during audit |
| Establish mypy baseline | F-41A | Python | P1 | M | F-03A | Baseline recorded in docs | Open |
| Upgrade CI: pytest + coverage gate + bandit + pip-audit | F-04, F-05 | CI | P1 | S | None | `ci.yml` runs all checks; coverage gate ≥ 70% | Open |
| Create `.eslintrc.js` | F-06 | Extension | P1 | XS | None | `npm run lint` exits 0 | Completed |
| Run `cargo fmt` and apply to all files | F-07 | Rust | P1 | XS | None | `cargo fmt --check` exits 0 | Open |
| Add `cargo clippy -D warnings` to CI | F-07 | Rust | P1 | XS | None | Clippy step in `ci.yml` fails on warnings | Open |
| Add `cargo audit` step to CI | F-28A / SEC-11 | Rust / CI | P1 | S | None | CI runs `cargo audit` | Open |
| Document Windows Rust build workaround | F-08A | Rust / Docs | P1 | S | None | `CONTRIBUTING.md` has Windows Rust dev instructions | Open |
| Add tests for `mcp/claude_config.py` | F-09 | Python | P1 | M | None | `mcp/claude_config.py` ≥ 80% coverage | Completed |
| Replace production `assert` with guard | F-18 / SEC-06 | Python | P1 | XS | None | Uses `if query_embedding is None: raise ValueError(...)` | Completed |
| Remove CodeLens claim from README | F-19 | Docs | P1 | XS | None | README does not claim CodeLens | Open |
| Remove unsupported editor plugin claims | F-20 | Docs | P1 | XS | None | README only lists VS Code | Open |
| Add disposables to `context.subscriptions` | F-22 | Extension | P1 | XS | None | Resources properly disposed | Completed |
| Remove `requirements.txt` entirely | F-35 | Python | P1 | XS | None | `requirements.txt` removed; install direct from `pyproject.toml` | Open |
| Apply `npm audit fix` | SEC-10 | Extension | P1 | XS | None | Safe audit fix: **completed during audit**. Remaining major toolchain upgrade: deferred to R2 | Completed during audit |

---

### Release 1 Go / No-Go Criteria

**Release is approved only when all of the following are true:**

1. **Every mandatory CI check passes** on the release commit
2. **No unwaived P0 finding** open.
3. **No unwaived Release-1 P1 finding** open.
4. **No confirmed user-reachable High security issue** present.
5. **All listed R1 work items completed** or waived.
6. **No test is deleted, skipped, or weakened** without approval.
7. **All existing tests pass** (no regressions). The specific count is not fixed.

---

## Release 2 — Critical Reliability and Contracts (v0.6.0)

**Objective:** Raise coverage on critical-path modules to ≥ 85%, implement mandatory behavioural scenarios, define versioned JSON contract, add storage schema versioning, improve error handling, and establish reproducible dependency resolution.

### Release 2 Work Items

| Work Item | Finding IDs | Component | Priority | Effort | Dependencies | Acceptance Criteria | Status |
|-----------|-------------|-----------|----------|--------|--------------|---------------------|--------|
| Raise `web/server.py` coverage to ≥85% | F-10 | Python | P2 | L | None | ≥85% coverage AND mandatory scenarios pass | Open |
| Raise `mcp/__init__.py` coverage to ≥85% | F-11 | Python | P2 | L | None | ≥85% AND tool-failure scenario passes | Open |
| Raise `search/grep.py` coverage to ≥85% | F-12 | Python | P2 | M | None | ≥85% AND grep timeout scenarios pass | Open |
| Raise `web/api.py` coverage to ≥85% | F-25 | Python | P2 | L | None | ≥85% AND REST error-handling passes | Open |
| Raise `lsp/__init__.py` coverage | F-13 | Python | P2 | L | None | ≥85% OR labelled `[Experimental]` | Open |
| Raise `llm/streaming.py` coverage to ≥85% | F-14 | Python | P2 | M | None | ≥85% AND streaming-interruption passes | Open |
| Raise `rust_backend.py` coverage to ≥80% | F-26 | Python | P2 | M | None | ≥80% (mock `codexa_core` if needed) | Open |
| Define versioned JSON output contract | F-15 | Architecture | P2 | M | None | `--json` output includes `"version": 1` | Open |
| Surface Rust/Python backend in CLI and ext | F-16 | Architecture | P2 | S | None | Prints backend at INFO; extension status bar | Open |
| Add `schema_version` to `IndexManifest` | F-17 | Architecture | P2 | M | None | Mismatched schema produces migration error | Open |
| Commit `uv.lock`; use `--frozen` in CI | F-27 / SEC-09 | CI | P2 | S | None | `uv.lock` in repo; CI uses `uv sync --frozen` | Open |
| Upgrade `@typescript-eslint` v8 + ESLint v9 | SEC-10 | Extension | P2 | M | None | `npm audit` — 0 vulnerabilities (all scopes) | Open |
| PIN GitHub Actions to SHAs | F-24 / SEC-08 | CI | P2 | S | None | All `uses:` lines have pinned commit SHA | Open |
| Add URL scheme validation | F-30 / SEC-05 | Python | P2 | XS | None | `urlopen` only called with `http` or `https` via `urlparse` | Open |
| Validate regex pattern length in grep | F-36 / SEC-04 | Python | P2 | S | None | Patterns > 500 chars raise `ValueError` | Open |
| Single source of truth for version | F-31A | Architecture | P2 | S | None | Versions read from shared source | Open |
| Document env-var override for LLM API key | F-37 / SEC-12 | Docs | P2 | XS | None | Document `CODEXA_API_KEY` env var | Open |
| Mypy burn-down (critical packages) | F-41B | Python | P2 | M | F-41A | Named packages reach 0 mypy errors; CI enforces | Open |
| Enforce mypy in CI | F-03B | CI | P2 | S | F-03A | CI enforces mypy on selected packages | Open |
| Remediate cargo audit CVEs | F-28B | Rust | P2 | M | F-28A | Vulnerabilities fixed or waived | Open |
| Fix ONNX build supply chain risk | F-23A / SEC-07 | Rust | P2 | M | None | Verify checksum or isolate build | Open |

---

## Release 3 — Performance and Native Integration (v0.7.0)

**Objective:** Establish reproducible performance baseline, implement measured optimizations, test Rust tests in CI.

### Release 3 Work Items

| Work Item | Finding IDs | Component | Priority | Effort | Dependencies | Acceptance Criteria | Status |
|-----------|-------------|-----------|----------|--------|--------------|---------------------|--------|
| Establish benchmark baseline | F-40 | All | P3 | M | None | `08-performance-baseline.md` filled | Open |
| Non-blocking VS Code indexing | RM-01 | Extension | P3 | M | None | Host not blocked during indexing | Open |
| Rust test CI (Windows/Linux) | F-08B | Rust / CI | P3 | M | None | Rust tests run successfully in CI | Open |
| Python↔Rust integration parity tests | F-32 | Python+Rust | P3 | L | Rust build | Identical inputs produce identical outputs | Open |
| ONNX integration tests | F-23B | Rust | P3 | L | F-23A | ONNX features tested in CI | Open |
| Web server: benchmark then decide | F-38 | Python | P3 | Measure | F-40 | Decide concurrency solution from data | Open |
| VS Code extension test suite | F-34 | Extension | P3 | L | None | `@vscode/test-electron` configured; ≥ 10 tests | Open |
| Raise `tui/__init__.py` coverage to ≥ 70% | F-29 | Python | P3 | M | None | ≥ 70% coverage | Open |
| Raise `evolution/` coverage to ≥ 80% | F-33 | Python | P3 | M | None | ≥ 80% coverage | Open |
| Refactor `analyze_impact` (D-complexity) | F-39 | Python | P3 | M | None | Radon CC ≤ C; all tests pass | Open |
| Mypy burn-down (remaining packages) | F-41C | Python | P3 | L | F-41B | Remaining packages reach 0 mypy errors | Open |

---

## Release 4 — Release Maturity (v0.8.0)

**Objective:** Automate release pipeline, reproducible builds, compatibility policies.

### Release 4 Work Items

| Work Item | Finding IDs | Component | Priority | Effort | Dependencies | Acceptance Criteria | Status |
|-----------|-------------|-----------|----------|--------|--------------|---------------------|--------|
| Public compatibility policy | RM-02 | Docs | P4 | M | None | `COMPATIBILITY.md` defines stability guarantees | Open |
| Automated coordinated release | F-31B | CI | P4 | L | F-31A | Fully automated CI release on tag | Open |
| Release automation pipeline | RM-03 | CI | P4 | L | None | Git tag push → artifact build → PyPI | Open |
| Reproducible builds | RM-04 | CI | P4 | M | F-27 | Builds produce identical hashes | Open |
| Artifact signing | RM-05 | CI | P4 | M | RM-04 | Artifacts have verifiable signatures | Open |
| Migration documentation | RM-06 | Docs | P4 | M | None | `MIGRATION.md` covers all breaking changes | Open |
| Supported-platform qualification | RM-07 | All | P4 | M | None | Support matrix defined and CI tested | Open |
| Plugin API stability | RM-08 | Python | P4 | M | None | Stable hooks guaranteed not to break | Open |
