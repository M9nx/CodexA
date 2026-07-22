# 03 — Python Core Audit (Corrected v2)

**Correction date:** 2026-07-22  
**Changes from v1:**
- Bandit claim "no CVEs" removed — Bandit does not assess CVEs
- pip-audit result added (run this session)
- mypy baseline expanded per § 5 correction requirements
- Removed broad `--ignore-missing-imports` from R1 acceptance criteria; scoped per correction requirement
- Coverage summary corrected to distinguish Python-fallback and Rust-native behaviour paths

---

## Commands Executed This Session (2026-07-22)

| Command | Exit Code | Evidence File |
|---------|-----------|---------------|
| `uv run mypy semantic_code_intelligence --ignore-missing-imports` | 1 (99 errors) | `evidence/python/mypy-baseline.txt` |
| `pip-audit --requirement requirements.txt` | 1 (0 known vulns) | `evidence/security/pip-audit.txt` |

## Commands Executed in Prior Session (2026-07-22, before checkpoint)

| Command | Exit Code | Evidence |
|---------|-----------|---------|
| `uv run pytest --cov=semantic_code_intelligence` | 0 (passed) | `pytest_report.txt` (retained in repo root) |
| `uv run bandit -r ... -x tests -f txt` | 1 (issues found) | `bandit_report.txt` (retained in repo root) |
| `uv run radon cc -a -na` | 0 | `radon_report.txt` (retained in repo root) |

## Commands Blocked

| Command | Reason |
|---------|--------|
| `mypy` without `--ignore-missing-imports` | 145 files; stub coverage incomplete; full run was not captured before this session |
| Full `pip-audit` (installed env) | `uv.lock` not committed; full env audit not run |
| `uv run mypy --strict` | Would add errors from missing stubs; not appropriate for initial baseline |

---

## 1. Test Results — Source-Confirmed

| Metric | Value | Status |
|--------|-------|--------|
| Tests collected | 2,669 | — |
| Tests passed | **2,669** | ✅ (prior session) |
| Tests failed | 0 | ✅ |
| Warnings | 5 | Minor |
| Duration | 453.29 s (7m 33s) | Acceptable |
| Coverage (total) | **70.92%** | ✅ Meets 70% gate |
| Production code lines | 23,104 | Excludes tests |

**Behaviour path distinction:**
- All 2,669 tests run against the Python-only path. The Rust-native path is **not tested** because `codexa_core` is not installed. Any coverage or test-pass claim for Rust-accelerated code paths is **unverified** in this environment.
- LLM provider tests use mocks. Real API calls are **not tested**.
- VS Code live-host behaviour is **not tested** — no extension test suite exists.
- HTTP/MCP external-client behaviour has very low unit test coverage (web/server 16%, mcp 30%).

---

## 2. Coverage Analysis — Source-Confirmed

### Overall: 70.92% (global gate met)

**Coverage policy (selected):**
- Global line coverage: ≥ 70% during stabilization
- Critical-module line coverage: ≥ 85% (target for R2)
- Mandatory behavioural scenarios required regardless of percentage (see § 10 below)

### Modules with Critically Low Coverage

| Module | Coverage | Behaviour Path | Risk |
|--------|----------|---------------|------|
| `web/server.py` | **16%** | Python-fallback | HTTP bridge; error handling and routing untested |
| `web/api.py` | **20%** | Python-fallback | REST API; all handlers essentially untested |
| `search/grep.py` | **21%** | Python-fallback | Subprocess calls; security-relevant path |
| `tui/__init__.py` | **21%** | Python-fallback | D-complexity function; TUI fallback |
| `mcp/__init__.py` | **30%** | Python-fallback | MCP server; 13 tools exposed to external agents |
| `lsp/__init__.py` | **39%** | Python-fallback | LSP server; likely incomplete |
| `llm/streaming.py` | **49%** | Python-fallback (mock LLM) | Token streaming failure → silent data loss |
| `web/ui.py` | **47%** | Python-fallback | Web UI page handlers |
| `llm/openai_provider.py` | **48%** | Mocked LLM | All OpenAI calls; error handling untested |
| `llm/investigation.py` | **59%** | Mocked LLM | Autonomous agent |
| `rust_backend.py` | **44%** | Python-only (Rust wheel absent) | 56% of branches structurally unreachable |
| `mcp/claude_config.py` | **0%** | Python-fallback | Completely untested |

