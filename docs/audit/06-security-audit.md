# 06 — Security Audit (Corrected v2)

**Correction date:** 2026-07-22  
**Changes from v1:**
- F-01 severity corrected to Medium (requires user interaction — user must invoke a CodexA command)
- F-02 severity corrected to Low (requires escapeHtml bypass, which has not been demonstrated)
- F-21 (CLI arg injection) removed — confirmed false positive
- Added SEC-10 as a dedicated finding for npm dev-dependency advisories
- Removed unsupported Bandit claim about "no CVEs in Python dependencies"
- Added `pip-audit` result (no known vulns in `requirements.txt`)
- Added explicit `cargo audit` blocked status
- Separated security severity, release priority, exploit preconditions, and interaction requirements

---

## Security Findings Register

| ID | Security Severity | Release Priority | Component | Exploit Preconditions | User Interaction Required | Reachability | Classification | Recommended Fix |
|----|------------------|-----------------|-----------|----------------------|--------------------------|--------------|----------------|-----------------|
| SEC-01 (= F-02) | **Low** | P1 | VS Code Extension | `escapeHtml()` must be bypassed; result must be rendered in a webview | User must receive crafted data in search/tool result | Reachable if escaping is bypassed | Defense-in-depth gap | Add nonce-based CSP `<meta>` to all webview HTML |
| SEC-02 (= F-01) | **Medium** | P1 | VS Code Extension | Attacker controls workspace; `.venv/Scripts/codexa.exe` exists in workspace root | User must **invoke** a CodexA command | Reachable: any workspace containing the crafted binary | Confirmed weakness | Check `vscode.workspace.isTrusted` before `execFile` |
| SEC-03 | **Removed** | — | — | **FALSE POSITIVE** — `execFile` argv; `split("=", 1)`; no secondary CLI parsing | — | — | — | — |
| SEC-04 (= F-36) | **Low** | P2 | Python | User supplies crafted regex pattern; Python `re` fallback must be active | User must supply pattern via `codexa grep` | Reachable if ripgrep is absent | Confirmed weakness | Add pattern-length limit (e.g., ≤ 500 chars) |
| SEC-05 (= F-30) | **Low** | P2 | Python | URL source must be attacker-controlled (config file or path traversal) | N/A (server-side) | Reachable only if config is attacker-controlled | Defense-in-depth gap | Validate scheme with `urlparse`: `if urlparse(url).scheme not in ("http", "https"): raise ValueError("Invalid URL scheme")` |
| SEC-06 (= F-18) | **Low** | P1 | Python | Python must be run with `-O` flag | N/A | Reachable only with `-O` flag; not typical for CLI use | Code standards violation | Replace `assert` with `if query_embedding is None: raise ValueError(...)` |
| SEC-07 (= F-23) | **Low** | P2 | Rust | ONNX `--features onnx` must be enabled at build time | N/A (build-time) | Build-time only; ONNX is an optional feature | Confirmed weakness | Pin ONNX binary version; verify checksum; or disable `download-binaries` |
| SEC-08 (= F-24) | **Info** | P2 | GitHub Actions | Upstream action's tag must be hijacked | N/A (CI pipeline) | Build/deploy time only | Defense-in-depth gap | Pin all `uses:` to commit SHA |
| SEC-09 (= F-27) | **Info** | P2 | Python deps | N/A | N/A | CI only | Defense-in-depth gap | Commit `uv.lock`; use `uv sync --frozen` in CI |
| SEC-10 | **Info** | P1 | Node.js / VS Code Extension | Dev-only; not in built extension | N/A | **Not reachable** in packaged extension | Dependency-scope exposure (dev toolchain only) | See detailed table below |
| SEC-11 (= F-28) | **Unknown** | P2 | Rust | N/A | N/A | Unknown — `cargo audit` not run | Requires validation | Install `cargo-audit`; run `cargo audit` in CI |
| SEC-12 (= F-37) | **Low** | P2 | Python | Config file must be committed to version control | N/A | Only if repo is shared | Operational risk | Document env-var override; add warning if key found in config on `init` |

---

## Detailed Analysis

### SEC-01 — Missing Content Security Policy in Webviews

**Security severity: Low**  
**Status:** Confirmed defense-in-depth gap. No exploit demonstrated.

All four webview HTML strings lack a CSP `<meta>` tag. The existing `escapeHtml()` in `SHARED_JS` provides the primary XSS defense and is correctly applied before all `innerHTML` assignments.

**Why Low (not Medium/High):** No bypass of `escapeHtml()` has been found. The CSP gap means there is no secondary defense, but the primary defense is present.

**Remediation:** Add per-webview nonce; inject as TypeScript constant; reference in CSP `<meta>` and `<script nonce="...">` tags. This is a VS Code best-practice requirement, not an immediate exploit risk.

---

### SEC-02 — Workspace Trust Not Checked Before Binary Execution

**Security severity: Medium**  
**Status:** Confirmed weakness. Reachable. Requires user action.

```typescript
function codexBin(): string {
  // No workspace trust check
  const venvBin = isWin
    ? path.join(root, ".venv", "Scripts", "codexa.exe")
    : path.join(root, ".venv", "bin", "codexa");
  if (fs.existsSync(venvBin)) { return venvBin; }
  return "codexa";
}
```

**Important correction from v1:** The binary is **not executed automatically on workspace open**. It is executed only when the user invokes a CodexA command (search, quality, index, etc.). This reduces severity from High to Medium because:
- User must take action after opening the workspace
- VS Code displays extension activation indicators

