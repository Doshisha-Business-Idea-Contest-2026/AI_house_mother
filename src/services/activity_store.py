"""Short-term persistence for activity proposals.

Whenever the bot sends an activity carousel we index the proposals by a
short hash of the title so the follow-up postbacks (``activity:detail:*``,
``activity:participated:*``) can resolve back to the original dict even
after the in-memory session times out.

Entries older than :data:`TTL_SECONDS` are pruned lazily on read/write.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from src.services.storage import load_json, locked_edit

logger = logging.getLogger(__name__)

_FILE = "session_activities.json"
TTL_SECONDS = 30 * 60  # 30 minutes


def make_key(title: str) -> str:
    """Return an 8-character stable hash for ``title``."""
    return hashlib.sha1(title.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]


def _load() -> dict[str, Any]:
    data = load_json(_FILE, default={"activities": {}})
    if "activities" not in data:
        data["activities"] = {}
    return data


def _prune(data: dict[str, Any]) -> None:
    now = time.time()
    stale = [
        k
        for k, v in data["activities"].items()
        if now - v.get("_written_at", 0) > TTL_SECONDS
    ]
    for k in stale:
        data["activities"].pop(k, None)


def remember(user_id: str, activities: list[dict[str, Any]]) -> list[str]:
    """Persist activities under short keys and return the list of keys."""
    # Prune + insert under a single lock so two concurrent proposal
    # carousels cannot lose one side's entries (docs/05 §3.1, Issue #45).
    keys: list[str] = []
    now = time.time()
    with locked_edit(_FILE, default={"activities": {}}) as data:
        if "activities" not in data:
            data["activities"] = {}
        _prune(data)
        for activity in activities:
            title = str(activity.get("title") or "activity")
            key = make_key(title)
            data["activities"][key] = {
                "user_id": user_id,
                "activity": activity,
                "_written_at": now,
            }
            keys.append(key)
    return keys


def resolve(key: str) -> dict[str, Any] | None:
    """Return the activity dict for ``key`` if still fresh."""
    data = _load()
    _prune(data)
    entry = data["activities"].get(key)
    if entry is None:
        return None
    return entry.get("activity")
