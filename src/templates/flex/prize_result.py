"""Flex Message builder for prize lottery results (FR-S11).

Dedicated celebratory layout for a ranked draw (docs/04 §4.9). Does NOT use
the shared left-accent-bar skeleton; a win gets its own centred composition:
a soft champagne banner, a gold rank badge (signature element), an oversized
prize glyph, the prize name, and a ticket-style detail card (draw number +
dummy expiry). White + champagne gold palette. A small "デモ演出" note keeps
it from being mistaken for a real prize (docs/05 §4.17).
"""

from __future__ import annotations

from typing import Any

_GOLD = "#D4AF37"
_GOLD_SOFT = "#FBF6E9"
_GOLD_DEEP = "#A8842A"
_GOLD_LINE = "#EFE6CC"
_INK = "#2B2B2B"
_MUTE = "#8A8A8A"
_FAINT = "#B8B8B8"
_WHITE = "#ffffff"
_CARD = "#F7F5F0"

_MISS_SOFT = "#EFF1F3"
_MISS_INK = "#5A6570"
_MISS_LINE = "#E8EAED"

_DEMO_NOTE = "※デモ演出です"


def build_prize_result_bubble(result: dict[str, Any]) -> dict[str, Any]:
    """Return a Flex bubble for a draw result."""
    if result.get("result") == "win":
        return _build_win_bubble(
            int(result.get("rank") or 0),
            result.get("prize") or {},
            int(result.get("seed") or 0),
        )
    return _build_lose_bubble()


def _banner(text: str, ground: str, color: str) -> dict[str, Any]:
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": ground,
        "cornerRadius": "12px",
        "paddingAll": "12px",
        "contents": [
            {
                "type": "text",
                "text": text,
                "align": "center",
                "weight": "bold",
                "size": "md",
                "color": color,
            }
        ],
    }


def _rank_badge(rank: int) -> dict[str, Any]:
    return {
        "type": "box",
        "layout": "horizontal",
        "margin": "lg",
        "contents": [
            {"type": "filler"},
            {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": _GOLD,
                "cornerRadius": "20px",
                "paddingTop": "6px",
                "paddingBottom": "6px",
                "paddingStart": "22px",
                "paddingEnd": "22px",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{rank} 等",
                        "color": _WHITE,
                        "weight": "bold",
                        "size": "lg",
                        "align": "center",
                    }
                ],
            },
            {"type": "filler"},
        ],
    }


def _info_row(label: str, value: str) -> dict[str, Any]:
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {"type": "text", "text": label, "size": "sm", "color": _MUTE, "flex": 0},
            {
                "type": "text",
                "text": value,
                "size": "sm",
                "color": _INK,
                "weight": "bold",
                "align": "end",
                "wrap": True,
            },
        ],
    }


def _info_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    contents: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if index > 0:
            contents.append({"type": "separator", "color": _GOLD_LINE, "margin": "md"})
            row = {**row, "margin": "md"}
        contents.append(row)
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": _CARD,
        "cornerRadius": "10px",
        "paddingAll": "14px",
        "margin": "lg",
        "contents": contents,
    }


def _shell(body_contents: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": _WHITE,
            "paddingAll": "20px",
            "contents": body_contents,
        },
    }


def _build_win_bubble(rank: int, prize: dict[str, Any], seed: int) -> dict[str, Any]:
    emoji = prize.get("emoji") or "🎁"
    name = prize.get("name") or "プレゼント"
    description = prize.get("description") or ""
    valid_until = prize.get("valid_until") or ""
    note = prize.get("note") or ""

    contents: list[dict[str, Any]] = [
        _banner("✦ ご当選 ✦", _GOLD_SOFT, _GOLD_DEEP),
        _rank_badge(rank),
        {
            "type": "text",
            "text": emoji,
            "size": "5xl",
            "align": "center",
            "margin": "lg",
        },
        {
            "type": "text",
            "text": name,
            "size": "xl",
            "weight": "bold",
            "align": "center",
            "wrap": True,
            "color": _INK,
            "margin": "md",
        },
    ]
    if description:
        contents.append(
            {
                "type": "text",
                "text": description,
                "size": "sm",
                "align": "center",
                "wrap": True,
                "color": _MUTE,
                "margin": "sm",
            }
        )

    rows = [_info_row("当選番号", f"NO. {seed:07d}")]
    if valid_until:
        rows.append(_info_row("有効期限", f"{valid_until} まで"))
    contents.append(_info_card(rows))

    if note:
        contents.append(
            {
                "type": "text",
                "text": note,
                "size": "xs",
                "align": "center",
                "wrap": True,
                "color": _MUTE,
                "margin": "md",
            }
        )
    contents.append({"type": "separator", "color": _GOLD_LINE, "margin": "lg"})
    contents.append(
        {
            "type": "text",
            "text": _DEMO_NOTE,
            "size": "xxs",
            "align": "center",
            "color": _FAINT,
            "margin": "sm",
        }
    )
    return _shell(contents)


def _build_lose_bubble() -> dict[str, Any]:
    contents: list[dict[str, Any]] = [
        _banner("またの機会に", _MISS_SOFT, _MISS_INK),
        {
            "type": "text",
            "text": "🍀",
            "size": "5xl",
            "align": "center",
            "margin": "lg",
        },
        {
            "type": "text",
            "text": "はずれ",
            "size": "lg",
            "weight": "bold",
            "align": "center",
            "color": _MISS_INK,
            "margin": "md",
        },
        {
            "type": "text",
            "text": "また投稿してチャレンジしよう！",
            "size": "sm",
            "align": "center",
            "wrap": True,
            "color": _MUTE,
            "margin": "sm",
        },
        {"type": "separator", "color": _MISS_LINE, "margin": "lg"},
        {
            "type": "text",
            "text": _DEMO_NOTE,
            "size": "xxs",
            "align": "center",
            "color": _FAINT,
            "margin": "sm",
        },
    ]
    return _shell(contents)
