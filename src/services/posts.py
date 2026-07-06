"""Student experience post persistence.

Persists student-authored posts to ``data/posts.json``. The month-scoped
readers below are the only way the parent-facing monthly summary sees
into this file, and they **must** keep the ``share_with_parent == True``
filter in place — dropping it would leak private posts to the parent
Flex message. See ``docs/04_functional_spec.md`` §4.5 and
``docs/05_data_model.md`` §4.3.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.services.storage import load_json, save_json

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_FILE = "posts.json"
_EMPTY: dict[str, list] = {"posts": []}

POST_ID_PREFIX = "P"
POST_ID_DIGITS = 5

CATEGORY_VALUES: tuple[str, ...] = (
    "event",
    "volunteer",
    "store",
    "medical",
    "tips",
    "other",
)
MAX_TITLE_LEN = 40
MAX_BODY_LEN = 500


def _load() -> dict[str, Any]:
    data = load_json(_FILE, default=_EMPTY)
    if "posts" not in data:
        data["posts"] = []
    return data


def _next_post_id(existing: list[dict[str, Any]]) -> str:
    """Return the next ``P``-prefixed sequential id.

    Scans ``existing`` for the largest numeric suffix and returns
    ``P`` + zero-padded ``max + 1``. Non-conforming ids are ignored.
    """
    max_num = 0
    for row in existing:
        pid = row.get("post_id", "")
        if not isinstance(pid, str) or not pid.startswith(POST_ID_PREFIX):
            continue
        try:
            n = int(pid[len(POST_ID_PREFIX):])
        except ValueError:
            continue
        if n > max_num:
            max_num = n
    return f"{POST_ID_PREFIX}{max_num + 1:0{POST_ID_DIGITS}d}"


def _normalize_area(area: str | None) -> str | None:
    """Normalize free-text area input to ``str`` or ``None``.

    Empty strings and the tokens ``なし``/``無し``/``skip`` (any case)
    are treated as "no area" per docs/04 §4.5.
    """
    if area is None:
        return None
    stripped = area.strip()
    if not stripped:
        return None
    if stripped.lower() in {"skip"}:
        return None
    if stripped in {"なし", "無し"}:
        return None
    return stripped


def add_post(
    line_user_id: str,
    category: str,
    title: str,
    body: str,
    area: str | None,
    share_with_parent: bool,
) -> dict[str, Any]:
    """Append a new post and return the stored record.

    Args:
        line_user_id: Author LINE user id.
        category: One of :data:`CATEGORY_VALUES`.
        title: Post title (truncated to :data:`MAX_TITLE_LEN`).
        body: Post body (truncated to :data:`MAX_BODY_LEN`).
        area: Free-text location, normalized via :func:`_normalize_area`.
        share_with_parent: Whether the post is exposed to linked parents
            through the monthly summary.

    Raises:
        ValueError: If ``category`` is not one of :data:`CATEGORY_VALUES`.
    """
    if category not in CATEGORY_VALUES:
        raise ValueError(f"Invalid category: {category}")

    data = _load()
    post_id = _next_post_id(data["posts"])
    record: dict[str, Any] = {
        "post_id": post_id,
        "line_user_id": line_user_id,
        "category": category,
        "title": title.strip()[:MAX_TITLE_LEN],
        "body": body.strip()[:MAX_BODY_LEN],
        "area": _normalize_area(area),
        "share_with_parent": bool(share_with_parent),
        "created_at": datetime.now(JST).isoformat(),
    }
    data["posts"].append(record)
    save_json(_FILE, data)
    logger.info(
        "post_added user=%s post_id=%s category=%s share=%s",
        line_user_id[:8],
        post_id,
        category,
        share_with_parent,
    )
    return record


def list_month_shared(
    student_user_id: str, year: int, month: int
) -> list[dict[str, Any]]:
    """Return all ``share_with_parent=True`` posts of the given JST month.

    Args:
        student_user_id: LINE user id of the author.
        year: Target JST year.
        month: Target JST month (1-12).

    Returns:
        Matching post dicts sorted by ``created_at`` ascending.
    """
    data = _load()
    matches: list[dict[str, Any]] = []
    for row in data["posts"]:
        if row.get("line_user_id") != student_user_id:
            continue
        if not row.get("share_with_parent"):
            continue
        created_at = row.get("created_at", "")
        try:
            created = datetime.fromisoformat(created_at).astimezone(JST)
        except (ValueError, TypeError):
            continue
        if created.year == year and created.month == month:
            matches.append(row)
    matches.sort(key=lambda r: r.get("created_at", ""))
    return matches


def list_current_month_shared(
    student_user_id: str, now_jst: datetime | None = None
) -> list[dict[str, Any]]:
    """Return this JST month's shared posts for ``student_user_id``.

    Args:
        student_user_id: LINE user id of the author.
        now_jst: Optional reference datetime (in JST) used to determine
            the "current" month. Defaults to :func:`datetime.now`.
    """
    ref = (now_jst or datetime.now(JST)).astimezone(JST)
    return list_month_shared(student_user_id, ref.year, ref.month)
