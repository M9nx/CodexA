"""Tests for the command router."""

from __future__ import annotations

import click
import pytest

from semantic_code_intelligence.cli.router import register_commands


class TestRouter:
    """Tests for command registration."""

    def test_register_commands_adds_all(self):
        group = click.Group(name="test")
        register_commands(group)

        command_names = list(group.commands.keys())
        assert "init" in command_names
        assert "index" in command_names
        assert "search" in command_names

    def test_register_commands_count(self):
        group = click.Group(name="test")
        register_commands(group)
        assert len(group.commands) == 30

    def test_registered_commands_are_click_commands(self):
        group = click.Group(name="test")
        register_commands(group)

        for name, cmd in group.commands.items():
            assert isinstance(cmd, click.Command), f"{name} is not a click.Command"

    def test_register_to_empty_group(self):
        group = click.Group(name="empty")
        assert len(group.commands) == 0
        register_commands(group)
        assert len(group.commands) > 0
