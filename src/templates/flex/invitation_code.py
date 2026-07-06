"""Flex Message bubble for invitation code delivery (FR-S7).

The bubble presents the freshly issued 6-character code in a large,
copy-friendly typography together with the expiry time and a short
one-liner the student can forward to their parent. Two postback buttons
in the footer let the student re-issue the code or return to the main
menu.

Spec: ``docs/04_functional_spec.md`` §4.6 and ``docs/05_data_model.md``
§4.4.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

HEADER_COLOR = "#00579C"  # match activity_carousel DEFAULT_COLOR
CODE_TEXT_COLOR = "#00579C"


def _format_expiry(expires_at_iso: str) -> str:
    """Return ``YYYY-MM-DD HH:MM`` in JST for the expiry line."""
    try:
        dt = datetime.fromisoformat(expires_at_iso).astimezone(JST)
    except ValueError:
        return expires_at_iso
    return dt.strftime("%Y-%m-%d %H:%M")


def build_invitation_bubble(code: str, expires_at_iso: str) -> dict[str, Any]:
    """Return a single Flex bubble showing the invitation ``code``.

    Args:
        code: The 6-character invitation code.
        expires_at_iso: ISO 8601 timestamp with timezone (returned by
            ``invitations.issue_code``). Rendered in JST.
    """
    expiry = _format_expiry(expires_at_iso)
    share_line = f"AI寮母を友だち追加して、このコードを入力してね: [{code}]"

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
                    "text": "🔑 保護者連携コード",
                    "color": "#ffffff",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": "保護者に共有してね",
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
            "contents": [
                {
                    "type": "text",
                    "text": code,
                    "color": CODE_TEXT_COLOR,
                    "size": "4xl",
                    "weight": "bold",
                    "align": "center",
                },
                {"type": "separator", "color": "#e0e0e0"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "xs",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"⏰ 有効期限: {expiry}",
                            "size": "sm",
                            "color": "#666666",
                            "wrap": True,
                        },
                        {
                            "type": "text",
                            "text": "1 回限り有効",
                            "size": "xs",
                            "color": "#999999",
                        },
                    ],
                },
                {"type": "separator", "color": "#e0e0e0"},
                {
                    "type": "text",
                    "text": "共有用メッセージ:",
                    "size": "xs",
                    "color": "#999999",
                },
                {
                    "type": "text",
                    "text": share_line,
                    "size": "sm",
                    "wrap": True,
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": HEADER_COLOR,
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "↺ 新しいコードを発行",
                        "data": "invite:regenerate",
                        "displayText": "新しいコードを発行",
                    },
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "🏠 メインメニュー",
                        "data": "menu:main",
                        "displayText": "メインメニュー",
                    },
                },
            ],
        },
    }
