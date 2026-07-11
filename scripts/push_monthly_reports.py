"""Systemd-timer entrypoint for the monthly parent summary push.

Runs :func:`monthly_report.push_previous_month_to_all` once and exits.
The script is idempotent per ``target_year_month`` thanks to the state
file at ``data/monthly_report_state.json`` — re-runs on the same month
skip unless ``--force`` is passed. ``--force`` uses retry-only
semantics: parents whose delivery for the target month is already
recorded in ``last_batch.deliveries`` are per-parent skipped, so only
previously-failed recipients get a push (Issue #62). Delete
``last_batch.deliveries`` from the state file manually to force a full
re-send to every parent.

Usage::

    python scripts/push_monthly_reports.py                # previous month
    python scripts/push_monthly_reports.py --month 2026-07
    python scripts/push_monthly_reports.py --now 2026-08-01T00:01+09:00
    python scripts/push_monthly_reports.py --month 2026-07 --force

Logs land in journald when launched from systemd; stderr when launched
by hand.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Allow ``python scripts/push_monthly_reports.py`` from the repo root
# without setting PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services import monthly_report  # noqa: E402

JST = ZoneInfo("Asia/Tokyo")

logger = logging.getLogger("push_monthly_reports")


def _parse_now(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Push the previous-month summary to every linked parent."
    )
    parser.add_argument(
        "--month",
        dest="target_year_month",
        default=None,
        help=(
            "Explicit YYYY-MM to push (default: the month before --now). "
            "Combine with --force to re-send a month already recorded in "
            "monthly_report_state.json."
        ),
    )
    parser.add_argument(
        "--now",
        dest="now",
        default=None,
        help=(
            "ISO 8601 datetime treated as 'now' for month boundary "
            "calculation. If no timezone is given, JST is assumed."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Retry semantics: re-run even if a batch for the same "
            "target_year_month is already recorded, but only push to "
            "parents whose delivery is NOT already in "
            "last_batch.deliveries (Issue #62). To force a full re-send, "
            "delete last_batch.deliveries from "
            "data/monthly_report_state.json manually."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    now = _parse_now(args.now) if args.now else None

    logger.info(
        "monthly_push starting month=%s force=%s now=%s",
        args.target_year_month,
        args.force,
        now.isoformat() if now else "<default>",
    )
    result = monthly_report.push_previous_month_to_all(
        now_jst=now,
        target_year_month=args.target_year_month,
        force=args.force,
    )
    logger.info(
        "monthly_push done target_year_month=%s batch_id=%s counters=%s skipped=%s",
        result["target_year_month"],
        result["batch_id"],
        result["counters"],
        result["skipped_batch"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