### Mandatory Behavioural Scenarios (Coverage Agnostic)

The following scenarios must be explicitly implemented in the test suite regardless of percentage achieved:

| Scenario | Module | Current Status |
|----------|--------|---------------|
| HTTP malformed input → correct 4xx response | `web/server.py`, `web/api.py` | **Missing** |
| Path traversal in file arguments → rejection | `search/grep.py`, `web/` | **Missing** |
| MCP tool failure → structured error response | `mcp/__init__.py` | **Missing** |
| Claude config backup and rollback on failure | `mcp/claude_config.py` | **Missing** |
| Grep timeout and pattern-length rejection | `search/grep.py` | **Missing** |
| LLM streaming interruption → partial result | `llm/streaming.py` | **Missing** |
| Rust backend absent → Python fallback, logged at INFO | `rust_backend.py` | **Missing** |
| Storage schema version mismatch → clear error | `storage/` | **Missing** |

---

## 3. Complexity Analysis — Source-Confirmed

| Metric | Value | Status |
|--------|-------|--------|
| Average CC | A (3.10) | ✅ Excellent |
| D-ranked functions | `analyze_impact`, `build_change_summary`, `_run_fallback_repl` | Warning |

---

## 4. Security Audit — Bandit (Production Code Only)

**Scope:** 23,104 lines of production code (tests excluded via `-x tests`).

**Important:** Bandit assesses **code patterns**, not dependency CVEs. Claims about dependency vulnerability status must come from `pip-audit` or `safety`, not from Bandit.

| Severity | Count (Production) |
|----------|-------------------|
| High | **0** ✅ |
| Medium | **3** |
| Low | **26** |

Medium findings (production only): Two B310 `urlopen` scheme issues in `llm/` and `web/`. One B603 subprocess in `search/grep.py`. See `06-security-audit.md` for full analysis.

---

## 5. Python Dependency Audit — pip-audit

**Command run this session:** `pip-audit --requirement requirements.txt`  
**Result:** No vulnerabilities were reported in the attempted `requirements.txt` audit, but the evidence metadata must be reconciled.  
**Scope:** `requirements.txt` (core + test deps only)  
**Limitation:** ml/dev/tui extras not audited; no `uv.lock` committed; full environment audit incomplete  
**Evidence:** `docs/audit/evidence/security/pip-audit.txt`

---

## 6. Type Checking (mypy) Baseline — NEW this session

**Command run this session:** `uv run mypy semantic_code_intelligence --ignore-missing-imports`  
**Result:** **99 errors in 30 files** (checked 145 source files)  
**mypy version:** 2.3.0 (installed this session)  
**Evidence:** `docs/audit/evidence/python/mypy-baseline.txt`

### Error Breakdown by Package

| Package | Error Count | Notes |
|---------|------------|-------|
| `cli/` | 44 | Largest single source; command files |
| `rust_backend.py` | 13 | Optional import type stubs missing |
| `mcp/` | 10 | Type inconsistencies |
| `storage/` | 10 | Type inconsistencies |
| `ci/` | 8 | — |
| `web/` | 5 | Incompatible assignment types (confirmed) |
| `llm/` | 3 | — |
| `lsp/` | 2 | — |
| Other | 4 | `tui`, `search`, `workspace`, `analysis` |
| **Total** | **99** | — |

### Confirmed Error Examples (from `web/server.py`)

