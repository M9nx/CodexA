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

`unit` is the only marker applied so far. Measured on this commit with 2683
collected tests:

| command | result |
| --- | --- |
| `pytest` | 2683 selected — unchanged, and this is what CI runs |
| `pytest -m unit` | 312 selected, 2371 deselected, passes in about 1 second |
| `pytest -m integration` | 0 selected, pytest exits 5 |

287 test functions carry `unit`: 119 in five files marked at module level, and
168 marked individually. Those 287 functions expand to 312 test items because
some are parametrized.

The `unit` group is deliberately conservative. A test only qualifies if neither
its own body, nor the fixtures it requests, nor any same-module helper it calls
touches the network, a subprocess, a real model, FAISS, the clock, threads, or
the real filesystem. A fast selection is therefore a strong signal, not a
guarantee, until `integration`, `model` and `http` markers exist.

Groups that are not yet marked (`integration`, `e2e`, `model`, `http`,
`platform`, `compat`, `slow`) currently select nothing.

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
