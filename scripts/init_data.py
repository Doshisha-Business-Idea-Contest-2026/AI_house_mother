"""Initialize empty runtime JSON files under data/.

Creates the following files with empty schemas if they do not exist:
  - data/users.json                  {"users": {}}
  - data/profiles.json               {"profiles": {}}
  - data/posts.json                  {"posts": []}
  - data/invitations.json            {"invitations": []}
  - data/parent_links.json           {"links": []}
  - data/session_activities.json     {"activities": {}}
  - data/monthly_report_state.json   {"last_batch": null}
  - data/sponsored_engagement.json   {"events": []}
  - data/usage_stats.json            {}
  - data/coupon_distributions.json   {}
  - data/prize_draws.json            {}

Also ensures data/seed/ exists (seed JSON files are added by later tasks).

Existing files are never overwritten.
"""

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

INITIAL_FILES: dict[str, Any] = {
    "users.json": {"users": {}},
    "profiles.json": {"profiles": {}},
    "posts.json": {"posts": []},
    "invitations.json": {"invitations": []},
    "parent_links.json": {"links": []},
    "session_activities.json": {"activities": {}},
    "monthly_report_state.json": {"last_batch": None},
    "sponsored_engagement.json": {"events": []},
    "usage_stats.json": {},
    "coupon_distributions.json": {},
    "prize_draws.json": {},
}


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "seed").mkdir(parents=True, exist_ok=True)

    for filename, initial in INITIAL_FILES.items():
        path = DATA_DIR / filename
        if path.exists():
            print(f"skip:  {path} (already exists)")
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=4, ensure_ascii=False)
        print(f"wrote: {path}")


if __name__ == "__main__":
    main()
