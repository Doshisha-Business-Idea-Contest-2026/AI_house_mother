"""Unit tests for :func:`src.services.storage.locked_edit` (Issue #45).

Focuses on the invariants a caller can rely on regardless of
concurrency: the CM yields the parsed value, persists on clean exit,
skips saving when the block raises, honours ``default`` on a missing
file, and creates its sidecar lock file. Concurrency itself is exercised
by ``tests/test_storage_concurrency.py``.

Style follows ``tests/test_posts.py``: no pytest fixtures, class-based,
``storage.DATA_DIR`` redirected to a temp path.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from src.services import storage


class _TempDataDirMixin:
    def setup_method(self) -> None:
        self._orig_data_dir = storage.DATA_DIR
        self._tmp = Path(tempfile.mkdtemp(prefix="ai_house_mother_test_"))
        storage.DATA_DIR = self._tmp

    def teardown_method(self) -> None:
        storage.DATA_DIR = self._orig_data_dir
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestLockedEditBasics(_TempDataDirMixin):
    def test_yields_default_when_file_missing(self) -> None:
        with storage.locked_edit("nope.json", default={"seed": True}) as data:
            assert data == {"seed": True}
            data["written"] = True

        # The CM persisted the mutated dict.
        written = json.loads((self._tmp / "nope.json").read_text(encoding="utf-8"))
        assert written == {"seed": True, "written": True}

    def test_yields_existing_content_and_persists_changes(self) -> None:
        (self._tmp / "u.json").write_text(
            json.dumps({"users": {"U1": {"role": "student"}}}), encoding="utf-8"
        )
        with storage.locked_edit("u.json") as data:
            assert data == {"users": {"U1": {"role": "student"}}}
            data["users"]["U2"] = {"role": "parent"}

        after = json.loads((self._tmp / "u.json").read_text(encoding="utf-8"))
        assert after["users"]["U2"] == {"role": "parent"}
        assert after["users"]["U1"] == {"role": "student"}

    def test_exception_inside_block_skips_save(self) -> None:
        (self._tmp / "u.json").write_text(
            json.dumps({"users": {"U1": {"role": "student"}}}), encoding="utf-8"
        )

        class _Boom(Exception):
            pass

        try:
            with storage.locked_edit("u.json") as data:
                data["users"]["U2"] = {"role": "parent"}
                raise _Boom("simulated failure mid-mutation")
        except _Boom:
            pass

        # The file must be untouched — an exception in the block must
        # not leave a partial mutation on disk.
        after = json.loads((self._tmp / "u.json").read_text(encoding="utf-8"))
        assert after == {"users": {"U1": {"role": "student"}}}

    def test_creates_sidecar_lock_file(self) -> None:
        with storage.locked_edit("posts.json", default={"posts": []}):
            pass

        lock_path = storage._lock_path_for("posts.json")
        assert lock_path.exists(), "sidecar lock file must be created"
        assert lock_path.parent.name == ".locks"

    def test_lock_path_follows_data_dir_monkeypatch(self) -> None:
        # The DATA_DIR patch is already active via the mixin; asserting
        # that _lock_path_for evaluates DATA_DIR every call means a
        # future test that redirects DATA_DIR at runtime keeps working.
        first = storage._lock_path_for("posts.json")
        assert first.parent == self._tmp / ".locks"

        # Point DATA_DIR at another temp dir mid-test and verify the
        # helper picks it up without re-import.
        second_dir = Path(tempfile.mkdtemp(prefix="ai_house_mother_test_"))
        try:
            storage.DATA_DIR = second_dir
            second = storage._lock_path_for("posts.json")
            assert second.parent == second_dir / ".locks"
        finally:
            shutil.rmtree(second_dir, ignore_errors=True)
