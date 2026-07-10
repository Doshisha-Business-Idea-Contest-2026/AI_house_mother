"""User role management (student vs. parent).

Persists role assignments in ``data/users.json`` using the storage
service. The user's LINE ``user_id`` is used as the primary key.
"""

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from src.services.storage import load_json, locked_edit

JST = ZoneInfo("Asia/Tokyo")

Role = Literal["student", "parent"]

_FILE = "users.json"
_EMPTY: dict = {"users": {}}


def get_user(line_user_id: str) -> dict | None:
    """Return the stored record for ``line_user_id`` or ``None``."""
    data = load_json(_FILE, default=_EMPTY)
    return data["users"].get(line_user_id)


def save_user(line_user_id: str, role: Role) -> None:
    """Insert or update a user's role.

    ``created_at`` is preserved on updates; ``updated_at`` is always
    refreshed.

    Args:
        line_user_id: LINE user identifier.
        role: Either ``"student"`` or ``"parent"``.

    Raises:
        ValueError: If ``role`` is not one of the allowed values.
    """
    if role not in ("student", "parent"):
        raise ValueError(f"invalid role: {role!r}")

    now = datetime.now(JST).isoformat()
    # Atomically preserve created_at while refreshing updated_at, so a
    # second concurrent registration cannot flip the timestamps
    # (docs/05 §3.1, Issue #45).
    with locked_edit(_FILE, default=_EMPTY) as data:
        data.setdefault("users", {})
        existing = data["users"].get(line_user_id, {})
        data["users"][line_user_id] = {
            "line_user_id": line_user_id,
            "role": role,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }


def get_role(line_user_id: str) -> Role | None:
    """Return the role of ``line_user_id`` or ``None`` when unregistered."""
    user = get_user(line_user_id)
    return user["role"] if user else None
