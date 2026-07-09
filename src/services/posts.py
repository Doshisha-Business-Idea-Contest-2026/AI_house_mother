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

POST_ID_PREFIX = "P"
POST_ID_DIGITS = 5

CATEGORY_VALUES: tuple[str, ...] = (
    "event",
    "volunteer",
    "store",
    "medical",
    "tips",
    "study",
    "money",
    "social",
    "effort",
    "other",
)
MAX_TITLE_LEN = 40
# ``body`` is a composed/derived field (see ``compose_body``); its cap must
# accommodate the concatenation of the five structured fields plus their
# ``【…】`` labels, so it is larger than any single field.
MAX_BODY_LEN = 1200
MAX_PERIOD_LEN = 100
MAX_SUMMARY_LEN = 300
MAX_LEARNED_LEN = 200
MAX_REGRET_LEN = 200
MAX_ADVICE_LEN = 200

# docs/04 §4.5: tokens that mean "no value" for skippable free-text steps
# (period / regret / advice) and the area step. Matched case-insensitively.
_SKIP_TOKENS: frozenset[str] = frozenset({"skip", "スキップ", "なし", "無し"})


def _load() -> dict[str, Any]:
    # Pass ``default=None`` (not a shared ``{"posts": []}`` constant): a
    # module-level mutable default is aliased across calls, so appending
    # to it when the file is missing would leak records between writes.
    data = load_json(_FILE, default=None)
    if not isinstance(data, dict):
        data = {}
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
            n = int(pid[len(POST_ID_PREFIX) :])
        except ValueError:
            continue
        if n > max_num:
            max_num = n
    return f"{POST_ID_PREFIX}{max_num + 1:0{POST_ID_DIGITS}d}"


def _normalize_skippable(text: str | None) -> str | None:
    """Normalize a skippable free-text input to ``str`` or ``None``.

    Empty strings and the skip tokens in :data:`_SKIP_TOKENS`
    (``skip`` / ``スキップ`` / ``なし`` / ``無し``, case-insensitive) are
    treated as "no value" per docs/04 §4.5. Used by the optional post
    steps (period / regret / advice) and by :func:`_normalize_area`.

    Args:
        text: Raw user input, or ``None``.

    Returns:
        The stripped text, or ``None`` when it is empty or a skip token.
    """
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.lower() in _SKIP_TOKENS:
        return None
    return stripped


def _normalize_area(area: str | None) -> str | None:
    """Normalize free-text area input to ``str`` or ``None``.

    Thin wrapper over :func:`_normalize_skippable` kept for call-site
    clarity; the area step shares the same skip-token semantics.
    """
    return _normalize_skippable(area)


def compose_body(
    period: str | None,
    summary: str | None,
    learned: str | None,
    regret: str | None,
    advice: str | None,
) -> str:
    """Compose the derived ``body`` from the five structured post fields.

    Non-empty fields are rendered as ``【label】value`` lines in a fixed
    order and joined by newlines (docs/04 §4.5, docs/05 §4.3). Empty or
    skipped fields are omitted so the body stays clean. The result feeds
    both the parent monthly report preview and the anonymized SECI
    context, so the two downstream readers need no changes.

    Args:
        period: When / duration (optional).
        summary: What happened (required upstream).
        learned: What was learned / went well (required upstream).
        regret: What was disappointing / caveats (optional).
        advice: Advice for the next person (optional).

    Returns:
        The composed body, truncated to :data:`MAX_BODY_LEN`.
    """
    sections: list[tuple[str, str | None]] = [
        ("いつ", period),
        ("やったこと", summary),
        ("学び", learned),
        ("残念・注意", regret),
        ("次の人へ", advice),
    ]
    lines = [
        f"【{label}】{value.strip()}"
        for label, value in sections
        if value is not None and value.strip()
    ]
    return "\n".join(lines)[:MAX_BODY_LEN]


def _truncate(text: str | None, limit: int) -> str | None:
    """Trim and cap an optional field, preserving ``None``."""
    if text is None:
        return None
    return text.strip()[:limit]


