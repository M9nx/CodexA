"""Tests for utils/logging module."""

from __future__ import annotations

import logging

from semantic_code_intelligence.utils.logging import (
    console,
    error_console,
    get_logger,
    setup_logging,
)


class TestSetupLogging:
    """Tests for logging setup."""

    def test_setup_logging_default(self):
        logger = setup_logging(verbose=False)
        assert logger.level == logging.INFO

    def test_setup_logging_verbose(self):
        logger = setup_logging(verbose=True)
        assert logger.level == logging.DEBUG

    def test_setup_returns_logger(self):
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "codexa"


class TestGetLogger:
    """Tests for logger retrieval."""

    def test_get_root_logger(self):
        logger = get_logger()
        assert logger.name == "codexa"

    def test_get_child_logger(self):
        logger = get_logger("test")
        assert logger.name == "codexa.test"

    def test_get_nested_child_logger(self):
        logger = get_logger("cli.init")
        assert logger.name == "codexa.cli.init"


class TestConsoles:
    """Tests for console instances."""

    def test_console_exists(self):
        assert console is not None

    def test_error_console_uses_stderr(self):
        assert error_console.stderr is True
