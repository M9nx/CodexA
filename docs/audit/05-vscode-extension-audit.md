# 05 — VS Code Extension Audit (Corrected v2)

**Correction date:** 2026-07-22

## Commands Executed

```bash
cd vscode-extension
npm.cmd install             # Completed successfully
npm.cmd run compile         # tsc -p ./ — PASSED, exit 0, no errors
npm.cmd run lint            # FAILED — ESLint: no configuration file found
npm.cmd audit               # 6 high severity vulnerabilities (after npm audit fix)
npm.cmd audit --omit=dev    # found 0 vulnerabilities
npm.cmd outdated            # Multiple packages outdated
```

---

## 1. TypeScript Compilation

**Status:** ✅ Compiles cleanly with zero errors.

`tsc -p ./` produces `out/extension.js` successfully. The TypeScript code is syntactically and type-system valid.

---

## 2. ESLint Configuration

**Status:** ❌ Missing `.eslintrc` or ESLint flat config file.

**Finding:** The `package.json` defines `"lint": "eslint src --ext ts"` using ESLint 8. ESLint 8 requires a legacy `.eslintrc.*` file (flat config was introduced in ESLint 9). No such file exists.

**Correct fix:** Create `.eslintrc.js` with `@typescript-eslint` integration — not ESLint 9 flat config (which would require upgrading ESLint).

The `@typescript-eslint` packages are version 6.x which is compatible with ESLint 8. An upgrade to v8.x `@typescript-eslint` packages requires ESLint v9.

---

## 3. npm Dependency Audit

### Production Dependencies: `npm audit --omit=dev`

**Result: 0 vulnerabilities** ✅

The extension has **no production runtime dependencies** — all packages listed are `devDependencies`.

### Dev Dependencies: `npm audit` (all)

**Result: 6 vulnerabilities (after `npm audit fix`)** ⚠️

All 6 remaining vulnerabilities are in the `minimatch` dependency chain (used by `@typescript-eslint`).
**All 6 vulnerabilities are in dev-only dependencies** (ESLint toolchain). They are **not reachable in the packaged extension** and do not affect end users.

**Recommended fix:** A coordinated major version upgrade of `@typescript-eslint` to v8 and `eslint` to v9 in Release 2.

---

## 4. Extension Architecture Analysis

### Structure
The entire extension (`1,121 lines`) is a single TypeScript file: `src/extension.ts`. This contains:
- Binary resolution logic (`codexBin()`)
- CLI runner wrapper (`runCodex()`)
- 4 webview providers (Search, Symbols, Quality, Tools)
- 8 command handlers
- All inline HTML/CSS/JS for webviews (~800 lines of embedded strings)

### Commands Registered vs. Documented

| Command ID | Title | Backend Operation | Status |
|-----------|-------|------------------|--------|
| `codexa.search` | Search Codebase | `codexa search --json` | Functional |
| `codexa.askCodexA` | Ask a Question | `codexa ask --json` | Functional |
| `codexa.callGraph` | Show Call Graph | `codexa tool run get_call_graph` | Functional |
| `codexa.models` | List Models | `codexa models list --json` | Functional |
| `codexa.quality` | Code Quality Analysis | `codexa quality --json` | Functional |
| `codexa.explainSymbol` | Explain Symbol at Cursor | `codexa tool run explain_symbol` | **Partial** — reads word at cursor but has no fallback if no word |
| `codexa.doctor` | Doctor (Health Check) | `codexa doctor --json` | Functional |
| `codexa.index` | Re-Index Codebase | `codexa index` | Functional |
| **README claims CodeLens** | — | — | ❌ **Not implemented in source** |

---

## 5. Security and Reliability Findings

#### 1. Workspace Trust Not Checked — P1

`codexBin()` checks for a `.venv/Scripts/codexa.exe` relative to workspace root, then falls back to `"codexa"` on PATH.
The extension **executes this binary only when the user invokes a CodexA command** (it does not execute automatically on workspace open).
However, the extension does not check `vscode.workspace.isTrusted` before executing the binary. If a malicious repository contains a `.venv/Scripts/codexa.exe`, a user invoking a command will execute the attacker's binary.

#### 2. No Content Security Policy (CSP) in Webviews — P1

All four webview providers set only `enableScripts: true`. No CSP `<meta>` tag is set in any webview HTML. The current webviews render untrusted content using `escapeHtml()`, but the absence of a CSP means any XSS bypass would have no secondary defense.

#### 3. Message Validation — P2

Incoming `postMessage` events from webviews are validated by `msg.type` checks, but the `msg` payload is not schema-validated. A bug in the webview JS could post malformed data to the extension host.

#### 4. No Cancellation Support — P2

All async operations (`runCodex`) have no cancellation token. If a user triggers multiple searches or quality analyses rapidly, they queue up with no way to cancel. Long-running commands block the extension host.

#### 5. Argument Injection Risk (FALSE POSITIVE) — Removed

_Historical note:_ It was previously thought that CLI arguments constructed via `["tool", "run", "explain_symbol", "--arg", \`symbol_name=${msg.symbol}\`]` were vulnerable to flag injection. This is a **false positive**. The use of the `execFile` array combined with `a.split("=", 1)` in Python `tool_cmd.py` ensures the value is placed strictly into the arguments dictionary without secondary flag parsing. No remediation is required.

---

## 6. Extension Activation and Cleanup

- Activation events are properly scoped: `onCommand:codexa.search`, `onView:*`
- **Missing:** Neither `statusBarItem` nor `outputChannel` are added to `context.subscriptions`. They will not be properly disposed when the extension is deactivated (Memory leak on deactivation).

---

## 7. Multi-root Workspace and Remote Compatibility

The extension uses `vscode.workspace.workspaceFolders?.[0]?.uri.fsPath` — this only uses the first workspace folder. In multi-root workspaces, this is a silent limitation. Remote workspace compatibility (SSH, WSL, Containers) is not addressed.
