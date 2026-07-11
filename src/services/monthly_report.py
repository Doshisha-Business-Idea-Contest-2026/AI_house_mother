"""Monthly summary generation for parents (FR-P3 + extension).

Pull path (this file's initial version): assemble the current-month
summary of a linked student's shared posts and hand it to the Flex
builder. Push path (added in T3.4-b) reuses the same helpers and the
same Flex to send a previous-month digest via ``push_monthly_reports.py``.

Extension (2026-07-09): the report dict now carries the previous month's
count, the lifetime total, current-month usage counters, and a Gemini
authored "AI 寮母より" closing line. See ``docs/04_functional_spec.md``
§5.3, ``docs/05_data_model.md`` §7 and §4.14, and ``docs/06_ai_spec.md``
§4.4. The privacy invariant (``share_with_parent == True`` only) is
still enforced by ``posts.list_month_shared``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.services import gemini, parent_links, posts, usage_stats
from src.services.line_reply import push_flex
from src.services.storage import load_json, save_json
from src.templates.flex.monthly_report import build_monthly_report_bubble
from src.templates.quick_reply import main_menu_quick_reply

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

MAX_POSTS_IN_REPORT = 5

# docs/04 §5.3: below this combined life+activity consultation count we
# switch the "今月の利用" line to a qualitative sentence instead of
# printing raw numbers. Kept as a service-level constant so the Flex
# builder stays a dumb renderer.
LOW_CONSULT_THRESHOLD = 3

# Placeholder shown while profile.display_name is not part of MVP scope.
DEFAULT_STUDENT_DISPLAY = "あなたのお子さん"


def _first_of_this_month(now_jst: datetime) -> datetime:
    """Return the 00:00 JST datetime of the 1st of ``now_jst``'s month."""
    return now_jst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _first_of_prev_month(now_jst: datetime) -> datetime:
    """Return the 00:00 JST datetime of the 1st of the previous month."""
    first_this = _first_of_this_month(now_jst)
    last_prev = first_this - timedelta(seconds=1)
    return last_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _year_month(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _trim(posts_in: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the newest ``MAX_POSTS_IN_REPORT`` posts (created_at desc)."""
    ordered = sorted(posts_in, key=lambda r: r.get("created_at", ""), reverse=True)
    return ordered[:MAX_POSTS_IN_REPORT]


def _prev_year_month(year: int, month: int) -> tuple[int, int]:
    """Return the ``(year, month)`` of the month before ``(year, month)``."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _assemble_report(
    student_user_id: str,
    ref_year: int,
    ref_month: int,
    year_month: str,
    *,
    interactive: bool = False,
) -> dict[str, Any]:
    """Build the full report dict for ``year_month`` (Pull and Push share this).

    Reads current-month posts, previous-month count, lifetime total, the
    current-month usage bucket, and asks Gemini for the closing summary.
    Every downstream renderer receives the same shape.

    ``interactive=True`` is forwarded to :func:`gemini.summarize_month` so
    the LINE Webhook Pull path uses the short timeout that fits inside
    the 30 s reply ceiling. The systemd-timer Push path keeps the
    longer batch timeout.
    """
    month_posts = posts.list_month_shared(student_user_id, ref_year, ref_month)
    prev_year, prev_month = _prev_year_month(ref_year, ref_month)
    prev_count = len(posts.list_month_shared(student_user_id, prev_year, prev_month))
    total_count = posts.count_all_shared(student_user_id)
    usage = usage_stats.get_month(student_user_id, year_month)

    profile = _load_profile(student_user_id)
    ai_summary = gemini.summarize_month(
        profile=profile,
        year_month=year_month,
        posts_month=month_posts,
        usage=usage,
        interactive=interactive,
    )

    trimmed = _trim(month_posts)
    return {
        "student_user_id": student_user_id,
        "year_month": year_month,
        "posts": trimmed,
        "student_display": DEFAULT_STUDENT_DISPLAY,
        "current_count": len(month_posts),
        "prev_count": prev_count,
        "total_count": total_count,
        "usage": usage,
        "ai_summary": ai_summary,
    }


def _load_profile(student_user_id: str) -> dict[str, Any] | None:
    # Imported lazily to keep the module import cycle small — profiles
    # only matter for the AI summary tone hint, not the core report.
    from src.services import profiles

    return profiles.get_profile(student_user_id)


def is_report_empty(report: dict[str, Any]) -> bool:
    """Return ``True`` when the report has nothing worth showing to a parent.

    Used by both the Pull path (to fall back to a plain-text nudge) and
    the Push path (to skip sending entirely, docs/04 §5.3 B5). A report
    counts as "empty" only when both the current-month shared posts *and*
    the current-month usage counters are zero — a month with 0 posts but
    non-zero consultation counts is not empty (the second-layer + AI
    summary still convey something to the parent).
    """
    if report.get("posts"):
        return False
    usage = report.get("usage") or {}
    return sum(int(v or 0) for v in usage.values()) == 0


def build_current_month_report(
    student_user_id: str, now_jst: datetime | None = None
) -> dict[str, Any]:
    """Return the current JST-month summary for ``student_user_id``.

    This is the LINE Webhook Pull path (parent's "📊 今月のレポート"
    button) so the Gemini call runs on the short interactive timeout.

    Args:
        student_user_id: LINE user id of the target student.
        now_jst: Optional reference datetime (JST). Defaults to the
            current wall clock.

    Returns:
        Report dict shaped for :func:`build_monthly_report_bubble` (see
        docs/05 §7 for the field table).
    """
    ref = (now_jst or datetime.now(JST)).astimezone(JST)
    return _assemble_report(
        student_user_id=student_user_id,
        ref_year=ref.year,
        ref_month=ref.month,
        year_month=_year_month(ref),
        interactive=True,
    )


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

    return _assemble_report(
        student_user_id=student_user_id,
        ref_year=year,
        ref_month=month,
        year_month=ym,
    )


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
    deliveries: dict[str, dict[str, str]],
    *,
    batch_id: str | None = None,
) -> str:
    """Persist the current batch state and return the batch id.

    ``deliveries`` (Issue #62) is a ``{parent_user_id: {year_month,
    sent_at}}`` map that grows one entry per successful push. Passing a
    pre-computed ``batch_id`` lets the per-push checkpoint and the final
    write share the same id.
    """
    if batch_id is None:
        batch_id = f"MRB-{executed_at.isoformat()}"
    state = {
        "last_batch": {
            "batch_id": batch_id,
            "target_year_month": target_year_month,
            "executed_at": executed_at.isoformat(),
            "counters": counters,
            "deliveries": deliveries,
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
        f" 頑張ったこと {report.get('current_count', len(report['posts']))} 件"
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
        force: When ``True`` allow the batch to run even if the state
            file already records the same ``target_year_month``. In this
            retry mode, parents whose delivery is recorded in
            ``last_batch.deliveries`` for the target month are
            per-parent skipped so only the previously-failed recipients
            get a push (Issue #62). To fully re-send to every parent,
            delete ``last_batch.deliveries`` from the state file
            manually.

    Returns:
        A summary dict::

            {
                "target_year_month": "2026-07",
                "batch_id": "MRB-...",
                "counters": {"sent": n, "empty": n, "errors": n},
                "skipped_batch": bool,
            }

        Empty ``(parent, student)`` pairs (0 shared posts *and* 0 usage
        counts) are silently skipped (``empty`` counter) and never
        generate a message. Per-parent LINE API errors are caught and
        counted in ``errors``; the batch proceeds to the next recipient.
        On every successful push the state file is rewritten so a crash
        mid-batch never re-sends to already-delivered parents (Issue
        #62).
    """
    executed_at = (now_jst or datetime.now(JST)).astimezone(JST)
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

    # Preserve per-parent delivery history only when force-retrying the
    # same target month (Issue #62). Different-month re-runs start with
    # an empty deliveries map so the previous month's records are
    # replaced along with the rest of last_batch.
    if (
        force
        and last_batch is not None
        and last_batch.get("target_year_month") == ym
        and isinstance(last_batch.get("deliveries"), dict)
    ):
        deliveries: dict[str, dict[str, str]] = {
            k: dict(v)
            for k, v in last_batch["deliveries"].items()
            if isinstance(v, dict)
        }
    else:
        deliveries = {}

    counters = {"sent": 0, "empty": 0, "errors": 0}
    batch_id = f"MRB-{executed_at.isoformat()}"

    for parent_user_id, student_user_id in parent_links.list_all_active_pairs():
        prev_delivery = deliveries.get(parent_user_id)
        if isinstance(prev_delivery, dict) and prev_delivery.get("year_month") == ym:
            logger.info(
                "monthly_push skipped parent=%s year_month=%s (already delivered)",
                parent_user_id[:8],
                ym,
            )
            continue
        try:
            report = _assemble_report(
                student_user_id=student_user_id,
                ref_year=year,
                ref_month=month,
                year_month=ym,
            )
            if is_report_empty(report):
                counters["empty"] += 1
                logger.info(
                    "monthly_push empty parent=%s student=%s year_month=%s",
                    parent_user_id[:8],
                    student_user_id[:8],
                    ym,
                )
                continue
            bubble = build_monthly_report_bubble(report)
            push_flex(
                parent_user_id,
                alt_text=_alt_text(report),
                contents=bubble,
                quick_reply=main_menu_quick_reply("parent"),
                raise_on_error=True,
            )
            counters["sent"] += 1
            deliveries[parent_user_id] = {
                "year_month": ym,
                "sent_at": datetime.now(JST).isoformat(),
            }
            # Per-push checkpoint (Issue #62): rewrite the whole state so
            # a crash between recipients does not lose the record. The
            # JSON is small (parent count ≪ 100) so the extra write cost
            # is acceptable.
            _record_batch(
                ym, executed_at, counters, deliveries, batch_id=batch_id
            )
            logger.info(
                "monthly_push sent parent=%s student=%s year_month=%s post_count=%d",
                parent_user_id[:8],
                student_user_id[:8],
                ym,
                report.get("current_count", 0),
            )
        except Exception:
            counters["errors"] += 1
            logger.exception(
                "monthly_push error parent=%s student=%s year_month=%s",
                parent_user_id[:8],
                student_user_id[:8],
                ym,
            )

    # Final checkpoint covers the "0 successful pushes" case (nothing to
    # do, empty-only, all-errors, or all-already-delivered) so the state
    # file always reflects the current run.
    _record_batch(ym, executed_at, counters, deliveries, batch_id=batch_id)
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
