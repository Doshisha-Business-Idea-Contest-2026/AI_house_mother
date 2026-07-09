"""Flex Message bubble for the student profile-view screen (FR-S2).

Shows the student's stored profile fields in a mega bubble that matches
the existing ``activity_carousel`` / ``invitation_code`` / ``monthly_report``
style (Doshisha navy header, medium-spaced body sections, palette
``#e0e0e0`` separators). No footer buttons: the accompanying Quick Reply
carries the ``✏️ 編集する`` / ``🏠 メインメニュー`` actions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.templates.flex import style

JST = ZoneInfo("Asia/Tokyo")

HEADER_COLOR = style.NAVY

_GRADE_LABELS: dict[str, str] = {
    "1": "1 年",
    "2": "2 年",
    "3": "3 年",
    "4": "4 年",
    "M1": "院 1",
    "M2": "院 2",
}


def _format_updated_at(iso_ts: str) -> str:
    """Return ``YYYY-MM-DD HH:MM`` in JST or the original on failure."""
    try:
        return datetime.fromisoformat(iso_ts).astimezone(JST).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_ts


def _field_row(label: str, value: str) -> dict[str, Any]:
    """Return a stacked label/value pair.

    Thin wrapper over :func:`style.label_value` kept for call-site clarity.
    """
    return style.label_value(label, value)


def build_profile_view_bubble(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a single Flex bubble summarising ``profile``.

    Args:
        profile: Profile dict as stored in ``data/profiles.json``.
            Missing optional fields are rendered as ``"—"`` so the
            layout does not collapse.
    """
    university = profile.get("university") or "—"
    faculty = profile.get("faculty") or "—"
    grade_raw = str(profile.get("grade") or "")
    grade = _GRADE_LABELS.get(grade_raw, grade_raw or "—")
    interests_list = profile.get("interests") or []
    interests = "、".join(interests_list) if interests_list else "—"
    recent_effort = profile.get("recent_effort") or "—"
    want_to_do = profile.get("want_to_do") or "—"
    updated_at = _format_updated_at(profile.get("updated_at", ""))

    fields: list[tuple[str, str]] = [
        ("🏫 大学", university),
        ("📚 学部", faculty),
        ("🎓 学年", grade),
        ("💫 興味のあること", interests),
        ("🔥 最近頑張っていること", recent_effort),
        ("🎯 やってみたいこと", want_to_do),
    ]
    card_contents: list[dict[str, Any]] = []
    for index, (label, value) in enumerate(fields):
        card_contents.append(_field_row(label, value))
        if index < len(fields) - 1:
            card_contents.append(style.separator())

    body_contents: list[dict[str, Any]] = [style.card(card_contents)]

    if updated_at:
        body_contents.append(
            {
                "type": "text",
                "text": f"⏰ 最終更新: {updated_at}",
                "size": "xs",
                "color": style.TEXT_WEAK,
            }
        )

    header = style.header_box(
        HEADER_COLOR,
        [
            {
                "type": "text",
                "text": "👤 あなたのプロフィール",
                "color": style.WHITE,
                "size": "sm",
            },
            {
                "type": "text",
                "text": "登録済みの内容はこちらです",
                "color": style.WHITE,
                "size": "xl",
                "weight": "bold",
                "wrap": True,
            },
        ],
    )
    return style.bubble(header=header, body=body_contents)
