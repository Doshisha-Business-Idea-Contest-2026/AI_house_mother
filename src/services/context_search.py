"""Very simple keyword-based context retrieval for life consultation.

We do not run RAG or embeddings. Instead we do case-insensitive
substring matching against seed items and score them so the top-k items
can be fed into the Gemini prompt.

See ``docs/06_ai_spec.md §5.3`` for the Zero-context handling contract
that this module supports.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from src.services import posts, seed

# Emergency detection keywords, split by severity.
EMERGENCY_LIFE = ["死にたい", "消えたい", "自殺"]
EMERGENCY_MEDICAL = ["救急", "119", "倒れた", "動けない", "血が"]
EMERGENCY_CRIME = ["犯罪", "盗まれた", "暴力", "襲われた"]

# Non-emergency medical keywords used to trigger the #7119 followup on
# Zero-context replies (see docs/06_ai_spec.md §5.3.5). "痛" is a root
# form so 痛い / 痛く / 痛かった / 頭痛 all match; the few false-
# positives (e.g. 痛快) are acceptable because the followup only fires
# under Zero-context anyway.
MEDICAL_INTENT_KEYWORDS = [
    "病院",
    "クリニック",
    "診療所",
    "熱",
    "体調",
    "薬",
    "症状",
    "痛",
    "怪我",
    "風邪",
    "めまい",
    "吐き気",
]


class ContextSearchResult(TypedDict):
    """Structured result returned by :func:`find_relevant_context`.

    - ``stores`` / ``areas`` / ``senior_posts`` are the top-k seed items
      that scored above zero for the current query.
    - ``student_posts`` are the top-k anonymized runtime posts (only the
      allow-listed fields from :func:`posts.list_all_for_context`); this
      is the SECI-model inheritance channel documented in
      ``docs/06_ai_spec.md §4.2``.
    - ``total_hits`` is the sum of the four lists' lengths.
    - ``matched_categories`` is the set of ``category`` fields collected
      from those items (used later for post-hoc analytics).
    """

    stores: list[dict[str, Any]]
    areas: list[dict[str, Any]]
    senior_posts: list[dict[str, Any]]
    student_posts: list[dict[str, Any]]
    total_hits: int
    matched_categories: set[str]


_TOKEN_SPLIT = re.compile(r"[\s、。,.!?！？]+")
# Filler characters we should not emit as 2-gram tokens.
_STOP_CHARS = set("　のをにはでとがもへよねなるかしてこそあっう")


def detect_emergency(user_message: str) -> str | None:
    """Return the emergency category name, or ``None`` when not urgent.

    Categories: ``"life"`` (self-harm), ``"medical"`` (119 events),
    ``"crime"`` (police cases).
    """
    text = user_message
    if any(kw in text for kw in EMERGENCY_LIFE):
        return "life"
    if any(kw in text for kw in EMERGENCY_MEDICAL):
        return "medical"
    if any(kw in text for kw in EMERGENCY_CRIME):
        return "crime"
    return None


def _tokens(text: str) -> list[str]:
    """Return coarse tokens plus 2-gram substrings.

    Japanese text often has no whitespace, so we complement the naive
    split with 2-character overlapping windows. Common filler characters
    like ``の`` / ``を`` / ``に`` are skipped as anchors so a 2-gram must
    contain at least one meaningful character.
    """
    coarse = [t.strip().lower() for t in _TOKEN_SPLIT.split(text) if t.strip()]
    grams: list[str] = []
    lowered = text.lower()
    for i in range(len(lowered) - 1):
        window = lowered[i : i + 2]
        if not window.strip():
            continue
        if window[0] in _STOP_CHARS or window[1] in _STOP_CHARS:
            continue
        grams.append(window)
    seen: set[str] = set()
    unique: list[str] = []
    for tok in coarse + grams:
        if tok in seen:
            continue
        seen.add(tok)
        unique.append(tok)
    return unique


def _score(item: dict[str, Any], fields: list[str], tokens: list[str]) -> int:
    if not tokens:
        return 0
    haystack = " ".join(str(item.get(f, "")) for f in fields).lower()
    for tag in item.get("tags", []) or []:
        haystack += " " + str(tag).lower()
    return sum(1 for tok in tokens if tok and tok in haystack)


def find_relevant_context(user_message: str, top_k: int = 5) -> ContextSearchResult:
    """Return matched seed items grouped by kind plus aggregate stats.

    See ``docs/06_ai_spec.md §5.3.3`` for the contract.
    """
    tokens = _tokens(user_message)

    def rank(items: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
        scored = [(_score(it, fields, tokens), it) for it in items]
        scored = [pair for pair in scored if pair[0] > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored[:top_k]]

    stores = rank(seed.get_stores(), ["name", "description", "area"])
    areas = rank(seed.get_areas(), ["name", "description"])
    senior_posts = rank(seed.get_senior_posts(), ["title", "body", "area"])
    student_posts = rank(posts.list_all_for_context(), ["title", "body", "area"])

    matched: set[str] = set()
    for item in (*stores, *areas, *senior_posts, *student_posts):
        category = item.get("category")
        if isinstance(category, str) and category:
            matched.add(category)

    return {
        "stores": stores,
        "areas": areas,
        "senior_posts": senior_posts,
        "student_posts": student_posts,
        "total_hits": (
            len(stores) + len(areas) + len(senior_posts) + len(student_posts)
        ),
        "matched_categories": matched,
    }


def should_add_disclaimer(result: ContextSearchResult) -> bool:
    """Return True when the Zero-context branch must fire.

    MVP: strictly ``total_hits == 0``. See ``docs/06_ai_spec.md §5.3.2``.
    """
    return result["total_hits"] == 0


def detect_medical_intent(user_message: str) -> bool:
    """Return True when the message contains non-emergency medical keywords.

    Distinct from :func:`detect_emergency` — this catches everyday medical
    topics (「病院」「クリニック」「体調」…) so a Zero-context reply can
    append the #7119 followup. See ``docs/06_ai_spec.md §5.3.5``.
    """
    return any(kw in user_message for kw in MEDICAL_INTENT_KEYWORDS)
