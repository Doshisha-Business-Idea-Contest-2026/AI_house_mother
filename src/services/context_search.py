"""Very simple keyword-based context retrieval for life consultation.

We do not run RAG or embeddings. Instead we do case-insensitive
substring matching against seed items and score them so the top-k items
can be fed into the Gemini prompt.
"""
from __future__ import annotations

import re
from typing import Any

from src.services import seed

# Emergency detection keywords, split by severity.
EMERGENCY_LIFE = ["死にたい", "消えたい", "自殺"]
EMERGENCY_MEDICAL = ["救急", "119", "倒れた", "動けない", "血が"]
EMERGENCY_CRIME = ["犯罪", "盗まれた", "暴力", "襲われた"]

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


def find_relevant_context(
    user_message: str, top_k: int = 5
) -> dict[str, list[dict[str, Any]]]:
    """Return matched seed items grouped by kind."""
    tokens = _tokens(user_message)

    def rank(items: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
        scored = [(_score(it, fields, tokens), it) for it in items]
        scored = [pair for pair in scored if pair[0] > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored[:top_k]]

    return {
        "stores": rank(seed.get_stores(), ["name", "description", "area"]),
        "areas": rank(seed.get_areas(), ["name", "description"]),
        "senior_posts": rank(seed.get_senior_posts(), ["title", "body", "area"]),
    }
