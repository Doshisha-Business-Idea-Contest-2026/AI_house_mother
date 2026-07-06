"""Reset every runtime JSON under ``data/`` back to its empty schema.

Intended to be run right before the presentation so the reviewers see
the onboarding flow from scratch, without leftover accounts, posts or
monthly-push state pollution.

Behavior:
    * Every file listed in :data:`scripts.init_data.INITIAL_FILES` is
      overwritten with its empty skeleton (``users``, ``profiles``,
      ``posts``, ``invitations``, ``parent_links``,
      ``session_activities``, ``monthly_report_state``).
    * ``data/seed/*.json`` is never touched — the seed dataset is the
      demo's factual backbone.
    * Requires interactive confirmation unless ``--yes`` is passed.
    * ``--dry-run`` prints the target list without writing anything.

Usage::

    python scripts/reset_demo.py --dry-run
    python scripts/reset_demo.py            # asks for y/N
    python scripts/reset_demo.py --yes      # non-interactive
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.init_data import DATA_DIR, INITIAL_FILES  # noqa: E402

logger = logging.getLogger("reset_demo")


def _print_targets(targets: list[tuple[Path, object]]) -> None:
    print("Runtime files to reset (seed/ is never touched):")
    for path, _initial in targets:
        state = "exists" if path.exists() else "missing"
        print(f"  - {path.relative_to(REPO_ROOT)}  [{state}]")


def _confirm() -> bool:
    try:
        answer = input(
            "\n上記のファイルを空スキーマで上書きします。よろしいですか？ [y/N] "
        )
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reset every runtime JSON under data/ so the LINE Bot starts "
            "the demo from a clean slate. data/seed/ is left untouched."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the target files without writing anything.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    targets: list[tuple[Path, object]] = [
        (DATA_DIR / name, initial)
        for name, initial in INITIAL_FILES.items()
    ]

    _print_targets(targets)

    if args.dry_run:
        print("\n[dry-run] no changes made.")
        return 0

    if not args.yes and not _confirm():
        print("aborted.")
        return 1

    for path, initial in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=4, ensure_ascii=False)
        logger.info("reset %s", path.relative_to(REPO_ROOT))

    print(f"\ndone. {len(targets)} file(s) reset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
