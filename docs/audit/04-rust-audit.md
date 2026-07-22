# 04 — Rust Native Extension Audit (Corrected v2)

**Correction date:** 2026-07-22  
**Changes from v1:**
- Removed statement "expected to pass based on code inspection" — result is environment-blocked, not inferred
- Added required CI matrix
- Separated optional-feature test failures
- Removed `cargo audit` clean claim — blocked, not assessed

---

## Commands Executed

| Command | Exit Code | Status | Evidence |
|---------|-----------|--------|---------|
| `cargo clean --manifest-path codexa-core/Cargo.toml` | 0 | Completed — removed 2,473 files, 760.2 MiB | Prior session |
| `cargo fmt --check --manifest-path codexa-core/Cargo.toml` | 1 | Formatting differences found | `evidence/rust/cargo-fmt-check.txt` (prior session report) |
| `cargo test --manifest-path codexa-core/Cargo.toml` | 1 | **Environment-blocked** — linker error | `evidence/rust/cargo-test.txt` |
| `cargo clippy --manifest-path codexa-core/Cargo.toml` | 0 (warnings) | Style warnings; not errors | Prior session |
| `cargo audit` | **Not run** | `cargo-audit` not installed | Blocked |

---

## 1. Formatting (`cargo fmt --check`)

**Status:** ❌ Formatting differences detected (prior session, confirmed via retained diff).

**Files affected:** `src/ann.rs`, `src/ast_chunk.rs`, `src/tantivy_search.rs`

**Nature:** All purely cosmetic — line-length wrapping of chained method calls and function signatures. No logic differences.

**Fix:** `cargo fmt --manifest-path codexa-core/Cargo.toml` — automated; no logic change required.

---

## 2. Linting (`cargo clippy`)

**Status:** ⚠️ Style warnings present. No `#![deny(warnings)]` or `#![deny(clippy::all)]` in `lib.rs`.

**Required CI configuration:**
```bash
cargo clippy --all-targets --all-features -- -D warnings
```
This turns all clippy warnings into errors. This is not the current configuration. Adding `-D warnings` is a R1 work item (part of F-08 documentation/CI improvement).

---

## 3. Tests (`cargo test`) — Environment-Blocked

**Status:** ❌ **Build fails on this machine. Actual test result is unknown.**

**Confirmed diagnosis:** Windows MinGW toolchain (`x86_64-pc-windows-gnu`) cannot locate `lpython313` in its library search path. Python 3.13 is installed via the `py` launcher but its import library (`python313.lib`) is not accessible to MinGW's `ld.exe`.

**This is an environment defect on this machine, not a code defect.** The conclusion cannot be drawn from code inspection alone that tests would pass. The test outcome remains **unverified**.

**Root cause confirmed (from linker output):**
```
C:/msys64/mingw64/.../ld.exe: cannot find -lpython313: No such file or directory
```

**Fix options for this machine:**
1. Install Python 3.13 MSVC build and set `PYO3_PYTHON` to MSVC Python path
2. Switch Rust toolchain: `rustup default stable-x86_64-pc-windows-msvc`
3. Use WSL2 for Rust development
4. Rely on CI (GitHub Actions) for Rust test validation

**The CI `build-wheels.yml` uses MSVC runners and does not have this issue.** However, `cargo test` is not currently run in CI — only `maturin build` (wheel creation) is validated.

---

## 4. Required CI Matrix for Rust Tests

The following CI matrix must be added as a R1 work item.

**Feature Policy:**
* `tantivy-backend`: **Experimental**. Excluded from default release artifacts.
* `onnx`: **Experimental**. Excluded from default release artifacts due to supply-chain risk (downloads binaries at build time).

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    features: ["", "--no-default-features", "--features tantivy-backend", "--features onnx"]
    exclude:
      - os: windows-latest
        features: "--features onnx"
steps:
  - uses: actions/checkout@v4
  - name: Set up Python
    uses: actions/setup-python@v5
    with:
      python-version: '3.13'
  - name: cargo fmt check
    run: cargo fmt --check --manifest-path codexa-core/Cargo.toml

  - name: cargo clippy
    run: cargo clippy --manifest-path codexa-core/Cargo.toml --all-targets ${{ matrix.features }} -- -D warnings

  - name: cargo test
    run: cargo test --manifest-path codexa-core/Cargo.toml ${{ matrix.features }}
```

**Optional-feature failures:** Since `--features tantivy-backend` and `--features onnx` are marked Experimental and are not shipped in the default wheels, their failures should be resolved before stabilizing them, but `continue-on-error` must **not** be used in CI if they are ever included in supported release artifacts. Until stabilized, they can be run in a separate allowable-failure CI job or omitted from the primary release gate.

---

## 5. FFI Boundary Inspection — Source-Confirmed

### Panic Safety

All `#[pyfunction]` and `#[pymethods]` functions return `PyResult<T>`. PyO3 normally catches panics at Python callback boundaries and raises `PanicException`, which derives from `BaseException`. This prevents ordinary `except Exception` handlers from silently swallowing Rust panics. Undefined behavior from invalid unsafe memory access is not recoverable through this mechanism.

**Unsafe block in `ann.rs`:**
```rust
dot += unsafe { *data.get_unchecked(offset + j) } * unsafe { *q.get_unchecked(j) };
```
These unsafe blocks are bounded by array construction invariants (not re-verified at each access). A bug in index construction could cause undefined behaviour in release mode. This risk is low given the construction logic, but is noted.

### Error Message Leakage

Some error conversions include raw file paths (e.g., `format!("Load error: {e}")`), which could expose internal filesystem layout in exceptions returned to the Python caller.

---

## 6. Version Divergence — Source-Confirmed

| Component | Version |
|-----------|---------|
| Python package (`pyproject.toml`) | **0.5.0** |
| Rust crate (`codexa-core/Cargo.toml`) | **0.1.0** |
| VS Code Extension (`package.json`) | **0.2.0** |

These versions are independent. No mechanism enforces compatibility. API breakage between Rust and Python would manifest at runtime, not at import time.

---

## 7. Supply Chain — Partial Assessment

### Cargo.lock: Source-confirmed — 77 crates locked
- `pyo3` pinned at 0.22.6 — no CVEs found in manual review
- `tantivy` pinned at 0.22.x — no CVEs found in manual review
- `instant-distance` pinned at 0.6.1 — no CVEs found in manual review

### `cargo audit`: ENVIRONMENT-BLOCKED

`cargo-audit` is not installed in this audit environment. **The Rust supply chain cannot be declared clean.** This is an open risk.

**Required action:** `cargo install cargo-audit && cargo audit` in CI. See F-28.

### ONNX Binary Download

The `ort` crate uses `features = ["download-binaries"]`, which downloads pre-built ONNX Runtime binaries at build time from a remote host. The binary is not verified by checksum in the build script. See SEC-07 / F-23.
