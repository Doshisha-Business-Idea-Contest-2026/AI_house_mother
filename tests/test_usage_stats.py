"""Unit tests for :mod:`src.services.usage_stats` (FR-P3 extension).

Cover the counter increments, month-bucket isolation, 0-fill of
``get_month``, and invalid event-type rejection. See
``docs/05_data_model.md`` §4.14.

Style follows ``tests/test_sponsored.py``: no pytest fixtures; each
test class redirects ``src.services.storage.DATA_DIR`` to a temp path
in ``setup_method`` and restores it in ``teardown_method`` so the real
``data/`` directory is never touched.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.services import storage, usage_stats


class _TempDataDirMixin:
    def setup_method(self) -> None:
        self._orig_data_dir = storage.DATA_DIR
        self._tmp = Path(tempfile.mkdtemp(prefix="ai_house_mother_test_"))
        storage.DATA_DIR = self._tmp

    def teardown_method(self) -> None:
        storage.DATA_DIR = self._orig_data_dir
        shutil.rmtree(self._tmp, ignore_errors=True)


_JST = ZoneInfo("Asia/Tokyo")


class TestRecord(_TempDataDirMixin):
    def test_first_record_creates_bucket_and_counts_one(self) -> None:
        now = datetime(2026, 7, 15, 12, 0, tzinfo=_JST)
        usage_stats.record("U-abc", "life", now_jst=now)
        month = usage_stats.get_month("U-abc", "2026-07")
        assert month == {"life": 1, "activity": 0, "post": 0, "profile": 0}

    def test_repeated_record_accumulates(self) -> None:
        now = datetime(2026, 7, 15, 12, 0, tzinfo=_JST)
        for _ in range(3):
            usage_stats.record("U-abc", "activity", now_jst=now)
        assert usage_stats.get_month("U-abc", "2026-07")["activity"] == 3

    def test_month_buckets_are_isolated(self) -> None:
        usage_stats.record(
            "U-abc", "life", now_jst=datetime(2026, 6, 30, 12, 0, tzinfo=_JST)
        )
        usage_stats.record(
            "U-abc", "life", now_jst=datetime(2026, 7, 1, 0, 5, tzinfo=_JST)
        )
        assert usage_stats.get_month("U-abc", "2026-06")["life"] == 1
        assert usage_stats.get_month("U-abc", "2026-07")["life"] == 1

    def test_users_are_isolated(self) -> None:
        now = datetime(2026, 7, 15, 12, 0, tzinfo=_JST)
        usage_stats.record("U-abc", "post", now_jst=now)
        usage_stats.record("U-def", "post", now_jst=now)
        assert usage_stats.get_month("U-abc", "2026-07")["post"] == 1
        assert usage_stats.get_month("U-def", "2026-07")["post"] == 1

    def test_invalid_event_type_raises(self) -> None:
        raised = False
        try:
            usage_stats.record("U-abc", "not-a-valid-event")
        except ValueError:
            raised = True
        assert raised


class TestGetMonth(_TempDataDirMixin):
    def test_missing_user_returns_zero_filled(self) -> None:
        assert usage_stats.get_month("U-unknown", "2026-07") == {
            "life": 0,
            "activity": 0,
            "post": 0,
            "profile": 0,
        }

    def test_missing_month_returns_zero_filled(self) -> None:
        usage_stats.record(
            "U-abc",
            "life",
            now_jst=datetime(2026, 7, 15, 12, 0, tzinfo=_JST),
        )
        assert usage_stats.get_month("U-abc", "2026-06") == {
            "life": 0,
            "activity": 0,
            "post": 0,
            "profile": 0,
        }

    def test_partial_month_bucket_gets_zero_filled(self) -> None:
        # A month that only has one event type recorded should still
        # report the other three as 0 (defensive against forward-compat
        # writes that predate a new event_type addition).
        usage_stats.record(
            "U-abc",
            "activity",
            now_jst=datetime(2026, 7, 15, 12, 0, tzinfo=_JST),
        )
        month = usage_stats.get_month("U-abc", "2026-07")
        assert month["activity"] == 1
        assert month["life"] == 0
        assert month["post"] == 0
        assert month["profile"] == 0
