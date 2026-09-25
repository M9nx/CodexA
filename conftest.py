"""Session-wide test isolation.

Two pieces of global state leak between tests in this suite:

1. **Logging configuration.** ``semantic_code_intelligence.utils.logging.setup_logging``
   calls ``logging.basicConfig(...)``, which mutates the *root* logger. Because
   ``basicConfig`` is a no-op once the root logger has handlers, whichever test
   configures logging first decides the level for the whole run. Tests that
   capture CLI output with ``CliRunner`` then see log records mixed into
   ``result.output``, which broke three ``test_phase17`` JSON assertions when
   the suite ran in a different order.

2. **Randomness.** Several tests build fixtures with ``numpy.random`` and the
   standard library ``random`` module, and nothing seeded them, so vector-store
   and search assertions rested on whatever values the global RNG happened to
   produce.

The fixtures below restore logging and reseed the RNGs around every test, so no
test can depend on, or corrupt, either piece of global state.
"""

from __future__ import annotations

import logging
import random

import numpy as np
import pytest

# Fixed so failures are reproducible; any constant works as long as it never
# changes between runs.
RANDOM_SEED = 20250925


@pytest.fixture(autouse=True)
def _isolate_logging():
    """Restore the root logger's handlers and level after every test."""
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    filters = list(root.filters)
    try:
        yield
    finally:
        for handler in list(root.handlers):
            if handler not in handlers:
                root.removeHandler(handler)
                handler.close()
        for handler in handlers:
            if handler not in root.handlers:
                root.addHandler(handler)
        root.setLevel(level)
        root.filters = filters


@pytest.fixture(autouse=True)
def _deterministic_random():
    """Reseed ``random`` and ``numpy.random`` before every test.

    Function-scoped on purpose: each test gets the same sequence regardless of
    what ran before it, which is what removes order dependence.
    """
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    yield
