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

from src.services.storage import load_json, locked_edit

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_FILE = "invitations.json"

CODE_LENGTH = 6
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TTL_HOURS = 24
_MAX_GENERATE_RETRIES = 5

REVOKED_SENTINEL = "__revoked__"


def _now_jst() -> datetime:
    return datetime.now(JST)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _ensure_shape(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("invitations"), list):
        data["invitations"] = []
    return data


def _load() -> dict[str, Any]:
    return _ensure_shape(load_json(_FILE, default=None))


def is_expired(expires_at_iso: str) -> bool:
    """Return ``True`` when ``expires_at_iso`` is in the past.

    Naive datetimes (no ``tzinfo``) are completed as JST and compared
    against the JST-aware clock with a WARNING log, so external writes
    or tests that persist ``datetime.now().isoformat()`` behave the same
    as the ``_iso(_now_jst())`` produced by :func:`issue_code` (Issue
    #57). Malformed strings raise a ``ValueError`` from
    :func:`datetime.fromisoformat` and are treated as expired so callers
    never see the exception propagate.
    """
    try:
        expires_at = datetime.fromisoformat(expires_at_iso)
    except (ValueError, TypeError):
        logger.warning("Invalid expires_at: %s", expires_at_iso)
        return True
    if expires_at.tzinfo is None:
        logger.warning("Naive expires_at treated as JST: %s", expires_at_iso)
        expires_at = expires_at.replace(tzinfo=JST)
    return expires_at <= _now_jst()


def generate_code() -> str:
    """Return a single random 6-character invitation code."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def find_active(code: str) -> dict[str, Any] | None:
    """Return the pending record for ``code`` if it exists and is unexpired."""
    data = _load()
    for inv in data["invitations"]:
        if inv.get("code") != code:
            continue
        if inv.get("used_at") is None and not is_expired(
            str(inv.get("expires_at", ""))
        ):
            return inv
    return None


def _generate_unique_code(existing: list[dict[str, Any]]) -> str:
    """Generate a code that does not collide with any existing record."""
    existing_codes = {inv.get("code") for inv in existing}
    for _ in range(_MAX_GENERATE_RETRIES):
        candidate = generate_code()
        if candidate not in existing_codes:
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
    now = _now_jst()
    now_iso = _iso(now)

    # Revoke-then-issue under a single lock so two rapid re-issues from
    # the same student cannot leave two active codes (docs/05 §3.1,
    # Issue #45).
    with locked_edit(_FILE, default=None) as data:
        data = _ensure_shape(data)

        revoked = 0
        for inv in data["invitations"]:
            if (
                inv.get("student_user_id") == student_user_id
                and inv.get("used_at") is None
                and not is_expired(str(inv.get("expires_at", "")))
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
    # Check-and-mark under a single lock so two parents entering the
    # same code cannot both succeed (docs/05 §3.1, Issue #45).
    with locked_edit(_FILE, default=None) as data:
        data = _ensure_shape(data)
        target: dict[str, Any] | None = None
        for inv in data["invitations"]:
            if (
                inv.get("code") == code
                and inv.get("used_at") is None
                and not is_expired(str(inv.get("expires_at", "")))
            ):
                target = inv
                break

        if target is None:
            for inv in data["invitations"]:
                if inv.get("code") != code:
                    continue
                if inv.get("used_at") is not None:
                    return None, "used"
                if is_expired(str(inv.get("expires_at", ""))):
                    return None, "expired"
            return None, "not_found"
        if target["student_user_id"] == parent_user_id:
            return None, "self_link"

        target["used_at"] = _iso(_now_jst())
        target["used_by_parent_id"] = parent_user_id
        student_user_id = target["student_user_id"]
    return student_user_id, "ok"
