# Testing

CodexA ships one full test suite that runs on every pull request across
Ubuntu and Windows on Python 3.11, 3.12 and 3.13. The test taxonomy exists so
that individual groups can be selected, measured and reused later without
changing what the required gate runs.

This page describes the marker vocabulary. It does not yet describe which
individual tests carry which marker — classification is applied incrementally in
follow-up work.

## Running the suite

```bash
# everything, exactly as CI runs it
pytest

# a single file or a single test
pytest semantic_code_intelligence/tests/test_chunker.py
pytest semantic_code_intelligence/tests/test_chunker.py::TestChunker::test_split
```

Pytest configuration lives in `pyproject.toml` under `[tool.pytest.ini_options]`:
`testpaths` points at `semantic_code_intelligence/tests`, `pythonpath` adds the
repository root, and the markers below are registered there.

## Markers

Markers are **orthogonal**, not a single bucket list. One test may carry
several, which is what allows precise selection later.

| Marker | Meaning |
| --- | --- |
| `unit` | Pure in-process logic with no external process, network or model |
| `integration` | Multiple in-process components exercised together, such as index and search, the vector store, or plugins |
| `e2e` | Full user journeys across the CLI and indexing pipeline |
| `model` | Loads a real sentence-transformers model; slow, and needs the model artifact on first run |
| `http` | Starts an HTTP server or issues HTTP requests |
| `platform` | Behaviour that is specific to an operating system or runtime |
| `compat` | Python version compatibility surface |
| `slow` | Cross-cutting marker for tests expected to take roughly 30 seconds or more |

`slow` is deliberately an attribute rather than a category: a `model` test is
usually also `slow`, and both facts are useful when selecting.

There is intentionally **no `smoke` marker**. A fast subset is better expressed
as a selection, so the definition cannot drift away from reality:

```bash
pytest -m "not slow and not model"   # fast subset
```

List everything pytest knows about, including the registered markers:

```bash
pytest --markers
```

## Selecting groups

```bash
pytest -m unit                  # one group
pytest -m "unit or integration" # several groups
pytest -m "not slow"            # exclude a group
pytest -m "model and not slow"  # combine dimensions
```

An empty selection is not an error in itself, but note that pytest exits with
code 5 when no tests are collected, which CI treats as a failure. Always confirm
a new selection actually matches something:

```bash
pytest -m unit --collect-only -q
```

## Current state

`unit`, `integration`, `model`, `http` and `slow` are applied. Measured on this
commit with 2683 collected tests:

| command | result |
| --- | --- |
| `pytest` | 2683 selected — unchanged, and this is what CI runs |
| `pytest -m unit` | 312 selected, passes in about 1 second |
| `pytest -m integration` | 493 selected |
| `pytest -m model` | 33 selected |
| `pytest -m http` | 5 selected |
| `pytest -m slow` | 1 selected |
| `pytest -m platform` | 0 selected |
| `pytest -m compat` | 0 selected |
| `pytest -m "unit or integration or model or http"` | 843 selected |

Each group runs and passes on its own, so a group can be used as a quick local
check or as the basis for a later CI split.

### The smoke selection

There is deliberately no `smoke` marker, because a definition expressed as a
selection cannot drift away from the tests. Two useful shapes, measured from CI
per-test durations (2683 tests, 204.2 s of summed test time in one cell):

| selection | tests | time | share of suite |
| --- | --- | --- | --- |
| `pytest` | 2683 | 204.2 s | 100 % |
| `pytest -m "not slow and not model"` | 2650 | 37.5 s | 18.4 % |
| `pytest -m "unit or integration or http"` | 810 | 7.4 s | 3.6 % |
| `pytest -m unit` | 312 | 0.3 s | 0.1 % |

The first is the practical smoke gate: it runs 98 % of the suite in under a
fifth of the time, because the 33 `model` tests alone account for 81.6 % of
suite runtime. The second is a much faster, narrower gate if that is ever
needed.

### Platform and version coverage

`platform` and `compat` are registered but **currently select nothing**, and
that is a real finding rather than an unfinished job:

- The test suite contains no `sys.platform`, `platform.system()`, `os.name`,
  `sys.version_info` or `skipif` logic at all.
- All six matrix cells report identical results: 2683 collected, 2678 passed,
  5 skipped, with the *same five* tests skipped on every cell. Those five are
  skipped by `pytest.importorskip("mcp")`, which does not depend on the OS or
  the Python version.
- The only two tests with a platform in their name,
  `test_uri_to_path_unix` and `test_uri_to_path_windows`, are plain
  input-parsing tests that pass identically everywhere.

So today every test runs on every OS and every supported Python version, and
none of them is conditional on either. Adding those tests is tracked under
platform coverage and Python compatibility work, not here.

### How tests are classified

`unit` is decided statically: a test qualifies only if neither its own body, nor
the fixtures it requests, nor any same-module helper it calls touches the
network, a subprocess, a real model, FAISS, the clock, threads, or the real
filesystem.

Static analysis has a known blind spot: a heavy dependency loaded *dynamically*
inside production code is invisible. One test was classified this way.
`test_phase20.py::TestToolRegistryInvocations::test_invoke_semantic_search_no_index`
takes **177.65 s on average on CI** because `ToolRegistry.invoke("semantic_search")`
loads a real embedding model, yet nothing in the test file mentions one. It is
marked `model` and `slow` on the strength of the JUnit duration evidence
produced by CI, not on static analysis.

`integration`, `model` and `http` are assigned from the resolved closure signals
by priority: HTTP server or socket first, then a real model or FAISS, then
anything else that needs the real environment. A test may carry more than one
marker.

### Not yet classified

- `e2e` — roughly 100 CLI tests that shell out to the `codexa` binary and touch
  the real home directory are deliberately still unmarked.
- `platform`, `compat` — nothing to classify yet; see
  [Platform and version coverage](#platform-and-version-coverage).
- About 1715 tests have no marker at all. Most look unit-like by the static
  rule, but they sit in the same category as the one test above that static
  analysis got wrong, so they are held back until each can be confirmed by
  evidence rather than by scanning.

## Adding a marker to a test

```python
import pytest

@pytest.mark.integration
@pytest.mark.slow
def test_index_then_search(tmp_path):
    ...
```

Module-level markers apply to every test in the file:

```python
pytestmark = [pytest.mark.e2e]
```

## Relationship to CI

CI currently runs the full suite on every matrix cell and does not select by
marker. The taxonomy exists to make later, evidence-based selection possible;
the required gate is the `ci-required` check, and reducing what runs under it is
a separate, explicitly validated step.
