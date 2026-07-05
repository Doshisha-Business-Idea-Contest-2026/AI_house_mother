"""Flex Message carousel builder for activity proposals (FR-S4).

The bubble structure is inspired by ``kcb_linebot/flex_templates.py``:
size mega, colour-coded header, section-separated body, and a footer
with two postback buttons ("詳しく聞く" / "参加した").
"""
from __future__ import annotations

from typing import Any


DEFAULT_COLOR = "#00579C"  # Doshisha-ish navy blue

_CATEGORY_COLORS: dict[str, str] = {
    "event": "#0080FF",  # bright blue
    "volunteer": "#4CAF50",  # green
    "workshop": "#9C27B0",  # purple
    "festival": "#E91E63",  # pink
    "study_group": "#3F51B5",  # indigo
    "store": "#FF9800",  # orange
    "senior_post": "#607D8B",  # slate
    "generated": DEFAULT_COLOR,
    "static_fallback": "#795548",  # brown
}

MAX_BUBBLES = 3


def get_activity_header_color(reference_type: str) -> str:
    """Return the header colour used for ``reference_type``."""
    return _CATEGORY_COLORS.get(reference_type, DEFAULT_COLOR)


def build_activity_carousel(
    activities: list[dict[str, Any]], keys: list[str]
) -> dict[str, Any]:
    """Return a Flex carousel JSON containing up to three activity bubbles.

    Args:
        activities: The list of proposal dicts. Extra items beyond
            :data:`MAX_BUBBLES` are dropped.
        keys: A parallel list of short hash keys used to identify each
            activity in postback data. Must be the same length as
            ``activities``.
    """
    if len(activities) != len(keys):
        raise ValueError("activities and keys must have the same length")

    bubbles = [
        _build_bubble(index=i + 1, activity=activities[i], key=keys[i])
        for i in range(min(len(activities), MAX_BUBBLES))
    ]

    if len(bubbles) == 1:
        return bubbles[0]

    return {
        "type": "carousel",
        "contents": bubbles,
    }


def _build_bubble(
    *, index: int, activity: dict[str, Any], key: str
) -> dict[str, Any]:
    color = get_activity_header_color(activity.get("reference_type", "generated"))
    title = activity.get("title") or f"提案 {index}"
    summary = activity.get("summary") or ""
    location = activity.get("location") or ""
    when = activity.get("when") or ""
    why = activity.get("why_recommend") or ""

    body_contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": summary,
            "wrap": True,
            "size": "sm",
        }
    ]

    if location or when:
        info_lines: list[dict[str, Any]] = []
        if location:
            info_lines.append(
                {
                    "type": "text",
                    "text": f"📍 {location}",
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True,
                }
            )
        if when:
            info_lines.append(
                {
                    "type": "text",
                    "text": f"🕒 {when}",
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True,
                }
            )
        body_contents.append({"type": "separator", "color": "#e0e0e0"})
        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "contents": info_lines,
            }
        )

    if why:
        body_contents.append({"type": "separator", "color": "#e0e0e0"})
        body_contents.append(
            {
                "type": "text",
                "text": f"💡 {why}",
                "wrap": True,
                "size": "xs",
                "color": "#999999",
            }
        )

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": color,
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": f"🎯 提案 {index}",
                    "color": "#ffffff",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": title,
                    "color": "#ffffff",
                    "size": "xl",
                    "weight": "bold",
                    "wrap": True,
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": color,
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "詳しく聞く",
                        "data": f"activity:detail:{key}",
                        "displayText": f"「{title}」について詳しく聞く",
                    },
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "参加した",
                        "data": f"activity:participated:{key}",
                        "displayText": f"「{title}」に参加した",
                    },
                },
            ],
        },
    }
