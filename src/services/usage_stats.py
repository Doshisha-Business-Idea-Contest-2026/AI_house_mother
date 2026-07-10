"""Monthly usage counters for the parent report (FR-P3 extension).

Every time a student interacts with a core feature — life consultation,
want-to-do consultation, experience posting, or profile update — the
handler layer bumps the matching counter in ``usage_stats.json`` via
:func:`record`. The parent monthly report reads the current-month bucket
via :func:`get_month` and folds it into the Flex message so an otherwise
empty month can still convey engagement (docs/04 §5.3, docs/05 §4.14).

Sharing usage counts to parents is covered by the invitation-code linking
consent (single-toggle). Raw ``line_user_id`` is used as the top-level
key (same convention as ``posts.json`` / ``profiles.json``) but is never
written to logs — only ``user_id[:8]`` is emitted.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.services.storage import load_json, locked_edit

logger = logging.getLogger(__name__)

_FILE = "usage_stats.json"
JST = ZoneInfo("Asia/Tokyo")

EVENT_TYPES: tuple[str, ...] = ("life", "activity", "post", "profile")


def _year_month(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _empty_month() -> dict[str, int]:
    return {event_type: 0 for event_type in EVENT_TYPES}


def record(user_id: str, event_type: str, now_jst: datetime | None = None) -> None:
    """Increment the ``event_type`` counter for ``user_id`` in the current month.

    Args:
        user_id: LINE user id of the student. Stored as-is in the JSON
            key (matches ``posts.json`` / ``profiles.json``), and never
            logged in full — only ``user_id[:8]`` is emitted.
        event_type: One of :data:`EVENT_TYPES`
            (``"life"`` / ``"activity"`` / ``"post"`` / ``"profile"``).
        now_jst: Reference JST datetime. Defaults to the current wall
            clock.

    Raises:
        ValueError: If ``event_type`` is not a recognised counter.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Invalid event_type: {event_type!r}")

    ref = (now_jst or datetime.now(JST)).astimezone(JST)
    year_month = _year_month(ref)

    # Increment under an exclusive lock — a plain read → modify → write
    # loses the counter's other update on parallel activity + life
    # bursts (docs/05 §3.1, Issue #45).
    with locked_edit(_FILE, default={}) as data:
        user_bucket = data.setdefault(user_id, {})
        month_bucket = user_bucket.setdefault(year_month, _empty_month())
        for event in EVENT_TYPES:
            month_bucket.setdefault(event, 0)
        month_bucket[event_type] = int(month_bucket[event_type]) + 1
        new_count = month_bucket[event_type]

    logger.info(
        "usage_stats recorded user=%s event=%s year_month=%s count=%d",
        user_id[:8],
        event_type,
        year_month,
        new_count,
    )


def get_month(user_id: str, year_month: str) -> dict[str, int]:
    """Return the counter dict for ``user_id`` in ``year_month``.

    Missing users, months, or individual counters return ``0`` — the
    caller can rely on all :data:`EVENT_TYPES` keys being present.

    Args:
        user_id: LINE user id of the student.
        year_month: Month string in ``"YYYY-MM"`` format.

    Returns:
        Dict keyed by :data:`EVENT_TYPES` with int counts (``0`` when
        no activity was recorded).
    """
    data: dict[str, Any] = load_json(_FILE, default={})
    month_bucket = data.get(user_id, {}).get(year_month, {})
    return {event: int(month_bucket.get(event, 0)) for event in EVENT_TYPES}