def add_post(
    line_user_id: str,
    category: str,
    title: str,
    summary: str,
    learned: str,
    area: str | None,
    share_with_parent: bool,
    period: str | None = None,
    period_raw: str | None = None,
    regret: str | None = None,
    advice: str | None = None,
) -> dict[str, Any]:
    """Append a new structured post and return the stored record.

    The five structured fields are stored individually and also folded
    into a composed ``body`` via :func:`compose_body`, so the parent
    monthly report and the SECI context (both read ``body``) keep working
    unchanged (docs/04 §4.5, docs/05 §4.3).

    Args:
        line_user_id: Author LINE user id.
        category: One of :data:`CATEGORY_VALUES`.
        title: Post title (truncated to :data:`MAX_TITLE_LEN`).
        summary: What happened (required, truncated to :data:`MAX_SUMMARY_LEN`).
        learned: What was learned (required, truncated to :data:`MAX_LEARNED_LEN`).
        area: Free-text location, normalized via :func:`_normalize_area`.
        share_with_parent: Whether the post is exposed to linked parents
            through the monthly summary.
        period: The LLM-normalized absolute period (optional,
            :data:`MAX_PERIOD_LEN`). Used for the composed ``body``.
        period_raw: The user's raw period words before normalization
            (optional, :data:`MAX_PERIOD_LEN`). Preserved for intent.
        regret: What was disappointing / caveats (optional, :data:`MAX_REGRET_LEN`).
        advice: Advice for the next person (optional, :data:`MAX_ADVICE_LEN`).

    Raises:
        ValueError: If ``category`` is not one of :data:`CATEGORY_VALUES`.
    """
    if category not in CATEGORY_VALUES:
        raise ValueError(f"Invalid category: {category}")

    period_v = _truncate(period, MAX_PERIOD_LEN)
    period_raw_v = _truncate(period_raw, MAX_PERIOD_LEN)
    summary_v = _truncate(summary, MAX_SUMMARY_LEN) or ""
    learned_v = _truncate(learned, MAX_LEARNED_LEN) or ""
    regret_v = _truncate(regret, MAX_REGRET_LEN)
    advice_v = _truncate(advice, MAX_ADVICE_LEN)

    # The body's 【いつ】 uses the normalized period; fall back to the raw
    # words when normalization was skipped or failed (docs/05 §4.3).
    period_for_body = period_v or period_raw_v

    data = _load()
    post_id = _next_post_id(data["posts"])
    record: dict[str, Any] = {
        "post_id": post_id,
        "line_user_id": line_user_id,
        "category": category,
        "title": title.strip()[:MAX_TITLE_LEN],
        "period_raw": period_raw_v,
        "period": period_v,
        "summary": summary_v,
        "learned": learned_v,
        "regret": regret_v,
        "advice": advice_v,
        "body": compose_body(period_for_body, summary_v, learned_v, regret_v, advice_v),
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


def count_all_shared(student_user_id: str) -> int:
    """Return the total lifetime count of ``share_with_parent=True`` posts.

    Used by the parent monthly report (FR-P3 extension) to show the
    cumulative "頑張ったこと" total alongside the current month's count.
    """
    data = _load()
    return sum(
        1
        for row in data["posts"]
        if row.get("line_user_id") == student_user_id and row.get("share_with_parent")
    )


def count_all(student_user_id: str) -> int:
    """Return the total lifetime count of a student's experience posts.

    Unlike :func:`count_all_shared` this counts every post regardless of
    ``share_with_parent``. It is the trigger denominator for coupon
    distribution (FR-S10, docs/04 §4.8): a batch is awarded every time
    this total reaches a new multiple of three.
    """
    data = _load()
    return sum(1 for row in data["posts"] if row.get("line_user_id") == student_user_id)


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


# Fields allowed to reach the life-consultation Gemini prompt. Keep this
# tuple in lockstep with docs/06_ai_spec §4.2 and docs/05_data_model §8:
# adding anything that could identify the author (line_user_id, post_id,
# share_with_parent, profile fields) would break the anonymization
# contract behind the SECI-model knowledge inheritance feature.
_CONTEXT_FIELDS: tuple[str, ...] = (
    "title",
    "body",
    "area",
    "category",
    "created_at",
)


def list_all_for_context() -> list[dict[str, Any]]:
    """Return every stored post projected to the anonymized allow-list.

    The result feeds ``context_search.find_relevant_context`` (T4.10)
    which forwards it to the life-consultation Gemini prompt. Only the
    five fields listed in :data:`_CONTEXT_FIELDS` are exposed;
    ``line_user_id`` / ``post_id`` / ``share_with_parent`` / any profile
    information must never be reintroduced here.

    Returns:
        A list of dicts with keys ``title``, ``body``, ``area``,
        ``category`` and ``created_at``. Original ordering is preserved.
    """
    data = _load()
    projected: list[dict[str, Any]] = []
    for row in data["posts"]:
        entry = {field: row.get(field) for field in _CONTEXT_FIELDS}
        projected.append(entry)
    return projected
