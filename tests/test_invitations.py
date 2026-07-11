"""Unit tests for :mod:`src.services.invitations`.

Covers the leaf helpers (``is_expired``) directly. Handler-level
integration tests live in ``tests/test_handlers_invite_code.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.services import invitations
from src.services.invitations import JST


class TestIsExpiredAwareInput:
    def test_future_aware_datetime_is_not_expired(self) -> None:
        future = datetime.now(JST) + timedelta(hours=1)
        assert invitations.is_expired(future.isoformat()) is False

    def test_past_aware_datetime_is_expired(self) -> None:
        past = datetime.now(JST) - timedelta(hours=1)
        assert invitations.is_expired(past.isoformat()) is True


class TestIsExpiredNaiveInput:
    """Naive datetime handling (Issue #57).

    ``issue_code`` always emits ``_iso(_now_jst())`` so runtime records
    are aware. External writes and tests that persist
    ``datetime.now().isoformat()`` still need to compare correctly
    against the JST-aware clock instead of being silently expired.
    """

    def test_future_naive_datetime_is_treated_as_jst_and_not_expired(self) -> None:
        # 24h in the future, naive — the aware clock is JST-now, so JST
        # completion must keep this in the future.
        future_naive = (datetime.now(JST) + timedelta(hours=24)).replace(tzinfo=None)
        assert invitations.is_expired(future_naive.isoformat()) is False

    def test_past_naive_datetime_is_treated_as_jst_and_expired(self) -> None:
        past_naive = (datetime.now(JST) - timedelta(hours=1)).replace(tzinfo=None)
        assert invitations.is_expired(past_naive.isoformat()) is True


class TestIsExpiredMalformed:
    def test_non_iso_string_is_expired(self) -> None:
        assert invitations.is_expired("not-a-date") is True

    def test_empty_string_is_expired(self) -> None:
        assert invitations.is_expired("") is True
