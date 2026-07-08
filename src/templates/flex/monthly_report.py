"""Flex Message bubble for the monthly parent summary (FR-P3).

A single mega bubble that folds together three sections:

1. **頑張ったこと** — shared post list (up to ``MAX_POSTS_IN_REPORT``)
   with a subtitle showing the previous month's count and the lifetime
   total.
2. **今月の利用** — current-month consultation and record counts, or a
   qualitative sentence when consultations are below the threshold
   (see ``services/monthly_report.LOW_CONSULT_THRESHOLD``).
3. **AI 寮母より** — Gemini-authored closing line.

Layout stays lean: no "send a message" button and no external links so
the parent view keeps the focus on the student's own text.
"""

from __future__ import annotations

from typing import Any

HEADER_COLOR = "#00579C"
_BODY_PREVIEW_LEN = 60
_SEPARATOR_COLOR = "#e0e0e0"

CATEGORY_EMOJI: dict[str, str] = {
    "event": "🏛️",
    "volunteer": "🧹",
    "store": "🍜",
    "medical": "🏥",
    "tips": "📋",
    "study": "🎓",
    "money": "💰",
    "social": "🤝",
    "effort": "💪",
    "other": "✨",
}

# docs/04 §5.3: same threshold the service uses to decide qualitative vs.
# numeric usage rendering. Keep as a local copy for the renderer so the
# Flex module doesn't import the service (avoids a cycle).
_LOW_CONSULT_THRESHOLD = 3

_LOW_CONSULT_TEXT = "今月も自分から相談していました"
_NO_ACTIVITY_TEXT = "今月はゆっくり過ごされていたようです"


def _shorten(text: str, limit: int = _BODY_PREVIEW_LEN) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _post_row(post: dict[str, Any]) -> list[dict[str, Any]]:
    emoji = CATEGORY_EMOJI.get(post.get("category", "other"), "✨")
    title = post.get("title", "").strip()
    body_preview = _shorten(post.get("body", ""))
    return [
        {
            "type": "text",
            "text": f"{emoji} {title}",
            "size": "md",
            "weight": "bold",
            "wrap": True,
        },
        {
            "type": "text",
            "text": body_preview,
            "size": "sm",
            "wrap": True,
            "color": "#666666",
        },
    ]


def _posts_section(report: dict[str, Any]) -> list[dict[str, Any]]:
    posts = report.get("posts") or []
    current_count = int(report.get("current_count", len(posts)))
    prev_count = int(report.get("prev_count", 0))
    total_count = int(report.get("total_count", current_count))

    subtitle = f"（先月 {prev_count} / 通算 {total_count}）"

    contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": f"🌸 頑張ったこと {current_count} 件",
            "weight": "bold",
            "size": "md",
        },
        {
            "type": "text",
            "text": subtitle,
            "size": "xs",
            "color": "#999999",
        },
    ]
    if posts:
        contents.append({"type": "separator", "color": _SEPARATOR_COLOR})
    for index, post in enumerate(posts):
        contents.extend(_post_row(post))
        if index < len(posts) - 1:
            contents.append({"type": "separator", "color": _SEPARATOR_COLOR})
    return contents


def _usage_section(report: dict[str, Any]) -> list[dict[str, Any]]:
    usage = report.get("usage") or {}
    life = int(usage.get("life", 0))
    activity = int(usage.get("activity", 0))
    post_count = int(usage.get("post", 0))
    profile_count = int(usage.get("profile", 0))
    consult_total = life + activity
    record_total = post_count + profile_count

    contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": "🏠 今月の利用",
            "weight": "bold",
            "size": "md",
        }
    ]

    # docs/04 §5.3 少回数フォールバック: below the threshold we drop the
    # numeric line and use a qualitative sentence. Zero everything → a
    # different (softer) sentence so parents don't see a bare number.
    if consult_total >= _LOW_CONSULT_THRESHOLD:
        contents.append(
            {
                "type": "text",
                "text": f"相談 {consult_total}回（生活 {life} / 活動 {activity}）",
                "size": "sm",
                "wrap": True,
                "color": "#333333",
            }
        )
    elif consult_total > 0:
        contents.append(
            {
                "type": "text",
                "text": _LOW_CONSULT_TEXT,
                "size": "sm",
                "wrap": True,
                "color": "#333333",
            }
        )

    if record_total > 0:
        contents.append(
            {
                "type": "text",
                "text": (
                    f"記録・更新 {record_total}回"
                    f"（投稿 {post_count} / プロフィール {profile_count}）"
                ),
                "size": "sm",
                "wrap": True,
                "color": "#333333",
            }
        )

    # If both blocks stayed empty (no consultations, no records) we still
    # want a sentence here rather than a lone header.
    if len(contents) == 1:
        contents.append(
            {
                "type": "text",
                "text": _NO_ACTIVITY_TEXT,
                "size": "sm",
                "wrap": True,
                "color": "#333333",
            }
        )
    return contents


def _ai_summary_section(report: dict[str, Any]) -> list[dict[str, Any]]:
    summary = (report.get("ai_summary") or "").strip()
    if not summary:
        return []
    return [
        {
            "type": "text",
            "text": "💬 AI寮母より",
            "weight": "bold",
            "size": "md",
        },
        {
            "type": "text",
            "text": summary,
            "size": "sm",
            "wrap": True,
            "color": "#666666",
        },
    ]


def build_monthly_report_bubble(report: dict[str, Any]) -> dict[str, Any]:
    """Return a single Flex bubble for the parent monthly summary.

    Args:
        report: The report dict assembled by
            ``services/monthly_report.py``. Required keys:
            ``student_display``, ``year_month``, ``posts``,
            ``current_count``, ``prev_count``, ``total_count``, ``usage``,
            ``ai_summary``.
    """
    student_display = report.get("student_display") or "あなたのお子さん"
    year_month = report.get("year_month", "")

    body_contents: list[dict[str, Any]] = []
    body_contents.extend(_posts_section(report))

    body_contents.append({"type": "separator", "color": _SEPARATOR_COLOR})
    body_contents.extend(_usage_section(report))

    ai_contents = _ai_summary_section(report)
    if ai_contents:
        body_contents.append({"type": "separator", "color": _SEPARATOR_COLOR})
        body_contents.extend(ai_contents)

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": HEADER_COLOR,
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": f"📊 {student_display}の今月",
                    "color": "#ffffff",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": year_month,
                    "color": "#ffffff",
                    "size": "xl",
                    "weight": "bold",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": body_contents,
        },
    }
