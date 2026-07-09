"""Welcome message shown right after a user adds the bot.

Renders a Flex bubble (`build_welcome_message`) that introduces the
service and drives the user to the role-selection Quick Reply
attached to the same message. Callers that need to prefix a system
message (e.g. cancel, session timeout, wrong-role fallback) pass
``prefix`` and the bubble prepends it above the main body.
"""

from linebot.v3.messaging import (
    PostbackAction,
    QuickReply,
    QuickReplyItem,
)

from src.templates.flex import style

HEADER_COLOR = style.NAVY

WELCOME_ALT_TEXT = (
    "AI寮母へようこそ🏠 学生か保護者を選んでオンボーディングを始めましょう。"
)

_BODY_LEAD_TEXT = (
    "京都・同志社周辺の学生さんと保護者の方をつなぐ AI 寮母です。"
    "まずはあなたのことを教えてください。"
)

_FEATURE_LINES: list[tuple[str, str]] = [
    ("🎯", "やりたいこと相談で自分に合う活動を提案"),
    ("💬", "生活相談で先輩の知恵と地域情報にアクセス"),
    ("👨\u200d👩\u200d👧", "保護者連携で頑張ったことを届ける"),
]


def _feature_row(emoji: str, text: str) -> dict:
    return {
        "type": "box",
        "layout": "baseline",
        "spacing": "sm",
        "contents": [
            {"type": "text", "text": emoji, "flex": 0, "size": "md"},
            {
                "type": "text",
                "text": text,
                "wrap": True,
                "size": "sm",
                "flex": 5,
                "color": style.TEXT_MAIN,
            },
        ],
    }


def build_welcome_bubble(prefix: str | None = None) -> dict:
    """Return the welcome Flex bubble dict.

    Args:
        prefix: Optional short system message displayed at the very top
            of the body. Used by session-timeout, cancel, wrong-role
            and unknown-command fallbacks to explain why the welcome
            bubble was surfaced again.
    """
    body_contents: list[dict] = []

    if prefix:
        body_contents.append(
            {
                "type": "text",
                "text": prefix,
                "wrap": True,
                "size": "sm",
                "color": style.TEXT_SUB,
            }
        )

    body_contents.append(
        {
            "type": "text",
            "text": _BODY_LEAD_TEXT,
            "wrap": True,
            "size": "sm",
            "color": style.TEXT_MAIN,
        }
    )
    # Group the three feature highlights in a tight, fill-less block, set off
    # from the lead/guidance by body whitespace and a hairline.
    feature_rows = [_feature_row(emoji, text) for emoji, text in _FEATURE_LINES]
    body_contents.append(
        {"type": "box", "layout": "vertical", "spacing": "sm", "contents": feature_rows}
    )
    body_contents.append(style.hairline())
    body_contents.append(
        {
            "type": "text",
            "text": "下のメニューから当てはまるほうを選んでください。",
            "wrap": True,
            "size": "sm",
            "color": style.TEXT_SUB,
        }
    )

    header = style.white_header("\U0001f3e0 AI寮母へようこそ")
    return style.bubble(header=header, body=body_contents)


def build_role_quick_reply() -> QuickReply:
    """Return the role-selection Quick Reply used with the welcome bubble."""
    return QuickReply(
        items=[
            QuickReplyItem(
                action=PostbackAction(
                    label="\U0001f468\u200d\U0001f393 学生です",
                    data="role:student",
                    display_text="\U0001f468\u200d\U0001f393 学生です",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="\U0001f468\u200d\U0001f469\u200d\U0001f467 保護者です",
                    data="role:parent",
                    display_text="\U0001f468\u200d\U0001f469\u200d\U0001f467 保護者です",
                )
            ),
        ]
    )


def build_welcome_message(
    prefix: str | None = None,
) -> tuple[str, dict, QuickReply]:
    """Return ``(alt_text, flex_contents, quick_reply)`` for the welcome bubble.

    Every caller in the handlers uses this triple to render the Flex
    version of the welcome message (see docs/04 §2.2 and T4.1a).
    """
    alt_text = WELCOME_ALT_TEXT if prefix is None else f"{prefix}\n{WELCOME_ALT_TEXT}"
    return alt_text, build_welcome_bubble(prefix=prefix), build_role_quick_reply()


def build_role_switch_quick_reply() -> QuickReply:
    """Legacy role-switch Quick Reply. Kept for the reserved-word command.

    The 「役割変更」 command is currently marked as unsupported in
    handlers/message.py, but the builder is preserved so we can flip
    the switch back on quickly if a demo tester needs it.
    """
    from linebot.v3.messaging import MessageAction

    return QuickReply(
        items=[
            QuickReplyItem(
                action=MessageAction(
                    label="\U0001f468\u200d\U0001f393 学生に切り替え", text="学生"
                )
            ),
            QuickReplyItem(
                action=MessageAction(
                    label="\U0001f468\u200d\U0001f469\u200d\U0001f467 保護者に切り替え",
                    text="保護者",
                )
            ),
            QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル")),
        ]
    )
