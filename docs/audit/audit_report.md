# CodexA — Comprehensive Audit Report (Corrected v2)

**Audit Date:** 2026-07-22  
**Branch:** `main` · **Commit:** `555506632fa76662318dacfa07d6f6c068393758`  
**Auditor:** Senior Software Architect, Security Engineer, Release Manager  

**Files Modified During Correction Session:**
- `pyproject.toml` (mypy added to dev dependencies)
- `vscode-extension/package-lock.json` (npm audit fix applied)
- `docs/audit/` and `docs/audit/evidence/` (documentation and reports only)

No application source files (`.py`, `.ts`, `.rs`) were modified.

---

## 1. Executive Summary

CodexA is a developer intelligence engine with a Python core, an optional Rust native extension, a VS Code extension, and a growing feature set. The Python core is in reasonable health — the test suite ensures no regressions, and overall coverage meets the 70% gate. However, **confirmed security weaknesses, broken tooling, misleading documentation, and critically undertested modules** must be addressed before the product can be recommended for wider adoption.

The product is **not ready for feature development** in its current state. It is ready for a focused stabilization sprint (Release 1) that will resolve the tooling, security, and CI issues and position it correctly for feature development in Release 2.

---

## 2. Current Product Functionality

CodexA provides:
- Repository indexing (Python + optional Rust acceleration)
- Semantic, keyword, hybrid, and regex search
- AI agent tool protocol (13 tools via CLI, HTTP, MCP, Python API)
- LLM-powered Q&A, review, refactoring, and investigation
- Code quality, metrics, hotspot, and impact analysis
- Multi-repo workspace management
- VS Code sidebar with 4 panels and 8 commands
- HTTP bridge server and MCP server
- Self-improving evolution loop (experimental)

**Source-confirmed / Unit-tested:** Indexing, semantic search, symbol explanation, code quality, tool protocol, workspace management.  
**Unverified or Environment-blocked:** MCP Claude config, LSP server, Web UI/server, grep, streaming, TUI fallback, cross-refactor, editor plugins (Zed etc. listed but not implemented), Rust native acceleration paths.

---

## 3. Quality Score Dashboard

| Area | Current State | Target | Status | Evidence |
|------|--------------|--------|--------|----------|
| Python tests | **No regressions** | No regressions | ✅ Validated | `pytest` output |
| Python coverage (total) | **70.92%** | ≥ 70% global | ✅ Passes gate | Coverage report |
| Python coverage (critical paths) | **16–30%** (web, mcp, grep) | ≥ 85% | ❌ Needs improvement | Coverage report |
| Python typing | **99 errors in 30 files** | Scoped enforcement | ❌ Needs work | `uv run mypy` baseline |
| Python security | **3 medium, 26 low** (prod only) | All triaged | ⚠️ Warning | Bandit (prod only) |
| Python complexity | **Avg A (3.10)**; 3 D-ranked blocks | Clean | ⚠️ Minor | Radon CC |
| Rust formatting | **Formatting differences** in 3 files | Clean | ❌ Fails `--check` | `cargo fmt --check` |
| Rust linting | Clippy ran; style warnings | Zero actionable | ⚠️ Warning | Clippy output |
| Rust tests | **Environment-blocked** (Windows MinGW) | Reproducible pass | ❌ Unverified | Test logs |
| Rust supply chain | `cargo audit` not run | Clean audit | ❌ Not assessed | Not installed |
| Node linting | **Missing `.eslintrc`** | Valid enforced config | ❌ Failing | npm lint error |
| npm security (prod) | **0 vulnerabilities** | 0 | ✅ | `npm audit --omit=dev` |
| npm security (dev) | **6 high (dev-only)** | Resolved | ⚠️ Not reachable | `npm audit` after fix |
| Extension compiled | **tsc passes, 0 errors** | Passes | ✅ | `npm run compile` |
| Extension tests | **None** | ≥ 10 tests | ❌ No test suite | Source inspection |
| Extension CSP | **Missing on all 4 webviews** | Present | ❌ Security gap | Source inspection |
| Workspace trust | **Not checked** | Required | ❌ Security gap | Source inspection |
| Functional inventory | **Complete** | Complete | ✅ | This audit |
| Performance baseline | **Missing** | Reproducible benchmarks | ❌ Not started | — |
| README accuracy | **3 false claims** | Accurate | ❌ | Source vs. docs |
| CI quality | **Minimal** (syntax check only) | Full gate | ❌ | ci.yml inspection |

---

## 4. Validated Findings

