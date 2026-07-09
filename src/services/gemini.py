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
from src.services import posts, prompts, seed

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

# docs/06 §4.5: JSON schema for the post-finalize call (title generation +
# period normalization). Kept minimal so the model returns exactly the two
# fields the confirmation card needs.
_POST_FINALIZE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "period": {"type": "string"},
    },
    "required": ["title", "period"],
}

# Snappy budget for the finalize call: it runs inline before the
# confirmation card, so we keep it well under the webhook timeout.
_FINALIZE_TIMEOUT_S = 8


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


def propose_from_student_efforts(
    profile: dict[str, Any] | None,
    *,
    fallback_count: int = 3,
) -> list[dict[str, Any]]:
    """Return 2–3 activity dicts based on other students' efforts.

    Backs the "ほかの学生の取り組み" branch (docs/06 §4.1.1). Material is
    senior post seed plus anonymized runtime posts
    (:func:`posts.list_all_for_context`). Falls back to senior-post seed
    on failure or when ``GEMINI_MOCK_MODE`` is on.
    """
    profile = profile or {}

    if GEMINI_MOCK_MODE:
        logger.info(
            "[GEMINI_MOCK] propose_from_student_efforts returning seed fallback"
        )
        return seed.pick_senior_post_activities(profile, count=fallback_count)

    interests: list[str] = profile.get("interests") or []
    prompt = prompts.build_student_efforts_prompt(
        profile=profile,
        senior_posts=seed.get_senior_posts_by_keywords(interests),
        student_posts=posts.list_all_for_context(),
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
        logger.warning("[GEMINI_FALLBACK] rate limit on propose_from_student_efforts")
        activities = []
    except gexc.DeadlineExceeded:
        logger.warning("[GEMINI_FALLBACK] timeout on propose_from_student_efforts")
        activities = []
    except Exception:
        logger.exception("[GEMINI_FALLBACK] propose_from_student_efforts failed")
        activities = []

    if not activities:
        activities = seed.pick_senior_post_activities(profile, count=fallback_count)
    elif len(activities) < 2:
        activities.extend(
            seed.pick_senior_post_activities(profile, count=2 - len(activities))
        )

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
        return (
            "うまく答えを考えられませんでした。少し時間を空けてもう一度お試しください。"
        )
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


# See docs/04 §5.3 / docs/06 §4.4: the parent monthly report's closing
# "AI 寮母より" line. Kept close to :func:`summarize_month` so the
# fallback wording never drifts from the code path that emits it.
_MONTH_SUMMARY_FALLBACK = "今月もお子さんは元気に過ごされている様子です。"
_MONTH_SUMMARY_MOCK = "（mock）今月も前向きに過ごされている様子です。"
_SUMMARY_MIN_CONSULT_FOR_LLM = 3


def summarize_month(
    profile: dict[str, Any] | None,
    year_month: str,
    posts_month: list[dict[str, Any]],
    usage: dict[str, int],
) -> str:
    """Return the closing AI comment for the parent monthly report (FR-P3).

    Skips Gemini entirely (returns the fallback line) when the month has
    no shared posts and fewer than
    :data:`_SUMMARY_MIN_CONSULT_FOR_LLM` consultations combined — there
    is not enough material for a meaningful summary, and paying a Gemini
    call for that is wasteful.

    Args:
        profile: The student profile (may be ``None``).
        year_month: Target month string ``"YYYY-MM"``.
        posts_month: Current-month shared posts (only ``title`` is used).
        usage: Current-month counters (``life`` / ``activity`` / ``post``
            / ``profile``, missing keys treated as 0).

    Returns:
        A short plain-text closing line (fallback or Gemini output).
    """
    life = int(usage.get("life", 0))
    activity = int(usage.get("activity", 0))
    if not posts_month and (life + activity) < _SUMMARY_MIN_CONSULT_FOR_LLM:
        return _MONTH_SUMMARY_FALLBACK

    if GEMINI_MOCK_MODE:
        return _MONTH_SUMMARY_MOCK

    prompt = prompts.build_month_summary_prompt(
        profile=profile,
        year_month=year_month,
        posts=posts_month,
        usage=usage,
    )
    answer = call_gemini(
        prompt, temperature=0.6, max_output_tokens=200, timeout=DEFAULT_TIMEOUT_S
    )
    if not answer:
        return _MONTH_SUMMARY_FALLBACK
    return answer


def finalize_post(
    category: str,
    summary: str,
    learned: str,
    regret: str | None,
    advice: str | None,
    area: str | None,
    period_raw: str | None,
    *,
    today: str,
) -> dict[str, str]:
    """Generate a title and normalize the period for an experience post.

    Runs a single JSON-mode Gemini call (FR-S6 / T4.15, docs/06 §4.5) to
    (1) produce a concise title from the post content and (2) rewrite the
    free-text ``period_raw`` into an absolute expression anchored on
    ``today``. Always returns a usable dict: on ``GEMINI_MOCK_MODE``,
    failure, empty response, or malformed JSON it falls back to
    ``title = summary[:MAX_TITLE_LEN]`` and ``period = period_raw``, so
    the post flow never blocks.

    Args:
        category: Post category value.
        summary: What happened (required).
        learned: What was learned (required).
        regret: Disappointment / caveats, or ``None``.
        advice: Advice for the next person, or ``None``.
        area: Free-text location, or ``None``.
        period_raw: The user's raw period words, or ``None``.
        today: Reference date ``"YYYY-MM-DD"`` (JST) for relative periods.

    Returns:
        ``{"title": str, "period": str}`` with the title capped at
        :data:`posts.MAX_TITLE_LEN` and the period at
        :data:`posts.MAX_PERIOD_LEN`.
    """
    fallback_title = (summary or "").strip()[: posts.MAX_TITLE_LEN]
    fallback_period = (period_raw or "").strip()

    if GEMINI_MOCK_MODE:
        logger.info("[GEMINI_MOCK] finalize_post returning fallback")
        return {"title": fallback_title, "period": fallback_period}

    prompt = prompts.build_post_finalize_prompt(
        category=category,
        summary=summary,
        learned=learned,
        regret=regret,
        advice=advice,
        area=area,
        period_raw=period_raw,
        today=today,
    )

    parsed: dict[str, Any] = {}
    try:
        cl = _build_client()
        response = cl.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 120,
                "response_mime_type": "application/json",
                "response_schema": _POST_FINALIZE_JSON_SCHEMA,
            },
            request_options={"timeout": _FINALIZE_TIMEOUT_S},
        )
        parsed = _parse_finalize_json((response.text or "").strip())
    except gexc.ResourceExhausted:
        logger.warning("[GEMINI_FALLBACK] rate limit on finalize_post")
    except gexc.DeadlineExceeded:
        logger.warning("[GEMINI_FALLBACK] timeout on finalize_post")
    except Exception:
        logger.exception("[GEMINI_FALLBACK] finalize_post failed")

    title = (parsed.get("title") or "").strip()[: posts.MAX_TITLE_LEN] or fallback_title
    period = (parsed.get("period") or "").strip()[: posts.MAX_PERIOD_LEN]
    if not period:
        # Empty from the model: keep the user's own words rather than
        # dropping the period entirely (only truly-blank input stays "").
        period = fallback_period
    return {"title": title, "period": period}


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


def _parse_finalize_json(raw: str) -> dict[str, Any]:
    """Parse the JSON object returned by the post-finalize call.

    Returns an empty dict on any problem (empty string, malformed JSON,
    or a non-object top level) so :func:`finalize_post` applies its
    fallback.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[GEMINI_FALLBACK] finalize JSON parse failed: %s", raw[:200])
        return {}
    if not isinstance(parsed, dict):
        logger.warning(
            "[GEMINI_FALLBACK] finalize JSON top-level not an object: %s", type(parsed)
        )
        return {}
    return parsed
