"""Gemini API wrapper.

Exposes a small surface used by the handlers:

- :func:`call_gemini` — raw text-in / text-out with sane defaults.
- :func:`propose_activities` — JSON-mode call returning activity dicts,
  with an automatic seed-based fallback when the model fails.
- :func:`answer_life_question` — text answer for a life consultation.
- :func:`answer_activity_detail` — text answer for the "詳しく聞く" button.

The wrapper is deliberately synchronous. The FastAPI router offloads the
call to a worker thread via :func:`asyncio.to_thread`.
"""
from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as gexc

from src.config import GEMINI_API_KEY, GEMINI_MOCK_MODE, GEMINI_MODEL
from src.services import prompts, seed

logger = logging.getLogger(__name__)

# LINE Webhook has a 30 s hard timeout. We stay just under that so a hung
# call still lets the router return 200 before the platform retries.
DEFAULT_TIMEOUT_S = 28
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 500

_ACTIVITY_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "location": {"type": "string"},
            "when": {"type": "string"},
            "why_recommend": {"type": "string"},
            "reference_type": {
                "type": "string",
                "enum": [
                    "event",
                    "volunteer",
                    "store",
                    "senior_post",
                    "generated",
                    "static_fallback",
                ],
            },
        },
        "required": ["title", "summary", "why_recommend", "reference_type"],
    },
}


_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured or GEMINI_MOCK_MODE:
        return
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    genai.configure(api_key=GEMINI_API_KEY)
    _configured = True


def _build_client() -> genai.GenerativeModel:
    _ensure_configured()
    return genai.GenerativeModel(GEMINI_MODEL)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def call_gemini(
    prompt: str,
    *,
    temperature: float = DEFAULT_TEMPERATURE,
    max_output_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> str:
    """Send a plain text prompt and return the text response.

    Returns an empty string if the API fails after one retry.
    """
    if GEMINI_MOCK_MODE:
        logger.info("[GEMINI_MOCK] call_gemini short-circuited")
        return "（mock モードのため実際の応答はありません）"

    cl = _build_client()
    for attempt in (1, 2):
        try:
            response = cl.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens,
                },
                request_options={"timeout": timeout},
            )
            return (response.text or "").strip()
        except gexc.ResourceExhausted:
            logger.warning("Gemini rate limit hit (attempt %d)", attempt)
            time.sleep(5)
        except gexc.DeadlineExceeded:
            logger.warning("Gemini timeout (attempt %d)", attempt)
            time.sleep(1)
        except Exception:
            logger.exception("Gemini call failed on attempt %d", attempt)
            break
    return ""


def propose_activities(
    profile: dict[str, Any] | None,
    *,
    fallback_count: int = 2,
) -> list[dict[str, Any]]:
    """Return 2–3 activity dictionaries proposed by Gemini.

    Falls back to seed-derived choices on failure or when
    ``GEMINI_MOCK_MODE`` is on.
    """
    profile = profile or {}

    if GEMINI_MOCK_MODE:
        logger.info("[GEMINI_MOCK] propose_activities returning static fallback")
        return seed.pick_static_fallback_activities(profile, count=fallback_count)

    interests: list[str] = profile.get("interests") or []
    want_to_do = profile.get("want_to_do") or ""
    keywords = [t for t in interests] + [w for w in want_to_do.split() if w]

    prompt = prompts.build_activity_prompt(
        profile=profile,
        areas=seed.get_areas(),
        stores=seed.get_stores_by_tags(interests),
        events=seed.get_events(),
        senior_posts=seed.get_senior_posts_by_keywords(keywords),
    )

    try:
        cl = _build_client()
        response = cl.generate_content(
            prompt,
            generation_config={
                "temperature": 0.8,
                "max_output_tokens": 800,
                "response_mime_type": "application/json",
                "response_schema": _ACTIVITY_JSON_SCHEMA,
            },
            request_options={"timeout": DEFAULT_TIMEOUT_S},
        )
        raw = (response.text or "").strip()
        activities = _parse_activity_json(raw)
    except gexc.ResourceExhausted:
        logger.warning("[GEMINI_FALLBACK] rate limit on propose_activities")
        activities = []
    except gexc.DeadlineExceeded:
        logger.warning("[GEMINI_FALLBACK] timeout on propose_activities")
        activities = []
    except Exception:
        logger.exception("[GEMINI_FALLBACK] propose_activities failed")
        activities = []

    if not activities:
        activities = seed.pick_static_fallback_activities(profile, count=fallback_count)
    elif len(activities) < 2:
        # Top up with a single static fallback to hit the minimum.
        activities.extend(
            seed.pick_static_fallback_activities(profile, count=2 - len(activities))
        )

    # Shuffle to avoid always-same order between calls
    random.shuffle(activities)
    return activities[:3]


def answer_life_question(
    profile: dict[str, Any] | None,
    user_message: str,
    context_hits: dict[str, Any],
    *,
    total_hits: int,
) -> str:
    """Return a Gemini-generated answer for a life-consultation question.

    ``total_hits`` must be the aggregate seed hit count from
    :func:`context_search.find_relevant_context`. When it is 0 the prompt
    forbids Gemini from inventing concrete facts. The Zero-context
    disclaimer and medical followup are prepended / appended by the
    handler layer (``handlers/student.py``) — this function only produces
    the Gemini body.
    """
    if GEMINI_MOCK_MODE:
        return (
            "（mock 応答）先輩の体験や地域情報を踏まえた回答をここに表示します。"
            f"\nあなたの質問: {user_message[:80]}"
        )

    prompt = prompts.build_life_consultation_prompt(
        profile=profile,
        user_message=user_message,
        stores=context_hits.get("stores", []),
        areas=context_hits.get("areas", []),
        senior_posts=context_hits.get("senior_posts", []),
        student_posts=context_hits.get("student_posts", []),
        total_hits=total_hits,
    )
    answer = call_gemini(
        prompt, temperature=0.5, max_output_tokens=500, timeout=DEFAULT_TIMEOUT_S
    )
    if not answer:
        return "うまく答えを考えられませんでした。少し時間を空けてもう一度お試しください。"
    return answer


def answer_activity_detail(
    profile: dict[str, Any] | None, activity: dict[str, Any]
) -> str:
    """Return more detail about a proposed activity."""
    if GEMINI_MOCK_MODE:
        return (
            f"（mock 応答）「{activity.get('title', '')}」について、"
            "参加方法や準備物の詳しい案内を表示します。"
        )
    prompt = prompts.build_activity_detail_prompt(profile=profile, activity=activity)
    answer = call_gemini(
        prompt, temperature=0.5, max_output_tokens=500, timeout=DEFAULT_TIMEOUT_S
    )
    if not answer:
        return (
            f"「{activity.get('title', '')}」の詳細情報を取得できませんでした。"
            "担当団体に直接お問い合わせいただくのがおすすめです。"
        )
    return answer


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _parse_activity_json(raw: str) -> list[dict[str, Any]]:
    """Parse the JSON string returned from Gemini in JSON mode.

    Even with ``response_mime_type: application/json`` there is a small
    chance the SDK returns whitespace-padded JSON or an empty string.
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[GEMINI_FALLBACK] JSON parse failed: %s", raw[:200])
        return []

    if not isinstance(parsed, list):
        logger.warning("[GEMINI_FALLBACK] Unexpected JSON top-level: %s", type(parsed))
        return []

    activities: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if "title" not in item or "summary" not in item:
            continue
        item.setdefault("location", "")
        item.setdefault("when", "")
        item.setdefault("why_recommend", "")
        item.setdefault("reference_type", "generated")
        activities.append(item)
    return activities
