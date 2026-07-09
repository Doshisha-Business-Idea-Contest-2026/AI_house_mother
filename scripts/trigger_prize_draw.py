"""Manually run a prize draw for a student (demo / testing helper).

Runs one ranked prize draw for a given LINE user id and pushes the
win/miss animation, so a demo can show a chosen rank without relying on
chance (FR-S11, docs/08 シーン6). ``--rank 1|2|3`` forces that rank and
``--lose`` forces a miss, so the demo can guarantee a 1st-place win. The
trigger runs on the server; nothing about it appears in the LINE chat.
This is a demo-only feature: prizes are fictional and no winner PII is
collected.

Usage:
    python scripts/trigger_prize_draw.py --list
    python scripts/trigger_prize_draw.py <user_id> --dry-run
    python scripts/trigger_prize_draw.py <user_id> --rank 1
    python scripts/trigger_prize_draw.py <user_id> --lose
    python scripts/trigger_prize_draw.py <user_id>          # random outcome
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import prizes  # noqa: E402
from src.services.line_reply import push_flex  # noqa: E402
from src.services.storage import load_json  # noqa: E402
from src.templates.flex.prize_result import build_prize_result_bubble  # noqa: E402


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
        help="Show active prizes without drawing or sending",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--rank",
        type=int,
        choices=[1, 2, 3],
        help="Force a winning rank (1/2/3)",
    )
    group.add_argument("--lose", action="store_true", help="Force a losing result")
    args = parser.parse_args()

    if args.list:
        _list_students()
        return 0

    if not args.user_id:
        parser.error("user_id is required unless --list is given")

    if args.dry_run:
        active = prizes._active_prizes()
        print(f"[dry-run] user={args.user_id[:8]}… active prizes:")
        for p in active:
            print(
                f"  {p.get('rank')}等  {p.get('prize_id')}  "
                f"{p.get('emoji', '')} {p.get('name')}"
            )
        print("[dry-run] no draw run, no message sent.")
        return 0

    force_rank: int | None = None
    if args.rank is not None:
        force_rank = args.rank
    elif args.lose:
        force_rank = 0

    result = prizes.draw(args.user_id, force_rank=force_rank)
    if result is None:
        print("No active prizes in seed; nothing drawn.")
        return 1
    push_flex(
        args.user_id,
        alt_text="🎁 くじ引きの結果",
        contents=build_prize_result_bubble(result),
        raise_on_error=True,
    )
    print(
        f"Draw sent to {args.user_id[:8]}…: "
        f"result={result['result']} rank={result['rank']} "
        f"prize={result['prize'].get('prize_id') if result['prize'] else None}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
