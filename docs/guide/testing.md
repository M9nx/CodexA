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

The markers are registered and documented, but **no test carries them yet**.
Measured on this commit with 2683 collected tests:

| command | result today |
| --- | --- |
| `pytest` | 2683 selected — unchanged, and this is what CI runs |
| `pytest -m unit` | 2683 deselected, **0 selected**, pytest exits 5 |
| `pytest -m "not slow and not model"` | 2683 selected (unmarked tests match negative markers) |

So a positive marker selection currently matches nothing until classification
lands. Nothing about CI changes, because CI runs a plain `pytest` with no `-m`
filter.

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
