"""Flex Message carousel builder for activity proposals (FR-S4).

Bubbles follow the shared card-in-card design language in
:mod:`src.templates.flex.style` (T4.13): a category-coloured header, body
details grouped inside a rounded tone card, and a footer with two postback
buttons ("詳しく聞く" / "参加した").
"""

from __future__ import annotations

from typing import Any

from src.templates.flex import style

# Back-compat aliases: the palette now lives in ``style`` (single source of
# truth). These names are preserved for existing imports and tests.
DEFAULT_COLOR = style.NAVY
_CATEGORY_COLORS = style.CATEGORY_COLORS

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
    """Return the header colour used for ``reference_type``.

    Thin wrapper over :func:`style.get_category_color` kept for
    backwards-compatible imports.
    """
    return style.get_category_color(reference_type)


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


def _build_bubble(*, index: int, activity: dict[str, Any], key: str) -> dict[str, Any]:
    reference_type = activity.get("reference_type", "generated")
    color = style.get_category_color(reference_type)
    title = activity.get("title") or f"提案 {index}"
    summary = activity.get("summary") or ""
    location = activity.get("location") or ""
    when = activity.get("when") or ""
    why = activity.get("why_recommend") or ""

    header = style.white_header(title, subtitle=f"🎯 提案 {index}", accent=color)

    body_contents: list[dict[str, Any]] = []

    # NFR-Truth-1 / docs/04_functional_spec.md §4.3: distinguish AI-invented
    # suggestions from seed-backed ones with a small caveat line.
    if reference_type == "generated":
        body_contents.append(
            {
                "type": "text",
                "text": "🧭 AI 提案（要確認）",
                "size": "xs",
                "color": style.TEXT_WEAK,
                "wrap": True,
            }
        )

    body_contents.append(
        {
            "type": "text",
            "text": summary,
            "wrap": True,
            "size": "sm",
            "color": style.TEXT_MAIN,
        }
    )

    # Group the location / when / why details in a tight, fill-less block so
    # they read together while the body whitespace separates them from the
    # summary (airy white style).
    detail_lines: list[dict[str, Any]] = []
    if location:
        detail_lines.append(
            {
                "type": "text",
                "text": f"📍 {location}",
                "size": "sm",
                "color": style.TEXT_SUB,
                "wrap": True,
            }
        )
    if when:
        detail_lines.append(
            {
                "type": "text",
                "text": f"🕒 {when}",
                "size": "sm",
                "color": style.TEXT_SUB,
                "wrap": True,
            }
        )
    if why:
        detail_lines.append(
            {
                "type": "text",
                "text": f"💡 {why}",
                "wrap": True,
                "size": "xs",
                "color": style.TEXT_WEAK,
            }
        )
    if detail_lines:
        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": detail_lines,
            }
        )

    if reference_type in _FRESHNESS_NOTE_TYPES:
        body_contents.append(style.hairline())
        body_contents.append(
            {
                "type": "text",
                "text": _FRESHNESS_NOTE_TEXT,
                "wrap": True,
                "size": "xxs",
                "color": style.TEXT_FAINT,
            }
        )

    footer_contents: list[dict[str, Any]] = [
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
    ]

    return style.bubble(header=header, body=body_contents, footer=footer_contents)


def _build_sponsored_bubble(sponsored: dict[str, Any]) -> dict[str, Any]:
    """Build the gold PR bubble for a sponsored entry (FR-S9).

    Unlike organic proposals this bubble carries a "🏢 PR（協賛）" badge,
    the sponsor's name, a disclosure line, the standard freshness caveat,
    and a URI apply button plus an "興味あり" postback for click tracking.
    Text is rendered verbatim from the seed (docs/04 §4.3).
    """
    color = style.CATEGORY_COLORS["sponsored"]
    sponsor_id = sponsored.get("sponsor_id") or ""
    company = sponsored.get("company_name") or ""
    title = sponsored.get("title") or "協賛イベント"
    summary = sponsored.get("summary") or ""
    apply_url = sponsored.get("apply_url") or ""
    event_date = sponsored.get("event_date") or ""
    deadline = sponsored.get("deadline") or ""

    # The gold PR distinction (FR-S9) now lives in the header accent bar; the
    # badge and company name sit as muted subtitle lines above the title.
    subtitle = [_SPONSORED_BADGE_TEXT, company] if company else [_SPONSORED_BADGE_TEXT]
    header = style.white_header(title, subtitle=subtitle, accent=color)

    body_contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": summary,
            "wrap": True,
            "size": "sm",
            "color": style.TEXT_MAIN,
        }
    ]

    info_lines: list[dict[str, Any]] = []
    if event_date:
        info_lines.append(
            {
                "type": "text",
                "text": f"📅 開催: {event_date}",
                "size": "sm",
                "color": style.TEXT_SUB,
                "wrap": True,
            }
        )
    if deadline:
        info_lines.append(
            {
                "type": "text",
                "text": f"⏳ 締切: {deadline}",
                "size": "sm",
                "color": style.TEXT_SUB,
                "wrap": True,
            }
        )
    if info_lines:
        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": info_lines,
            }
        )

    # Disclosure + freshness caveat live at the body tail (FR-S9): the
    # disclosure stays legible while the generic freshness note is faint.
    body_contents.append(style.hairline())
    body_contents.append(
        {
            "type": "text",
            "text": _SPONSORED_DISCLOSURE_TEXT,
            "wrap": True,
            "size": "xs",
            "color": style.TEXT_WEAK,
        }
    )
    body_contents.append(
        {
            "type": "text",
            "text": _FRESHNESS_NOTE_TEXT,
            "wrap": True,
            "size": "xxs",
            "color": style.TEXT_FAINT,
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

    return style.bubble(header=header, body=body_contents, footer=footer_contents)