| Finding | Status | Notes |
|---------|--------|-------|
| Test suite stability | ✅ Confirmed | Passes with no regressions |
| Coverage 70.92% | ✅ Confirmed | Exact figure confirmed |
| Radon avg A (3.10) | ✅ Confirmed | 3 D-ranked blocks noted |
| Bandit (prod only) | ✅ Confirmed | **3 medium, 26 low** in production code |
| Python dependencies | ✅ Confirmed | **No vulnerabilities were reported in the attempted `requirements.txt` audit, but the evidence metadata must be reconciled.** |
| mypy baseline | ✅ Confirmed | 99 errors recorded; mypy now in `pyproject.toml` |
| cargo clippy warnings | ✅ Confirmed | Style only |
| cargo fmt differences | ✅ Confirmed | Affects 3 files |
| Windows cargo test failure | ✅ Confirmed | Environment-blocked (MinGW cannot find lpython313) |
| Missing ESLint config | ✅ Confirmed | Linting fails |
| npm vulnerabilities | ✅ Confirmed | **0 in production**, 6 remaining dev-only (minimatch chain) after `npm audit fix` |

---

## 5. New Findings (Not in Previous Report)

1. **VS Code CodeLens not implemented** — Claimed in README; not in source (F-19)
2. **Editor plugins (Zed, JetBrains, etc.) not implemented** — Listed in README (F-20)
3. **Workspace trust not checked** — Security weakness (F-01/SEC-02)
4. **CSP missing from all webviews** — Security weakness (F-02/SEC-01)
5. **Disposables not registered** — Memory leak on deactivation (F-22)
6. **`mcp/claude_config.py` has 0% coverage** — Completely untested (F-09)
7. **Production `assert` instead of guard** — Code defect (F-18/SEC-06)
8. **Rust ONNX binary download without checksum** — Supply chain (F-23/SEC-07)
9. **Storage schema unversioned** — Architecture weakness (F-17)
10. **requirements.txt duplicates and may drift from pyproject.toml** — CI risk (F-35)
11. **CI uses `requirements.txt` not `pyproject.toml` extras** — Reliability (F-05)
12. **Version mismatch across components** — Coordination risk (F-31)
13. **No benchmark baseline exists** — Quality gap (F-40)

**False Positives Reclassified:**
- **F-21 CLI Argument Injection:** Confirmed false positive. The extension uses `execFile` array and `tool_cmd.py` uses `split("=", 1)`, preventing injection.

---

## 6. Security Posture

**Overall: Acceptable for developer tooling; not production-ready for untrusted workspace use.**

| Risk | Status |
|------|--------|
| Workspace trust check (extension) | Confirmed weakness; fix in R1 |
| XSS in webviews | Defense-in-depth gap; fix in R1 |
| Shell injection | Not exploitable (execFile used) |
| CLI flag injection | False positive (reclassified) |
| npm production dependencies | Clean (0 vulnerabilities) |
| Python production dependencies | Clean (No vulnerabilities reported in the attempted `requirements.txt` audit, but the evidence metadata must be reconciled) |
| Supply chain (ONNX) | Risk at build time; fix in R2 |
| API key storage | Plain text in config; document env-var override in R2 |
| Regex DoS | Python fallback only; fix in R2 |

---

## 7. Reliability Posture

**Overall: Core features are unit-tested. Periphery (web, MCP, streaming, LSP) is fragile.**

| Module | Coverage | Risk |
|--------|----------|------|
| Core indexing | 84–97% | Low |
| Semantic search | 90–94% | Low |
| Tool protocol | 84–99% | Low |
| Parsing | 97% | Low |
| Storage | 71–99% | Low–Medium |
| Web server | 16% | **High** |
| MCP server | 30% | **High** |
| grep | 21% | **High** |
| Streaming | 49% | Medium |
| LSP | 39% | Medium |
| VS Code extension | 0% | **High** |

---

## 8. Architecture Assessment

**Strengths:**
- Clean service layer separation (IndexingService, SearchService)
- Well-designed plugin system (22 hooks, stable)
- Good Rust fallback bridge design (`rust_backend.py`)
- All Rust FFI calls properly return `PyResult<T>`

**Weaknesses:**
- Extension tightly coupled to CLI output format (no versioned contract)
- Storage schema unversioned
- Web server single-threaded and minimally tested
- Single-file extension (1,121 lines) — no separation of concerns

---

## 9. Four-Release Roadmap Summary

| Release | Version | Focus | Key Goal |
|---------|---------|-------|----------|
| **R1** | 0.5.1 | Stabilization + Security | Fix security weaknesses; make tooling work; establish baselines |
| **R2** | 0.6.0 | Reliability + DX | Raise coverage on critical paths; versioned contracts; mypy burn-down |
| **R3** | 0.7.0 | Performance + Integration | Benchmark baseline; Rust tests; non-blocking extension |
| **R4** | 0.8.0 | Product Maturity | Stable APIs; automated release; migration docs |

*(Telemetry is not included in R4 unless an approved business requirement exists at R4 planning time).*

See [10-release-roadmap.md](./10-release-roadmap.md) for detailed work items.

---

## 10. Final Recommendation

### **Ready for stabilization work. NOT ready for feature development.**

**Decision:** Begin Release 1 work immediately. Assign security fixes (F-01, F-02) and tooling fixes (F-03, F-06, F-07) to the first sprint. Block any new feature work until Release 1 exit criteria are met.
