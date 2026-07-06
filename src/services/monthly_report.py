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

from src.services import parent_links, posts
from src.services.line_reply import push_flex
from src.services.storage import load_json, save_json
from src.templates.flex.monthly_report import build_monthly_report_bubble

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

MAX_POSTS_IN_REPORT = 5

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


def build_previous_month_report(
    student_user_id: str,
    now_jst: datetime | None = None,
    target_year_month: str | None = None,
) -> dict[str, Any]:
    """Return the previous JST-month summary (Push path).

    Args:
        student_user_id: LINE user id of the target student.
        now_jst: Reference JST datetime. Defaults to the current wall
            clock.
        target_year_month: Explicit ``"YYYY-MM"`` override (e.g. for
            manual re-runs). When ``None`` the month right before
            ``now_jst`` is used.
    """
    if target_year_month is None:
        ref = (now_jst or datetime.now(JST)).astimezone(JST)
        prev_first = _first_of_prev_month(ref)
        year, month = prev_first.year, prev_first.month
        ym = _year_month(prev_first)
    else:
        year, month, ym = _parse_year_month(target_year_month)

    month_posts = posts.list_month_shared(student_user_id, year, month)
    return {
        "student_user_id": student_user_id,
        "year_month": ym,
        "posts": _trim(month_posts),
        "student_display": DEFAULT_STUDENT_DISPLAY,
    }


# ---------------------------------------------------------------------------
# Push scheduler (T3.4-b)
# ---------------------------------------------------------------------------


STATE_FILE = "monthly_report_state.json"
_STATE_EMPTY: dict[str, Any] = {"last_batch": None}


def _parse_year_month(value: str) -> tuple[int, int, str]:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid target_year_month: {value!r}")
    year = int(parts[0])
    month = int(parts[1])
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month in {value!r}")
    return year, month, f"{year:04d}-{month:02d}"


def _load_state() -> dict[str, Any]:
    return load_json(STATE_FILE, default=_STATE_EMPTY)


def _record_batch(
    target_year_month: str,
    executed_at: datetime,
    counters: dict[str, int],
) -> str:
    batch_id = f"MRB-{executed_at.isoformat()}"
    state = {
        "last_batch": {
            "batch_id": batch_id,
            "target_year_month": target_year_month,
            "executed_at": executed_at.isoformat(),
            "counters": counters,
        }
    }
    save_json(STATE_FILE, state)
    return batch_id


def _resolve_target_year_month(
    now_jst: datetime | None, target_year_month: str | None
) -> str:
    if target_year_month is not None:
        _year, _month, ym = _parse_year_month(target_year_month)
        return ym
    ref = (now_jst or datetime.now(JST)).astimezone(JST)
    return _year_month(_first_of_prev_month(ref))


def _alt_text(report: dict[str, Any]) -> str:
    return (
        f"📊 {report['student_display']}の{report['year_month']}"
        f" 頑張ったこと {len(report['posts'])} 件"
    )


def push_previous_month_to_all(
    now_jst: datetime | None = None,
    target_year_month: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Push the previous-month summary to every linked parent.

    Args:
        now_jst: Reference JST datetime used when ``target_year_month``
            is not supplied.
        target_year_month: Explicit ``"YYYY-MM"`` override for manual
            re-runs.
        force: When ``True`` run even if the state file records the same
            ``target_year_month`` as already delivered.

    Returns:
        A summary dict::

            {
                "target_year_month": "2026-07",
                "batch_id": "MRB-...",
                "counters": {"sent": n, "empty": n, "errors": n},
                "skipped_batch": bool,
            }

        Zero-post ``(parent, student)`` pairs are silently skipped
        (``empty`` counter) and never generate a message. Per-parent
        LINE API errors are caught and counted in ``errors``; the batch
        proceeds to the next recipient.
    """
    executed_at = datetime.now(JST)
    ym = _resolve_target_year_month(now_jst, target_year_month)

    state = _load_state()
    last_batch = state.get("last_batch") if state else None
    if (
        not force
        and last_batch is not None
        and last_batch.get("target_year_month") == ym
    ):
        logger.info(
            "monthly_push skipped year_month=%s (already recorded, use --force to override)",
            ym,
        )
        return {
            "target_year_month": ym,
            "batch_id": last_batch.get("batch_id", ""),
            "counters": last_batch.get("counters", {}),
            "skipped_batch": True,
        }

    year, month, _ym_string = _parse_year_month(ym)

    counters = {"sent": 0, "empty": 0, "errors": 0}
    for parent_user_id, student_user_id in parent_links.list_all_active_pairs():
        try:
            month_posts = posts.list_month_shared(student_user_id, year, month)
            trimmed = _trim(month_posts)
            report = {
                "student_user_id": student_user_id,
                "year_month": ym,
                "posts": trimmed,
                "student_display": DEFAULT_STUDENT_DISPLAY,
            }
            if not trimmed:
                counters["empty"] += 1
                logger.info(
                    "monthly_push empty parent=%s student=%s year_month=%s",
                    parent_user_id[:8],
                    student_user_id[:8],
                    ym,
                )
                continue
            bubble = build_monthly_report_bubble(
                student_display=report["student_display"],
                year_month=report["year_month"],
                posts=report["posts"],
            )
            push_flex(
                parent_user_id,
                alt_text=_alt_text(report),
                contents=bubble,
                raise_on_error=True,
                sender="notify",
            )
            counters["sent"] += 1
            logger.info(
                "monthly_push sent parent=%s student=%s year_month=%s post_count=%d",
                parent_user_id[:8],
                student_user_id[:8],
                ym,
                len(trimmed),
            )
        except Exception:
            counters["errors"] += 1
            logger.exception(
                "monthly_push error parent=%s student=%s year_month=%s",
                parent_user_id[:8],
                student_user_id[:8],
                ym,
            )

    batch_id = _record_batch(ym, executed_at, counters)
    logger.info(
        "monthly_push batch_completed batch_id=%s year_month=%s counters=%s",
        batch_id,
        ym,
        counters,
    )
    return {
        "target_year_month": ym,
        "batch_id": batch_id,
        "counters": counters,
        "skipped_batch": False,
    }
