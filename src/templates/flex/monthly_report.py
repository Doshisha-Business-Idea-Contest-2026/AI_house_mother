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

from src.templates.flex import style

HEADER_COLOR = style.NAVY
_BODY_PREVIEW_LEN = 60
_SEPARATOR_COLOR = style.SEPARATOR

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
            "color": style.TEXT_MAIN,
        },
        {
            "type": "text",
            "text": body_preview,
            "size": "sm",
            "wrap": True,
            "color": style.TEXT_SUB,
        },
    ]


def _posts_section(report: dict[str, Any]) -> list[dict[str, Any]]:
    posts = report.get("posts") or []
    current_count = int(report.get("current_count", len(posts)))
    prev_count = int(report.get("prev_count", 0))
    total_count = int(report.get("total_count", current_count))

    subtitle = f"（先月 {prev_count} / 通算 {total_count}）"

    block: list[dict[str, Any]] = [
        style.section_heading(f"🌸 頑張ったこと {current_count} 件"),
        {"type": "text", "text": subtitle, "size": "xs", "color": style.TEXT_WEAK},
    ]
    if posts:
        post_rows: list[dict[str, Any]] = []
        for index, post in enumerate(posts):
            post_rows.extend(_post_row(post))
            if index < len(posts) - 1:
                post_rows.append(style.hairline())
        block.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": post_rows,
            }
        )
    return block


def _usage_section(report: dict[str, Any]) -> list[dict[str, Any]]:
    usage = report.get("usage") or {}
    life = int(usage.get("life", 0))
    activity = int(usage.get("activity", 0))
    post_count = int(usage.get("post", 0))
    profile_count = int(usage.get("profile", 0))
    consult_total = life + activity
    record_total = post_count + profile_count

    lines: list[dict[str, Any]] = []

    # docs/04 §5.3 少回数フォールバック: below the threshold we drop the
    # numeric line and use a qualitative sentence. Zero everything → a
    # different (softer) sentence so parents don't see a bare number.
    if consult_total >= _LOW_CONSULT_THRESHOLD:
        lines.append(
            {
                "type": "text",
                "text": f"相談 {consult_total}回（生活 {life} / 活動 {activity}）",
                "size": "sm",
                "wrap": True,
                "color": style.TEXT_MAIN,
            }
        )
    elif consult_total > 0:
        lines.append(
            {
                "type": "text",
                "text": _LOW_CONSULT_TEXT,
                "size": "sm",
                "wrap": True,
                "color": style.TEXT_MAIN,
            }
        )

    if record_total > 0:
        lines.append(
            {
                "type": "text",
                "text": (
                    f"記録・更新 {record_total}回"
                    f"（投稿 {post_count} / プロフィール {profile_count}）"
                ),
                "size": "sm",
                "wrap": True,
                "color": style.TEXT_MAIN,
            }
        )

    # If both blocks stayed empty (no consultations, no records) we still
    # want a sentence here rather than a lone header.
    if not lines:
        lines.append(
            {
                "type": "text",
                "text": _NO_ACTIVITY_TEXT,
                "size": "sm",
                "wrap": True,
                "color": style.TEXT_MAIN,
            }
        )
    return [
        style.section_heading("🏠 今月の利用"),
        {"type": "box", "layout": "vertical", "spacing": "sm", "contents": lines},
    ]


def _ai_summary_section(report: dict[str, Any]) -> list[dict[str, Any]]:
    summary = (report.get("ai_summary") or "").strip()
    if not summary:
        return []
    return [
        style.section_heading("💬 AI寮母より"),
        {
            "type": "text",
            "text": summary,
            "size": "sm",
            "wrap": True,
            "color": style.TEXT_SUB,
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
    body_contents.append(style.hairline())
    body_contents.extend(_usage_section(report))

    ai_contents = _ai_summary_section(report)
    if ai_contents:
        body_contents.append(style.hairline())
        body_contents.extend(ai_contents)

    header = style.white_header(year_month, subtitle=f"📊 {student_display}の今月")
    return style.bubble(header=header, body=body_contents)
