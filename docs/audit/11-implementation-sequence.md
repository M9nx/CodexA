# 11 — Release 1–2 Implementation Sequence (Corrected v3)

**Correction date:** 2026-07-22

This document defines a dependency-aware execution order for all work items.

---

## Dependency Graph

```
Phase 0: Environment Repair (parallel)
├── Add mypy to pyproject.toml dev deps (F-03A)
├── Create .eslintrc.js (F-06)
├── Run cargo fmt (F-07)
└── Document Windows Rust build workaround (F-08A)
        │
        ▼
Phase 1: CI Infrastructure (sequential then parallel)
├── Upgrade ci.yml to use uv + mypy + coverage (F-04, F-05)  [requires F-03A]
├── npm audit fix in extension  [requires F-06 for full lint]
├── Establish mypy baseline (F-41A) [completed during audit]
└── Add cargo audit to CI (F-28A)
        │
        ▼
Phase 2: Security Fixes (parallel)
├── Workspace trust check in codexBin()  (F-01)
├── CSP meta tags in all webviews  (F-02)
├── Replace assert with if/raise  (F-18)
├── Add disposables to context.subscriptions  (F-22)
└── npm audit fix  (SEC-10)
        │
        ▼
Phase 3: Documentation Corrections (parallel with Phase 2)
├── Remove CodeLens claim from README  (F-19)
├── Correct editor plugin list  (F-20)
└── Remove/redirect requirements.txt  (F-35)
        │
        ▼
Phase 4: Coverage Expansion — R1 (parallel)
└── Add tests for mcp/claude_config.py  (F-09)
        │
        ▼
Phase 5: Release 1 Completion
└── Pass all mandatory CI checks and verify no test regressions
        │
        ▼
Phase 6: Coverage Expansion — R2 Critical Paths (parallel)
├── Add tests for web/server.py  (F-10)
├── Add tests for mcp/__init__.py  (F-11)
├── Add tests for search/grep.py  (F-12)
├── Add tests for web/api.py  (F-25)
└── Add tests for llm/streaming.py  (F-14)
        │
        ▼
Phase 7: Architecture Improvements (sequential — need coverage first)
├── Define versioned JSON contract  (F-15)  [requires Phase 6]
├── Surface backend selection  (F-16)
├── Add schema_version to IndexManifest  (F-17)
└── Coordinate version numbers  (F-31A)
        │
        ▼
Phase 8: Reliability and UX (parallel)
├── Extension cancellation support  (UX)
├── Multi-root workspace support  (UX)
├── Commit uv.lock + CI --frozen  (F-27)
├── URL scheme validation via urlparse  (F-30)
└── Pin GitHub Actions to SHAs  (F-24)
```

---

## Parallel vs. Sequential Work

### Fully Parallel Tracks

The following tracks have no cross-dependencies and can be worked simultaneously by different engineers:

| Track A | Track B | Track C |
|---------|---------|---------|
| Python tooling (mypy, CI) | Rust formatting + docs | Extension security fixes |

### Must Remain Sequential

1. **Coverage before architecture refactoring.** Do not refactor `web/server.py` before it has ≥85% tests (in R2); refactoring without tests cannot be verified.

2. **CI before coverage expansion.** Coverage improvements must be tracked by a real CI coverage check; otherwise they cannot be gated.

3. **Versioned contract before extension integration improvements.** The extension's coupling to CLI output cannot be safely changed without first defining what the new contract looks like.

---

## Critical Path for Release 1

```
Day 1-2: Phase 0 (environment repair) — all in parallel
Day 2-3: Phase 1 (CI infrastructure)
Day 3-4: Phase 2 + Phase 3 (security + docs) — in parallel with Phase 1 completion
Day 4-5: Phase 4 (critical coverage: claude_config first)
```

**Minimum Release 1 checklist:**
```
[ ] mypy in dev deps
[ ] mypy baseline recorded (F-41A) [completed during audit]
[ ] ESLint config present and passing
[ ] cargo fmt passing  
[ ] ci.yml runs real checks including cargo audit (F-28A)
[ ] requirements.txt removed or uses valid syntax
[ ] Workspace trust check in extension
[ ] CSP in all webviews
[ ] Disposables fixed
[ ] README corrected
[ ] assert→raise in workspace/__init__.py
[ ] npm audit fix applied
[ ] mcp/claude_config.py coverage ≥ 80%
[ ] All tests pass (no regressions from baseline count)
```

---

## Work Breakdown by Owner Type

| Work Type | Phase | Owner Suggestion |
|-----------|-------|-----------------|
| CI/CD configuration | 1, 8 | DevOps / Lead |
| Security fixes | 2, 8 | Security-aware engineer |
| Documentation | 3, 0 | Any contributor |
| Test writing | 4, 6 | Quality-focused engineer |
| Architecture | 7 | Lead architect |