```
web/server.py:162: error: Incompatible types in assignment
  (expression: HotspotReport, variable: QualityReport) [assignment]
web/server.py:221: error: Incompatible types in assignment
  (expression: OllamaProvider, variable: OpenAIProvider) [assignment]
web/server.py:287: error: Incompatible types in assignment
  (expression: ToolExecutionResult, variable: AskResult) [assignment]
```

These are **real type errors** correlating with `web/server.py` having only 16% coverage — the type errors in this module are not tested.

### mypy Remediation Plan (§ 5 correction requirement)

**R1 scope — Install and establish baseline:**
1. Add `mypy>=1.0` to `pyproject.toml [dev]` ✅ (done this session via `uv add --dev mypy`)
2. Add `mypy.ini` or `[tool.mypy]` section to `pyproject.toml` with baseline config
3. Record the baseline: 99 errors in 30 files (this document serves as the record)

**R1 scope — Enforce clean packages (no new errors):**
Select packages with ≤ 5 errors for immediate enforcement. These can reach 0 errors without a large effort:

| Package | Errors | Action |
|---------|--------|--------|
| `tui/` | 1 | Fix and enforce |
| `search/` | 1 | Fix and enforce |
| `workspace/` | 1 | Fix and enforce |
| `analysis/` | 1 | Fix and enforce |
| `web/` | 5 | Fix and enforce |
| `lsp/` | 2 | Fix and enforce |

**R1 gate:** Selected packages above reach 0 mypy errors. CI runs mypy on selected packages and fails on new errors.

**R2 scope — Burn-down plan:**

| Package | Errors | Target Release |
|---------|--------|---------------|
| `llm/` | 3 | R2 |
| `mcp/` | 10 | R2 |
| `storage/` | 10 | R2 |
| `ci/` | 8 | R2 |
| `rust_backend.py` | 13 | R2 (may require stub generation) |
| `cli/` | 44 | R2–R3 (largest; may need incremental) |

**Repository-wide zero-error mypy is NOT a R1 requirement.** The baseline has 99 errors across 30 files; requiring zero errors in R1 is not proportionate.

**Prohibited shortcuts:** Do not use `# type: ignore` globally, `exclude_dirs` covering tested packages, or `ignore_missing_imports = True` in `mypy.ini` without per-module scoping.

---

## 7. CI Workflow Issues — Source-Confirmed

The `ci.yml` workflow:
- Runs `pytest --tb=short -q` — **no coverage gate**
- Runs a `lint` job that only checks `python -m py_compile __init__.py` — **not real linting**
- Does **not** run `mypy`, `bandit`, or `radon`
- Uses `pip install -r requirements.txt` — **diverges from `pyproject.toml` extras**
- Does **not** test the Rust extension build
- Does **not** enforce or measure coverage

The `build-wheels.yml` correctly tests Rust builds across platforms on tag push but is not part of the regular CI gate.

---

## 8. Key Python Dependencies

| Package | Version Specified | Notes |
|---------|------------------|----|
| click | ≥8.1.0 | Stable |
| pydantic | ≥2.0.0 | Stable |
| sentence-transformers | ≥2.2.0 (ml extra) | Used for embedding generation |
| faiss-cpu | ≥1.7.4 (ml extra) | Used for vector search (Python path) |
| mcp | ≥1.0.0 | MCP server implementation |
| tree-sitter | ≥0.21.0 | **API may have changed** between 0.21 and 0.26 |
| mypy | **Added this session** (2.3.0) | Must be committed to `pyproject.toml` dev deps |

### Dependency File Duplication

`requirements.txt` manually mirrors `pyproject.toml` dependencies without version pinning. This creates a drift risk between CI (which installs from `requirements.txt`) and the package (defined in `pyproject.toml`).

**Recommendation:** Prefer removing `requirements.txt` as an independent source of truth and installing directly from `pyproject.toml`. Otherwise use valid requirements syntax.
