"""Sponsored PR matching and engagement tracking (FR-S9).

The want-to-do consultation carousel may lead with a single sponsored
event (job hunting / hackathon / idea contest) that matches the student's
profile. Selection is deterministic and runs *after* Gemini returns its
organic proposals, so sponsor data never reaches the prompt (this keeps
the LLM from paraphrasing or inventing dates and eligibility rules). See
``docs/04_functional_spec.md §4.3`` and ``docs/05_data_model.md §4.12``.

Matching scores ``active`` entries against the profile's ``faculty`` /
``grade`` / ``interests`` and returns the single top-scoring entry, or
``None`` when nothing matches. Interest taps are logged to
``sponsored_engagement.json`` with a hashed user id (the raw id is never
stored).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.services import seed
from src.services.storage import locked_edit

logger = logging.getLogger(__name__)

_FILE = "sponsored_engagement.json"
JST = ZoneInfo("Asia/Tokyo")


def _score(profile: dict[str, Any], item: dict[str, Any]) -> int:
    """Return the match score for ``item`` against ``profile``.

    Scoring (docs/05 §4.12): faculty partial match ``+1``, grade exact
    match ``+1``, and one point per overlapping interest tag. An empty
    ``target`` field means "all students" for that axis and contributes
    no points. A score of ``0`` means no axis matched.

    Args:
        profile: The student profile dict (``faculty`` / ``grade`` /
            ``interests``).
        item: A single sponsored entry from the seed.

    Returns:
        The integer match score (``0`` when nothing matches).
    """
    target = item.get("target", {})
    score = 0

    faculty = profile.get("faculty") or ""
    target_faculties = target.get("faculties") or []
    if faculty and any(f and f in faculty for f in target_faculties):
        score += 1

    grade = str(profile.get("grade") or "")
    target_grades = [str(g) for g in (target.get("grades") or [])]
    if grade and grade in target_grades:
        score += 1

    interests = {str(i).lower() for i in (profile.get("interests") or [])}
    target_tags = target.get("interest_tags") or []
    score += sum(1 for tag in target_tags if str(tag).lower() in interests)

    return score


def match_for_profile(
    profile: dict[str, Any], items: list[dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    """Return the best-matching active sponsored entry, or ``None``.

    Deterministic selection: filter to ``active`` entries, score each
    against ``profile``, and return the highest-scoring one. Entries with
    a score of ``0`` are excluded so unrelated ads are never forced onto
    the student. Ties resolve to seed order (first wins).

    Args:
        profile: The student profile dict.
        items: Sponsored entries to consider. Defaults to the seed
            (``seed.get_sponsored()``); injectable for tests.

    Returns:
        The top-scoring sponsored entry, or ``None`` when none match.
    """
    if not profile:
        return None
    candidates = seed.get_sponsored() if items is None else items

    best: dict[str, Any] | None = None
    best_score = 0
    for item in candidates:
        if not item.get("active"):
            continue
        score = _score(profile, item)
        if score > best_score:
            best = item
            best_score = score
    return best


def get_by_id(sponsor_id: str) -> dict[str, Any] | None:
    """Return the sponsored entry with ``sponsor_id``, or ``None``."""
    for item in seed.get_sponsored():
        if item.get("sponsor_id") == sponsor_id:
            return item
    return None


def _hash_user_id(user_id: str) -> str:
    """Return a stable hash of ``user_id`` (raw value is never stored)."""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def record_interest(user_id: str, sponsor_id: str) -> None:
    """Append an "興味あり" tap to ``sponsored_engagement.json`` (FR-S9).

    The LINE user id is hashed before storage so the raw identifier never
    lands on disk (docs/05 §4.13). The store is an append-only event log.

    Args:
        user_id: The LINE user id of the tapping student.
        sponsor_id: The tapped sponsored entry's id.
    """
    # Append-only log, but two near-simultaneous taps (Flex carousel
    # re-tap during network hiccup) can race — the lock guarantees both
    # events land (docs/05 §3.1, Issue #45).
    with locked_edit(_FILE, default={"events": []}) as data:
        if "events" not in data:
            data["events"] = []
        data["events"].append(
            {
                "sponsor_id": sponsor_id,
                "user_hash": _hash_user_id(user_id),
                "clicked_at": datetime.now(JST).isoformat(),
            }
        )
    logger.info(
        "Sponsored interest recorded: sponsor=%s user=%s",
        sponsor_id,
        user_id[:8],
    )
