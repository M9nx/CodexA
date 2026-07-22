# 09 — Findings Register (Corrected v2)

**Correction date:** 2026-07-22  
**Changes from v1:**
- F-21 reclassified as a **false positive** and removed from remediation scope
- F-01, F-02 severity corrected; preconditions and interaction requirements separated
- F-10 npm item corrected — F-10 is `web/server.py` coverage; npm advisories are `SEC-10`
- All severities normalized across this register, security audit, roadmap, and main report
- Phased findings (F-03, F-08, F-23, F-31, F-41) split to ensure 1:1 mapping with Release Priorities
- New RM-01 to RM-08 findings added to track previously untracked roadmap work items
- Added `Status` field (Open, Partially completed, Completed during audit, Accepted risk, Blocked)

---

## Priority Definitions

| Level | Definition |
|-------|-----------|
| **P0** | Release blocker — must be fixed before shipping |
| **P1** | Must fix in Release 1 (v0.5.1) |
| **P2** | Must fix in Release 2 (v0.6.0) |
| **P3** | Planned improvement (Release 3) |
| **P4** | Release Maturity (Release 4) |

## Severity Definitions

| Level | Definition |
|-------|-----------|
| **High** | Real, confirmed exploit path; user data, system integrity, or remote execution at risk |
| **Medium** | Confirmed weakness requiring user interaction or specific conditions to exploit |
| **Low** | Defense-in-depth gap; no direct exploit path demonstrated |
| **Info** | Observation: maintainability, quality, or process gap |

---

## False Positives

| ID | Previous classification | Reason for reclassification |
|----|------------------------|------------------------------|
| F-21 | P2 Low — CLI arg injection | `execFile` passes `symbol_name=<value>` as a single argv element. `tool_cmd.py:132` splits on the first `=` only. No secondary CLI flag parsing occurs. **False positive.** |

---

## Findings

