"""Student profile persistence.

Profiles are keyed by LINE ``user_id`` and stored in ``data/profiles.json``.
See ``docs/05_data_model.md`` §4.2 for the schema.
"""
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.services.storage import load_json, save_json

JST = ZoneInfo("Asia/Tokyo")

_FILE = "profiles.json"
_EMPTY: dict = {"profiles": {}}


def get_profile(line_user_id: str) -> dict | None:
    """Return the stored profile record for ``line_user_id`` or ``None``."""
    data = load_json(_FILE, default=_EMPTY)
    return data["profiles"].get(line_user_id)


def has_profile(line_user_id: str) -> bool:
    """Return ``True`` when a profile exists for ``line_user_id``."""
    return get_profile(line_user_id) is not None


def save_profile(line_user_id: str, profile: dict[str, Any]) -> None:
    """Insert or update the profile for ``line_user_id``.

    ``created_at`` is preserved across updates while ``updated_at`` is
    always refreshed. Extra keys in ``profile`` are stored verbatim.

    Args:
        line_user_id: LINE user identifier used as the primary key.
        profile: Profile fields such as ``university``, ``faculty``,
            ``grade``, ``interests``, ``recent_effort``, ``want_to_do``.
    """
    data = load_json(_FILE, default=_EMPTY)
    now = datetime.now(JST).isoformat()
    existing = data["profiles"].get(line_user_id, {})
    merged = {
        "line_user_id": line_user_id,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    merged.update(profile)
    data["profiles"][line_user_id] = merged
    save_json(_FILE, data)


def delete_profile(line_user_id: str) -> bool:
    """Remove the profile record. Returns ``True`` if a record was deleted."""
    data = load_json(_FILE, default=_EMPTY)
    if line_user_id not in data["profiles"]:
        return False
    del data["profiles"][line_user_id]
    save_json(_FILE, data)
    return True
