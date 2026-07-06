"""Monthly summary generation for parents (FR-P3).

Pull path (this file's initial version): assemble the current-month
summary of a linked student's shared posts and hand it to the Flex
builder. Push path (added in T3.4-b) reuses the same helpers and the
same Flex to send a previous-month digest via ``push_monthly_reports.py``.

Spec: ``docs/04_functional_spec.md`` §5.3 and ``docs/05_data_model.md``
§7. The privacy invariant (``share_with_parent == True`` only) is
enforced by ``posts.list_month_shared`` which this module wraps.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.services import posts

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

MAX_POSTS_IN_REPORT = 5

CATEGORY_EMOJI: dict[str, str] = {
    "event": "🏛️",
    "volunteer": "🧹",
    "store": "🍜",
    "medical": "🏥",
    "tips": "📋",
    "other": "✨",
}

# Placeholder shown while profile.display_name is not part of MVP scope.
DEFAULT_STUDENT_DISPLAY = "あなたのお子さん"


def _first_of_this_month(now_jst: datetime) -> datetime:
    """Return the 00:00 JST datetime of the 1st of ``now_jst``'s month."""
    return now_jst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _first_of_prev_month(now_jst: datetime) -> datetime:
    """Return the 00:00 JST datetime of the 1st of the previous month."""
    first_this = _first_of_this_month(now_jst)
    last_prev = first_this - timedelta(seconds=1)
    return last_prev.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )


def _year_month(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _trim(posts_in: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the newest ``MAX_POSTS_IN_REPORT`` posts (created_at desc)."""
    ordered = sorted(
        posts_in, key=lambda r: r.get("created_at", ""), reverse=True
    )
    return ordered[:MAX_POSTS_IN_REPORT]


def build_current_month_report(
    student_user_id: str, now_jst: datetime | None = None
) -> dict[str, Any]:
    """Return the current JST-month summary for ``student_user_id``.

    Args:
        student_user_id: LINE user id of the target student.
        now_jst: Optional reference datetime (JST). Defaults to the
            current wall clock.

    Returns:
        Dict with ``year_month`` (``"YYYY-MM"``), ``posts`` (up to
        :data:`MAX_POSTS_IN_REPORT` entries, newest first) and
        ``student_display`` used by the Flex builder.
    """
    ref = (now_jst or datetime.now(JST)).astimezone(JST)
    month_posts = posts.list_month_shared(student_user_id, ref.year, ref.month)
    return {
        "student_user_id": student_user_id,
        "year_month": _year_month(ref),
        "posts": _trim(month_posts),
        "student_display": DEFAULT_STUDENT_DISPLAY,
    }