| ID | Priority | Security | Component | Evidence Type | Evidence Summary | User Impact | Eng Impact | Effort | Deps | Release | Status |
|----|----------|----------|-----------|---------------|------------------|-------------|------------|--------|------|---------|--------|
| F-01 | P1 | Medium | VS Code Ext | Source-confirmed | `codexBin()` resolves without checking `vscode.workspace.isTrusted` | Code execution (attacker binary) | Security | XS | None | R1 | Completed |
| F-02 | P1 | Low | VS Code Ext | Source-confirmed | 4 webviews use `enableScripts: true` with no CSP `<meta>` | XSS via bypassed escaping | Security | S | None | R1 | Completed |
| F-03A | P1 | — | Python | Source-confirmed | `mypy` not in `pyproject.toml` | Type regressions undetected | DX / quality | XS | None | R1 | Completed during audit |
| F-03B | P2 | — | Python | Source-confirmed | `mypy` enforcement missing in CI | Type regressions undetected | DX / quality | S | F-03A | R2 | Open |
| F-04 | P1 | — | CI/CD | Source-confirmed | `ci.yml` lacks coverage gate | CI doesn't enforce quality | CI | S | None | R1 | Open |
| F-05 | P1 | — | CI/CD | Source-confirmed | CI installs `requirements.txt` not `pyproject.toml` extras | Different test environment | CI | S | None | R1 | Open |
| F-06 | P1 | — | VS Code Ext | Command-confirmed | `npm run lint` missing `.eslintrc.*` | Extension linting non-functional | DX | XS | None | R1 | Completed |
| F-07 | P1 | — | Rust | Command-confirmed | `cargo fmt --check` diffs | Formatting not enforced | Quality | XS | None | R1 | Open |
| F-08A | P1 | — | Rust | Command-confirmed | `cargo test` Windows MSVC CI fix | No CI Rust tests | DX | M | None | R1 | Completed |
| F-08B | P3 | — | Rust | Command-confirmed | Windows MinGW block (local dev) | Local dev blocked | DX | S | None | R3 | Blocked |
| F-09 | P1 | — | Python | Source-confirmed | `mcp/claude_config.py` — 0% coverage | Regressions are silent | Reliability | M | None | R1 | Completed |
| F-10 | P2 | — | Python | Unit-tested | `web/server.py` — 16% coverage | HTTP bridge regressions silent | Reliability | L | None | R2 | Open |
| F-11 | P2 | — | Python | Unit-tested | `mcp/__init__.py` — 30% coverage | MCP tool failures undetected | Reliability | L | None | R2 | Open |
| F-12 | P2 | — | Python | Unit-tested | `search/grep.py` — 21% coverage | Grep failures silent | Reliability | M | None | R2 | Open |
| F-13 | P2 | — | Python | Unit-tested | `lsp/__init__.py` — 39% coverage | LSP server incomplete | Reliability | L | None | R2 | Open |
| F-14 | P2 | — | Python | Unit-tested | `llm/streaming.py` — 49% coverage | Silent partial output | Reliability | M | None | R2 | Open |
| F-15 | P2 | — | Architecture | Source-confirmed | Extension parses CLI without version | CLI restructuring breaks ext | Maint. | M | None | R2 | Open |
| F-16 | P2 | — | Architecture | Source-confirmed | Rust backend fallback logging silent | Users unaware of degraded perf | UX | S | None | R2 | Open |
| F-17 | P2 | — | Architecture | Source-confirmed | `IndexManifest` misses `schema_version` | Corrupted load with vague error | Reliability | M | None | R2 | Open |
| F-18 | P1 | Low | Python | Source-confirmed | `assert query_embedding` in prod path | Assertion removed in `-O` mode | Quality | XS | None | R1 | Completed |
| F-19 | P1 | — | Docs | Source-confirmed | README asserts CodeLens support | Misleading | Docs | S | None | R1 | Open |
| F-20 | P1 | — | Docs | Source-confirmed | README lists missing editor plugins | Misleading | Docs | S | None | R1 | Open |
| F-22 | P1 | — | VS Code Ext | Source-confirmed | Disposables leak on deactivation | Memory leak | Reliability | XS | None | R1 | Completed |
| F-23A | P2 | Low | Rust | Source-confirmed | `ort` downloads ONNX via build script | Supply-chain injection risk | Security | M | None | R2 | Open |
| F-23B | P3 | Low | Rust | Source-confirmed | ONNX integration tests | Parity untested | Quality | L | None | R3 | Open |
| F-24 | P2 | Info | Supply chain | Source-confirmed | GH Actions unpinned | Supply-chain injection | Security | S | None | R2 | Open |
| F-25 | P2 | — | Python | Unit-tested | `web/api.py` — 20% coverage | REST API regressions silent | Reliability | L | None | R2 | Open |
| F-26 | P2 | — | Python | Unit-tested | `rust_backend.py` — 44% coverage | Rust fallback paths untested | Reliability | M | None | R2 | Open |
| F-27 | P2 | Info | Python | Source-confirmed | No `uv.lock` committed | CI builds use diff versions | Reprod. | S | None | R2 | Open |
| F-28A | P1 | Unknown| Rust | Blocked | `cargo-audit` CI step | Rust crate CVEs undetected | Security | S | None | R1 | Open |
| F-28B | P2 | Unknown| Rust | Blocked | `cargo-audit` local/remediation | CVE fixes | Security | M | F-28A | R2 | Open |
| F-29 | P3 | — | Python | Unit-tested | `tui/__init__.py` — 21% coverage | TUI fallback regressions silent | Reliability | M | None | R3 | Open |
| F-30 | P2 | Low | Python | Source-confirmed | `urlopen` called without scheme check | SSRF if URL source is controlled | Security | XS | None | R2 | Open |
| F-31A | P2 | — | Architecture | Source-confirmed | Shared version source needed | Undocumented compatibility | Maint. | S | None | R2 | Open |
| F-31B | P4 | — | Architecture | Source-confirmed | Automated coordinated release | PyPI manual steps | Maint. | L | F-31A | R4 | Open |
| F-32 | P3 | — | Architecture | Blocked | Rust parity untestable | Behavior divergence | Reliability | L | None | R3 | Open |
| F-33 | P3 | — | Python | Unit-tested | `evolution/` — 67% coverage | Evolution loop silent fails | Reliability | M | None | R3 | Open |
| F-34 | P3 | — | VS Code Ext | Source-confirmed | 0 extension tests | Extension regressions silent | Reliability | L | None | R3 | Open |
| F-35 | P1 | — | Docs | Source-confirmed | `requirements.txt` mirrors pyproject | Confusing; CI drift risk | Maint. | XS | None | R1 | Open |
| F-36 | P2 | Low | Python | Source-confirmed | Regex DoS limit missing | ReDoS via backtracking | Security | S | None | R2 | Open |
| F-37 | P2 | Low | Python | Source-confirmed | API keys plain text in config | Credential exposure | Security | S | None | R2 | Open |
| F-38 | P3 | — | Architecture | Source-confirmed | `http.server` single-threaded | Performance degradation | Scale | M | None | R3 | Open |
| F-39 | P3 | Info | Python | Unit-tested | Radon CC D-complexity functions | Higher bug risk | Maint. | M | None | R3 | Open |
| F-40 | P3 | Info | Performance| Unverified | No reproducible benchmark | Performance regressions silent | Quality | M | None | R3 | Open |
| F-41A | P1 | — | Python | Command-confirmed | mypy baseline | Type errors accumulate | Quality | M | F-03A | R1 | Open |
| F-41B | P2 | — | Python | Command-confirmed | mypy burn-down (critical pkgs) | Type errors accumulate | Quality | M | F-41A | R2 | Open |
| F-41C | P3 | — | Python | Command-confirmed | mypy burn-down (remaining) | Type errors accumulate | Quality | L | F-41B | R3 | Open |
| RM-01 | P3 | — | VS Code Ext | Source-confirmed | Non-blocking VS Code indexing | Host blocked | UX | M | None | R3 | Open |
| RM-02 | P4 | — | Docs | Source-confirmed | Public compatibility policy | Unclear stability | Maint. | M | None | R4 | Open |
| RM-03 | P4 | — | CI/CD | Source-confirmed | Release automation | Manual publishing risk | CI | L | None | R4 | Open |
| RM-04 | P4 | — | CI/CD | Source-confirmed | Reproducible builds | Artifact drift | Reprod. | M | None | R4 | Open |
| RM-05 | P4 | — | CI/CD | Source-confirmed | Artifact signing | Supply chain tampering | Security | M | None | R4 | Open |
| RM-06 | P4 | — | Docs | Source-confirmed | Migration documentation | User breakages | Docs | M | None | R4 | Open |
| RM-07 | P4 | — | CI/CD | Source-confirmed | Supported-platform qualification | Untested combinations | Quality | M | None | R4 | Open |
| RM-08 | P4 | — | Architecture | Source-confirmed | Plugin API stability | Unstable APIs | Maint. | M | None | R4 | Open |

*(Note: Preconditions and User Interaction columns omitted in this table for space, detailed explicitly in 06-security-audit.md)*

---

## Removed Findings (was in v1, not in v2)

| Former ID | Reason for removal |
|-----------|-------------------|
| F-21 | False positive — confirmed via `execFile` argv analysis |
| F-10 (npm) | Incorrect — F-10 is `web/server.py`. npm advisories tracked via `SEC-10`. |

---

## Finding ID Cross-Reference

See `12-traceability-audit.md` for full traceability matrix.
