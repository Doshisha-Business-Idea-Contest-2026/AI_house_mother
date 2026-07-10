"""Parent <-> student link persistence.

A link record captures which parent LINE user is authorised to receive
monthly summaries of which student. See ``docs/04_functional_spec.md``
§5.2 and ``docs/05_data_model.md`` §4.5.

Relationships:
    * One student -> N parents (each parent authenticates with their own
      invitation code).
    * One parent -> N students (a parent with several children uses one
      code per child).

The ``link`` function is idempotent on ``(parent_user_id,
student_user_id)``: repeated calls refresh ``linked_at`` and ensure
``active`` is True, but do not create duplicate rows.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.services.storage import load_json, locked_edit

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_FILE = "parent_links.json"


def _now_iso() -> str:
    return datetime.now(JST).isoformat()


def _ensure_shape(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("links"), list):
        data["links"] = []
    return data


def _load() -> dict[str, Any]:
    return _ensure_shape(load_json(_FILE, default=None))


def link(parent_user_id: str, student_user_id: str) -> dict[str, Any]:
    """Create or reactivate the ``(parent, student)`` link.

    If a record for the same pair already exists, its ``linked_at`` is
    refreshed and ``active`` is set to True (idempotent). Otherwise a new
    row is appended.

    Args:
        parent_user_id: LINE user id of the parent.
        student_user_id: LINE user id of the student.

    Returns:
        The stored (or updated) link record.
    """
    now = _now_iso()
    # Wrap the "find-or-append" walk under a lock so a re-tap of the
    # link button from another LINE session cannot append a duplicate
    # row (docs/05 §3.1, Issue #45).
    with locked_edit(_FILE, default=None) as data:
        data = _ensure_shape(data)
        for row in data["links"]:
            if (
                row["parent_user_id"] == parent_user_id
                and row["student_user_id"] == student_user_id
            ):
                row["linked_at"] = now
                row["active"] = True
                logger.info(
                    "parent_link refreshed parent=%s student=%s",
                    parent_user_id[:8],
                    student_user_id[:8],
                )
                return row

        record: dict[str, Any] = {
            "parent_user_id": parent_user_id,
            "student_user_id": student_user_id,
            "linked_at": now,
            "active": True,
        }
        data["links"].append(record)
    logger.info(
        "parent_link created parent=%s student=%s",
        parent_user_id[:8],
        student_user_id[:8],
    )
    return record


def list_students_for_parent(parent_user_id: str) -> list[str]:
    """Return student ids linked to ``parent_user_id`` (only ``active``)."""
    data = _load()
    return [
        row["student_user_id"]
        for row in data["links"]
        if row["parent_user_id"] == parent_user_id and row.get("active", True)
    ]


def list_parents_for_student(student_user_id: str) -> list[str]:
    """Return parent ids linked to ``student_user_id`` (only ``active``)."""
    data = _load()
    return [
        row["parent_user_id"]
        for row in data["links"]
        if row["student_user_id"] == student_user_id and row.get("active", True)
    ]


def list_all_active_pairs() -> list[tuple[str, str]]:
    """Return ``(parent_user_id, student_user_id)`` for every active link."""
    data = _load()
    return [
        (row["parent_user_id"], row["student_user_id"])
        for row in data["links"]
        if row.get("active", True)
    ]
