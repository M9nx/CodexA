"""Tests for the hash store."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantic_code_intelligence.storage.hash_store import HashStore


class TestHashStore:
    """Tests for HashStore operations."""

    def test_empty_store(self):
        store = HashStore()
        assert store.count == 0
        assert store.get("file.py") is None

    def test_set_and_get(self):
        store = HashStore()
        store.set("file.py", "abc123")
        assert store.get("file.py") == "abc123"

    def test_has_changed_new_file(self):
        store = HashStore()
        assert store.has_changed("file.py", "hash1") is True

    def test_has_changed_same_hash(self):
        store = HashStore()
        store.set("file.py", "hash1")
        assert store.has_changed("file.py", "hash1") is False

    def test_has_changed_different_hash(self):
        store = HashStore()
        store.set("file.py", "hash1")
        assert store.has_changed("file.py", "hash2") is True

    def test_remove(self):
        store = HashStore()
        store.set("file.py", "hash1")
        store.remove("file.py")
        assert store.get("file.py") is None
        assert store.count == 0

    def test_remove_nonexistent_no_error(self):
        store = HashStore()
        store.remove("nonexistent.py")  # should not raise

    def test_count(self):
        store = HashStore()
        store.set("a.py", "h1")
        store.set("b.py", "h2")
        assert store.count == 2


class TestHashStorePersistence:
    """Tests for save/load."""

    def test_save_creates_file(self, tmp_path: Path):
        store = HashStore()
        store.set("file.py", "hash1")
        store.save(tmp_path)
        assert (tmp_path / "file_hashes.json").exists()

    def test_load_roundtrip(self, tmp_path: Path):
        store = HashStore()
        store.set("a.py", "h1")
        store.set("b.py", "h2")
        store.save(tmp_path)

        loaded = HashStore.load(tmp_path)
        assert loaded.count == 2
        assert loaded.get("a.py") == "h1"
        assert loaded.get("b.py") == "h2"

    def test_load_nonexistent_returns_empty(self, tmp_path: Path):
        loaded = HashStore.load(tmp_path / "nope")
        assert loaded.count == 0
