"""Unit tests for user-scoped activity proposal storage."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.services import activity_store, storage


class _TempDataDirMixin:
    def setup_method(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_data_dir = storage.DATA_DIR
        storage.DATA_DIR = Path(self._tmp.name)

    def teardown_method(self) -> None:
        storage.DATA_DIR = self._orig_data_dir
        self._tmp.cleanup()


class TestActivityStoreUserScope(_TempDataDirMixin):
    def test_same_title_keys_are_scoped_by_user(self) -> None:
        title = "地域清掃ボランティア"

        keys_a = activity_store.remember("U-a", [{"title": title, "summary": "A"}])
        keys_b = activity_store.remember("U-b", [{"title": title, "summary": "B"}])

        assert keys_a != keys_b
        assert activity_store.resolve(keys_a[0], "U-a") == {
            "title": title,
            "summary": "A",
        }
        assert activity_store.resolve(keys_b[0], "U-b") == {
            "title": title,
            "summary": "B",
        }

    def test_resolve_rejects_other_user_key(self) -> None:
        key = activity_store.remember(
            "U-owner", [{"title": "朝活", "summary": "owner only"}]
        )[0]

        assert activity_store.resolve(key, "U-other") is None
