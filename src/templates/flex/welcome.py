"""Welcome message shown right after a user adds the bot.

Currently a simple text + Quick Reply keyboard. The Flex bubble
variant landed as part of the Day 4 T4.1a polish (see the sibling
history in this directory).
"""
from linebot.v3.messaging import (
    MessageAction,
    PostbackAction,
    QuickReply,
    QuickReplyItem,
)

WELCOME_TEXT = (
    "AI寮母へようこそ🏠\n"
    "まずはあなたのことを教えてください。あなたはどちらですか？"
)


def build_welcome_message() -> tuple[str, QuickReply]:
    """Return the welcome text and its Quick Reply keyboard."""
    qr = QuickReply(
        items=[
            QuickReplyItem(
                action=PostbackAction(
                    label="👨‍🎓 学生です",
                    data="role:student",
                    display_text="👨‍🎓 学生です",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="👨‍👩‍👧 保護者です",
                    data="role:parent",
                    display_text="👨‍👩‍👧 保護者です",
                )
            ),
        ]
    )
    return WELCOME_TEXT, qr


def build_role_switch_quick_reply() -> QuickReply:
    """Quick Reply for re-selecting one's role via 「役割変更」 command."""
    return QuickReply(
        items=[
            QuickReplyItem(
                action=MessageAction(label="👨‍🎓 学生に切り替え", text="学生")
            ),
            QuickReplyItem(
                action=MessageAction(label="👨‍👩‍👧 保護者に切り替え", text="保護者")
            ),
            QuickReplyItem(action=MessageAction(label="キャンセル", text="キャンセル")),
        ]
    )
