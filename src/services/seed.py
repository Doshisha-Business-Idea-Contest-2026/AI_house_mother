"""Seed data loader.

Loads the ``data/seed/*.json`` fixtures on first access and caches them
in memory. All lookups are read-only; there is no writeback path.
"""
import logging
from pathlib import Path
from typing import Any

from src.services.storage import load_json

logger = logging.getLogger(__name__)

_SEED_FILES = {
    "areas": ("seed/areas.json", "areas"),
    "stores": ("seed/stores.json", "stores"),
    "events": ("seed/events.json", "events"),
    "senior_posts": ("seed/senior_posts.json", "senior_posts"),
    "demo_profiles": ("seed/demo_profiles.json", "demo_profiles"),
}

_cache: dict[str, list[dict[str, Any]]] | None = None


def load_all(force_reload: bool = False) -> dict[str, list[dict[str, Any]]]:
    """Return every seed collection as a dict of lists.

    Args:
        force_reload: When ``True`` bypass the module-level cache.

    Returns:
        Dictionary keyed by ``areas``, ``stores``, ``events``,
        ``senior_posts``, ``demo_profiles``. Each value is the ``list``
        stored under the corresponding top-level key of the JSON file.
    """
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    loaded: dict[str, list[dict[str, Any]]] = {}
    for key, (relative_path, root_key) in _SEED_FILES.items():
        data = load_json(relative_path, default={root_key: []})
        loaded[key] = data.get(root_key, [])
    _cache = loaded
    logger.info(
        "Seed loaded: areas=%d stores=%d events=%d senior_posts=%d demo_profiles=%d",
        len(loaded["areas"]),
        len(loaded["stores"]),
        len(loaded["events"]),
        len(loaded["senior_posts"]),
        len(loaded["demo_profiles"]),
    )
    return loaded


# ---------------------------------------------------------------------------
# High-level accessors used by prompts / carousel builders
# ---------------------------------------------------------------------------


def get_areas() -> list[dict[str, Any]]:
    return load_all()["areas"]


def get_stores() -> list[dict[str, Any]]:
    return load_all()["stores"]


def get_events() -> list[dict[str, Any]]:
    return load_all()["events"]


def get_senior_posts() -> list[dict[str, Any]]:
    return load_all()["senior_posts"]


def get_demo_profiles() -> list[dict[str, Any]]:
    return load_all()["demo_profiles"]


def _has_tag_intersection(item_tags: list[str], wanted: list[str]) -> bool:
    if not wanted:
        return False
    lowered = {t.lower() for t in item_tags}
    return any(w.lower() in lowered for w in wanted)


def get_stores_by_tags(tags: list[str], limit: int = 8) -> list[dict[str, Any]]:
    """Return stores whose tags intersect with ``tags``, up to ``limit``."""
    stores = get_stores()
    matched = [s for s in stores if _has_tag_intersection(s.get("tags", []), tags)]
    if len(matched) < limit:
        # top up with generic (non-matched) stores so the LLM has variety
        others = [s for s in stores if s not in matched]
        matched.extend(others[: limit - len(matched)])
    return matched[:limit]


def get_senior_posts_by_keywords(
    keywords: list[str], limit: int = 5
) -> list[dict[str, Any]]:
    """Return senior posts whose title / body / area contains any keyword."""
    if not keywords:
        return get_senior_posts()[:limit]
    lowered = [k.lower() for k in keywords if k]
    scored: list[tuple[int, dict[str, Any]]] = []
    for post in get_senior_posts():
        haystack = " ".join(
            [
                post.get("title", ""),
                post.get("body", ""),
                post.get("area", ""),
                post.get("category", ""),
            ]
        ).lower()
        score = sum(1 for kw in lowered if kw and kw in haystack)
        if score > 0:
            scored.append((score, post))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]


def pick_static_fallback_activities(
    profile: dict[str, Any], count: int = 2
) -> list[dict[str, Any]]:
    """Return ``count`` fallback activities pulled straight from seed.

    Used when Gemini fails or ``GEMINI_MOCK_MODE`` is on. Prefers events
    whose tags overlap with the user's interests, then fills up from the
    rest.
    """
    events = get_events()
    interests = profile.get("interests", [])
    matched = [e for e in events if _has_tag_intersection(e.get("tags", []), interests)]
    others = [e for e in events if e not in matched]
    pool = matched + others

    result: list[dict[str, Any]] = []
    for event in pool[:count]:
        result.append(
            {
                "title": event.get("name", "地域の活動"),
                "summary": event.get("description", "")[:120],
                "location": event.get("area", ""),
                "when": event.get("schedule", ""),
                "why_recommend": "seed データから選ばれたフォールバック候補です。",
                "reference_type": "static_fallback",
            }
        )
    return result


def pick_senior_post_activities(
    profile: dict[str, Any], count: int = 3
) -> list[dict[str, Any]]:
    """Return ``count`` activity dicts derived from senior post seed.

    Fallback for the "ほかの学生の取り組み" branch (docs/06 §4.1.1) when
    Gemini fails or ``GEMINI_MOCK_MODE`` is on. Prefers posts whose
    title/body/area contains one of the student's interests, then fills
    up from the rest. Author identity (``author_pseudonym``) is never
    copied into the result so the anonymization contract holds.
    """
    interests = profile.get("interests", [])
    scored = get_senior_posts_by_keywords(interests, limit=count) if interests else []
    pool = list(scored)
    if len(pool) < count:
        for post in get_senior_posts():
            if post not in pool:
                pool.append(post)
            if len(pool) >= count:
                break

    result: list[dict[str, Any]] = []
    for post in pool[:count]:
        result.append(
            {
                "title": post.get("title", "先輩の取り組み"),
                "summary": (post.get("body", "") or "")[:120],
                "location": post.get("area", ""),
                "when": "",
                "why_recommend": "先輩の体験投稿から選ばれた候補です。",
                "reference_type": "senior_post",
            }
        )
    return result