**Precondition:** Attacker provides a repository (e.g., via clone) containing `.venv/Scripts/codexa.exe`. User opens the repository and invokes any CodexA command.

**Remediation:**
```typescript
function codexBin(): string {
  if (!vscode.workspace.isTrusted) {
    throw new Error("CodexA: not available in untrusted workspaces. Mark workspace as trusted to enable.");
  }
  // existing resolution logic unchanged
}
```

---

### SEC-03 — CLI Argument Injection (FALSE POSITIVE — REMOVED)

**Investigation:**

The extension passes `["--arg", "symbol_name=${msg.symbol}"]` to `execFile`. `execFile` passes each array element as a distinct OS-level argument. The string `"symbol_name=SomeClass --json --force"` reaches `tool_cmd.py` as a **single string** in the `arg` tuple.

`tool_cmd.py:132`:
```python
key, value = a.split("=", 1)   # maxsplit=1 — splits only on first =
arguments[key.strip()] = value.strip()  # value goes directly into dict
```

The value is placed directly into `arguments["symbol_name"]` as a plain string. There is no secondary CLI-flag parsing. A crafted value cannot inject additional flags.

**Conclusion:** F-21 is a false positive. No remediation required. The `--` separator proposed in v1 was **incorrect** because there is no `--` support in this command structure, and inserting it would break the parser.

---

### SEC-10 — npm Dev-Dependency Advisories (Detailed)

**Before `npm audit fix`:** 10 high-severity advisories (5 packages)  
**After `npm audit fix`:** 6 high-severity advisories (1 package chain) — 4 packages resolved

| Package | Advisories | Severity | Dependency Path | Scope | Fix Available | Breaking Risk | Decision |
|---------|-----------|----------|-----------------|-------|--------------|---------------|----------|
| `minimatch` 9.0.0–9.0.6 | GHSA-3ppc-4f35-3m26, GHSA-7r86-cg39-jmmj, GHSA-23c5-xmqv-rm74 (ReDoS) | High | `minimatch` → `@typescript-eslint/typescript-estree@6.x` → `eslint-plugin@6.x` + `parser@6.x` | **Dev only** | Requires `@typescript-eslint` v8 + ESLint v9 upgrade | **High** (coordinated major upgrade) | **Accept risk** — dev-only; not in built extension; fix is a coordinated major version upgrade |
| `brace-expansion` | GHSA-f886-m6hf-6m8v, GHSA-3jxr-9vmj-r5cp | High | `eslint` transitive | **Dev only** | `npm audit fix` (safe) | Low | ✅ **Fixed** by `npm audit fix` |
| `flatted` | GHSA-rf6f-7fwh-wjgh | High | ESLint cache dep | **Dev only** | `npm audit fix` (safe) | Low | ✅ **Fixed** |
| `js-yaml` | GHSA-h67p-54hq-rp68, GHSA-52cp-r559-cp3m | High | ESLint transitive | **Dev only** | `npm audit fix` (safe) | Low | ✅ **Fixed** |
| `picomatch` | GHSA-3v7f-55p6-f55p, GHSA-c2c7-rcm5-vvqj | High | ESLint transitive | **Dev only** | `npm audit fix` (safe) | Low | ✅ **Fixed** |

**Post-fix state:**
- `npm audit --omit=dev` → **0 vulnerabilities** ✅
- `npm audit` (all) → **6 high** (all in `minimatch` / `@typescript-eslint` chain, dev-only)
- `npm run compile` → **0 errors** ✅ (verified after fix)

**Accepted-risk statement for remaining 6 advisories:**  
The 6 remaining minimatch-chain advisories are dev-only (used only during `npm run lint`). They are not included in the built extension (`out/extension.js`). The fix requires upgrading `@typescript-eslint` from v6 to v8 and `eslint` from v8 to v9, which is a coordinated breaking change requiring a separate R2 work item. The risk to end users is **zero**; the risk to developer CI is limited to ReDoS in ESLint glob processing, which is not a user-reachable path.

**Waiver:**  
- Owner: Engineering Lead  
- Rationale: Dev-only; not reachable in built extension  
- Compensating control: `npm audit --omit=dev` passes (0 production vulns)  
- Expiration: R2 work item to upgrade `@typescript-eslint` v8 + ESLint v9  

---

### Python Dependency Audit

**Tool:** `pip-audit` (installed this session via `uv tool install pip-audit`)  
**Scope:** `requirements.txt` (production core dependencies)  
**Result:** No vulnerabilities were reported in the attempted `requirements.txt` audit, but the evidence metadata must be reconciled.  
**Evidence:** `docs/audit/evidence/security/pip-audit.txt`

**Important limitation:** `pip-audit` was run against `requirements.txt` only. The full installed environment (including `ml`, `dev`, `tui` extras) was not audited. `uv.lock` exists locally but is untracked and not committed or enforced by CI, preventing lockfile-based audit. Bandit does NOT provide dependency CVE status and was not used for this assessment.

---

### Rust Dependency Audit

**Status: Environment-blocked.**  
`cargo-audit` is not installed in this audit environment. The Rust crate supply chain cannot be confirmed clean. This is an **open risk** until `cargo audit` is run in CI.

Evidence from `Cargo.lock` inspection (not a substitute for `cargo audit`):  
- `pyo3` pinned at 0.22.6 — no CVEs found in manual check  
- `instant-distance` pinned at 0.6.1 — no CVEs found in manual check  
- 77 total crates locked  

**Required action:** Install `cargo-audit` in CI; add `cargo audit` step to `ci.yml`.
