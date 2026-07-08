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
    "sponsored": "#C9A227",  # gold — corporate PR slot (FR-S9)
}

MAX_BUBBLES = 3

# NFR-Truth-4 / docs/04_functional_spec.md §4.4: seed の実在情報を含む
# 提案（store / event / volunteer）は、時点情報が古くなる前提で汎用注記を
# 必ず bubble 末尾に添える。個別の data_freshness_note は Phase 3 では
# 引き当てず、一律の警句のみ表示する。
_FRESHNESS_NOTE_TYPES: frozenset[str] = frozenset({"store", "event", "volunteer"})
_FRESHNESS_NOTE_TEXT = "※情報は変わっている可能性があります"

# NFR-Truth / docs/04_functional_spec.md §4.3: sponsored PR は通常提案と
# 一目で区別できるようゴールドヘッダー＋バッジ＋開示文を必ず添える。
_SPONSORED_BADGE_TEXT = "🏢 PR（協賛）"
_SPONSORED_DISCLOSURE_TEXT = "この案内は協賛企業からの提供です"


def get_activity_header_color(reference_type: str) -> str:
    """Return the header colour used for ``reference_type``."""
    return _CATEGORY_COLORS.get(reference_type, DEFAULT_COLOR)


def build_activity_carousel(
    activities: list[dict[str, Any]],
    keys: list[str],
    sponsored: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a Flex carousel JSON containing up to three activity bubbles.

    Args:
        activities: The list of proposal dicts. Extra items beyond
            :data:`MAX_BUBBLES` are dropped.
        keys: A parallel list of short hash keys used to identify each
            activity in postback data. Must be the same length as
            ``activities``.
        sponsored: An optional sponsored PR entry (FR-S9). When present it
            is prepended as a distinct gold bubble ahead of the organic
            proposals, so the carousel holds up to ``MAX_BUBBLES + 1``
            bubbles. See ``docs/04_functional_spec.md §4.3``.
    """
    if len(activities) != len(keys):
        raise ValueError("activities and keys must have the same length")

    bubbles = [
        _build_bubble(index=i + 1, activity=activities[i], key=keys[i])
        for i in range(min(len(activities), MAX_BUBBLES))
    ]

    if sponsored is not None:
        bubbles.insert(0, _build_sponsored_bubble(sponsored))

    if len(bubbles) == 1:
        return bubbles[0]

    return {
        "type": "carousel",
        "contents": bubbles,
    }


def _build_bubble(
    *, index: int, activity: dict[str, Any], key: str
) -> dict[str, Any]:
    reference_type = activity.get("reference_type", "generated")
    color = get_activity_header_color(reference_type)
    title = activity.get("title") or f"提案 {index}"
    summary = activity.get("summary") or ""
    location = activity.get("location") or ""
    when = activity.get("when") or ""
    why = activity.get("why_recommend") or ""

    # NFR-Truth-1 / docs/04_functional_spec.md §4.3: distinguish AI-invented
    # suggestions from seed-backed ones with a small caveat line.
    header_contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": f"🎯 提案 {index}",
            "color": "#ffffff",
            "size": "sm",
        },
    ]
    if reference_type == "generated":
        header_contents.append(
            {
                "type": "text",
                "text": "🧭 AI 提案（要確認）",
                "color": "#ffffff",
                "size": "sm",
                "wrap": True,
            }
        )
    header_contents.append(
        {
            "type": "text",
            "text": title,
            "color": "#ffffff",
            "size": "xl",
            "weight": "bold",
            "wrap": True,
        }
    )

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

    if reference_type in _FRESHNESS_NOTE_TYPES:
        body_contents.append({"type": "separator", "color": "#e0e0e0"})
        body_contents.append(
            {
                "type": "text",
                "text": _FRESHNESS_NOTE_TEXT,
                "wrap": True,
                "size": "xxs",
                "color": "#aaaaaa",
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
            "contents": header_contents,
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


def _build_sponsored_bubble(sponsored: dict[str, Any]) -> dict[str, Any]:
    """Build the gold PR bubble for a sponsored entry (FR-S9).

    Unlike organic proposals this bubble carries a "🏢 PR（協賛）" badge,
    the sponsor's name, a disclosure line, the standard freshness caveat,
    and a URI apply button plus an "興味あり" postback for click tracking.
    Text is rendered verbatim from the seed (docs/04 §4.3).
    """
    color = _CATEGORY_COLORS["sponsored"]
    sponsor_id = sponsored.get("sponsor_id") or ""
    company = sponsored.get("company_name") or ""
    title = sponsored.get("title") or "協賛イベント"
    summary = sponsored.get("summary") or ""
    apply_url = sponsored.get("apply_url") or ""
    event_date = sponsored.get("event_date") or ""
    deadline = sponsored.get("deadline") or ""

    header_contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": _SPONSORED_BADGE_TEXT,
            "color": "#ffffff",
            "size": "sm",
            "weight": "bold",
        },
    ]
    if company:
        header_contents.append(
            {
                "type": "text",
                "text": company,
                "color": "#ffffff",
                "size": "xs",
                "wrap": True,
            }
        )
    header_contents.append(
        {
            "type": "text",
            "text": title,
            "color": "#ffffff",
            "size": "xl",
            "weight": "bold",
            "wrap": True,
        }
    )

    body_contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": summary,
            "wrap": True,
            "size": "sm",
        }
    ]

    info_lines: list[dict[str, Any]] = []
    if event_date:
        info_lines.append(
            {
                "type": "text",
                "text": f"📅 開催: {event_date}",
                "size": "sm",
                "color": "#666666",
                "wrap": True,
            }
        )
    if deadline:
        info_lines.append(
            {
                "type": "text",
                "text": f"⏳ 締切: {deadline}",
                "size": "sm",
                "color": "#666666",
                "wrap": True,
            }
        )
    if info_lines:
        body_contents.append({"type": "separator", "color": "#e0e0e0"})
        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "contents": info_lines,
            }
        )

    body_contents.append({"type": "separator", "color": "#e0e0e0"})
    body_contents.append(
        {
            "type": "text",
            "text": _SPONSORED_DISCLOSURE_TEXT,
            "wrap": True,
            "size": "xs",
            "color": "#999999",
        }
    )
    body_contents.append(
        {
            "type": "text",
            "text": _FRESHNESS_NOTE_TEXT,
            "wrap": True,
            "size": "xxs",
            "color": "#aaaaaa",
        }
    )

    footer_contents: list[dict[str, Any]] = []
    if apply_url:
        footer_contents.append(
            {
                "type": "button",
                "style": "primary",
                "color": color,
                "height": "sm",
                "action": {
                    "type": "uri",
                    "label": "詳細・応募はこちら",
                    "uri": apply_url,
                },
            }
        )
    footer_contents.append(
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "興味あり",
                "data": f"sponsored:interest:{sponsor_id}",
                "displayText": f"「{title}」に興味あり",
            },
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
            "contents": header_contents,
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
            "contents": footer_contents,
        },
    }
