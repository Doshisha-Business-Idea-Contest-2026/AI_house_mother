"""Invitation code persistence for the student -> parent link flow.

Students trigger ``issue_code`` from the "family link" menu and share the
resulting 6-character code with their parent. Parents consume it through
``consume`` in the parent link handler. See ``docs/04_functional_spec.md``
§4.6 and ``docs/05_data_model.md`` §4.4 for the specification.

Invariants:
  * Only one active (``used_at IS NULL`` and not expired) code per student
    at any time. ``issue_code`` revokes any prior pending code by writing
    ``used_at=now`` and ``used_by_parent_id=REVOKED_SENTINEL`` before
    generating the new one.
  * Codes come from ``CODE_ALPHABET`` (32 characters, ``I``/``O``/``0``/``1``
    excluded for readability) and are single-use.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.services.storage import load_json, save_json

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_FILE = "invitations.json"
_EMPTY: dict[str, list] = {"invitations": []}

CODE_LENGTH = 6
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TTL_HOURS = 24
_MAX_GENERATE_RETRIES = 5

REVOKED_SENTINEL = "__revoked__"


def _now_jst() -> datetime:
    return datetime.now(JST)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _load() -> dict[str, Any]:
    data = load_json(_FILE, default=_EMPTY)
    if "invitations" not in data:
        data["invitations"] = []
    return data


def is_expired(expires_at_iso: str) -> bool:
    """Return ``True`` when ``expires_at_iso`` is in the past.

    Malformed strings (``ValueError`` from :func:`datetime.fromisoformat`)
    and naive datetimes that cannot be compared to the JST-aware clock
    (``TypeError``) are both treated as expired so callers never see the
    exception propagate.
    """
    try:
        expires_at = datetime.fromisoformat(expires_at_iso)
        return expires_at <= _now_jst()
    except (ValueError, TypeError):
        logger.warning("Invalid or naive expires_at: %s", expires_at_iso)
        return True


def generate_code() -> str:
    """Return a single random 6-character invitation code."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def find_active(code: str) -> dict[str, Any] | None:
    """Return the pending record for ``code`` if it exists and is unexpired."""
    data = _load()
    for inv in data["invitations"]:
        if inv["code"] != code:
            continue
        if inv["used_at"] is not None:
            return None
        if is_expired(inv["expires_at"]):
            return None
        return inv
    return None


def _generate_unique_code(existing: list[dict[str, Any]]) -> str:
    """Generate a code that does not collide with any active record."""
    active_codes = {
        inv["code"]
        for inv in existing
        if inv["used_at"] is None and not is_expired(inv["expires_at"])
    }
    for _ in range(_MAX_GENERATE_RETRIES):
        candidate = generate_code()
        if candidate not in active_codes:
            return candidate
    raise RuntimeError(
        "Failed to generate a unique invitation code after "
        f"{_MAX_GENERATE_RETRIES} retries"
    )


def issue_code(student_user_id: str) -> dict[str, Any]:
    """Issue a fresh invitation code for ``student_user_id``.

    Any prior pending record for the same student is revoked (``used_at``
    and ``used_by_parent_id=REVOKED_SENTINEL``) before the new code is
    generated so that exactly one active code exists per student.

    Args:
        student_user_id: LINE user id of the issuing student.

    Returns:
        The new invitation record dict.
    """
    data = _load()
    now = _now_jst()
    now_iso = _iso(now)

    revoked = 0
    for inv in data["invitations"]:
        if (
            inv["student_user_id"] == student_user_id
            and inv["used_at"] is None
            and not is_expired(inv["expires_at"])
        ):
            inv["used_at"] = now_iso
            inv["used_by_parent_id"] = REVOKED_SENTINEL
            revoked += 1

    code = _generate_unique_code(data["invitations"])
    record: dict[str, Any] = {
        "code": code,
        "student_user_id": student_user_id,
        "created_at": now_iso,
        "expires_at": _iso(now + timedelta(hours=TTL_HOURS)),
        "used_at": None,
        "used_by_parent_id": None,
    }
    data["invitations"].append(record)
    save_json(_FILE, data)
    logger.info("Issued invitation code (revoked=%d, ttl_hours=%d)", revoked, TTL_HOURS)
    return record


def consume(code: str, parent_user_id: str) -> tuple[str | None, str]:
    """Consume an invitation code for ``parent_user_id``.

    Args:
        code: Code entered by the parent.
        parent_user_id: LINE user id of the parent trying to link.

    Returns:
        Tuple ``(student_user_id, error_reason)``. ``error_reason`` is one
        of ``"ok"``, ``"not_found"``, ``"expired"``, ``"used"``,
        ``"self_link"``. ``student_user_id`` is ``None`` on any error.
    """
    data = _load()
    target: dict[str, Any] | None = None
    for inv in data["invitations"]:
        if inv["code"] == code:
            target = inv
            break

    if target is None:
        return None, "not_found"
    if target["used_at"] is not None:
        return None, "used"
    if is_expired(target["expires_at"]):
        return None, "expired"
    if target["student_user_id"] == parent_user_id:
        return None, "self_link"

    target["used_at"] = _iso(_now_jst())
    target["used_by_parent_id"] = parent_user_id
    save_json(_FILE, data)
    return target["student_user_id"], "ok"
