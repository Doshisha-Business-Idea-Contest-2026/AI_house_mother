"""Flex Message bubble for the monthly parent summary (FR-P3).

A single mega bubble that lists up to ``MAX_POSTS_IN_REPORT`` posts of a
student, each prefixed with a category emoji. Day 3 keeps the layout
lean: no "send a message" button, no external links — Day 4's T4.1a
polishes and adds sender switch differentiation.
"""
from __future__ import annotations

from typing import Any

from src.services.monthly_report import CATEGORY_EMOJI

HEADER_COLOR = "#00579C"
_BODY_PREVIEW_LEN = 60


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


def build_monthly_report_bubble(
    student_display: str,
    year_month: str,
    posts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a single Flex bubble summarising ``posts``.

    Args:
        student_display: How to address the student in the header
            (Day 3 uses ``"あなたのお子さん"`` by default).
        year_month: The report year-month string, e.g. ``"2026-07"``.
        posts: Up to ``MAX_POSTS_IN_REPORT`` post dicts, newest first.
    """
    body_contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": f"✨ 頑張ったこと {len(posts)} 件",
            "weight": "bold",
            "size": "md",
        },
        {"type": "separator", "color": "#e0e0e0"},
    ]
    for index, post in enumerate(posts):
        body_contents.extend(_post_row(post))
        if index < len(posts) - 1:
            body_contents.append(
                {"type": "separator", "color": "#f0f0f0"}
            )

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
            "spacing": "sm",
            "contents": body_contents,
        },
    }
