"""Manually trigger a coupon batch for a student (demo / testing helper).

Awards the next coupon batch to a given LINE user id without requiring the
student to actually post three times (FR-S10, docs/08 シーン6 手動発火). The
trigger runs on the server, so nothing about it appears in the LINE chat —
only the coupon carousel is delivered.

Usage:
    python scripts/trigger_coupon.py --list
    python scripts/trigger_coupon.py <user_id> --dry-run
    python scripts/trigger_coupon.py <user_id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import coupons  # noqa: E402
from src.services.line_reply import push_flex  # noqa: E402
from src.services.storage import load_json  # noqa: E402
from src.templates.flex.coupon_carousel import build_coupon_carousel  # noqa: E402


def _list_students() -> None:
    """Print registered student user ids so one can be passed as target."""
    data = load_json("users.json", default={"users": {}})
    users = data.get("users", {})
    students = [uid for uid, row in users.items() if row.get("role") == "student"]
    if not students:
        print("No student users registered.")
        return
    print(f"Registered students ({len(students)}):")
    for uid in students:
        print(f"  {uid}")


def _next_milestone(user_id: str) -> int:
    """Return the milestone that :func:`force_award_next` would award."""
    data = load_json(coupons._FILE, default={})
    last = int(data.get(user_id, {}).get("last_awarded_milestone", 0))
    return last + coupons.COUPONS_PER_BATCH


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", nargs="?", help="Target student LINE user id")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered student user ids and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the coupons that would be sent without sending them",
    )
    args = parser.parse_args()

    if args.list:
        _list_students()
        return 0

    if not args.user_id:
        parser.error("user_id is required unless --list is given")

    if args.dry_run:
        milestone = _next_milestone(args.user_id)
        selected = coupons.select_coupons_for_milestone(milestone)
        if not selected:
            print("No active coupons in seed; nothing would be sent.")
            return 1
        print(f"[dry-run] user={args.user_id[:8]}… next milestone={milestone}")
        for c in selected:
            print(f"  {c.get('coupon_id')}  {c.get('store_name')}  {c.get('title')}")
        print("[dry-run] no message sent.")
        return 0

    awarded = coupons.force_award_next(args.user_id)
    if not awarded:
        print("No active coupons in seed; nothing sent.")
        return 1
    push_flex(
        args.user_id,
        alt_text="🎫 クーポンが届きました",
        contents=build_coupon_carousel(awarded),
        raise_on_error=True,
    )
    ids = [c.get("coupon_id") for c in awarded]
    print(f"Sent {len(awarded)} coupons to {args.user_id[:8]}…: {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
