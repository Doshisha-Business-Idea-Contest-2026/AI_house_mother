"""Postback event handler.

Handles quick-reply buttons whose action is ``PostbackAction``.
Day 1 supports:

- ``role:student`` — record the student role and confirm.
- ``role:parent`` — record the parent role and confirm.
"""
import logging

from linebot.v3.webhooks import PostbackEvent

from src.config import handler
from src.services import users
from src.services.line_reply import reply_text

logger = logging.getLogger(__name__)


STUDENT_CONFIRM = (
    "こんにちは、学生さん！🎓\n"
    "まずはプロフィールを教えてもらえると、あなたに合った提案ができます。\n"
    "（プロフィール登録は近日追加します。今日はテスト運用中です）"
)

PARENT_CONFIRM = (
    "こんにちは、保護者の方！👨\u200d👩\u200d👧\n"
    "お子さんから招待コードを受け取っていますか？\n"
    "（コード入力は近日追加します。今日はテスト運用中です）"
)


@handler.add(PostbackEvent)
def handle_postback(event: PostbackEvent) -> None:
    """Route postback data to the appropriate action."""
    user_id = event.source.user_id
    data = event.postback.data
    logger.info("Postback from %s: %s", user_id[:8] if user_id else "?", data)

    if data == "role:student":
        users.save_user(user_id, "student")
        reply_text(event.reply_token, STUDENT_CONFIRM)
        return

    if data == "role:parent":
        users.save_user(user_id, "parent")
        reply_text(event.reply_token, PARENT_CONFIRM)
        return

    logger.warning("Unknown postback data: %s", data)
    reply_text(event.reply_token, "未対応のアクションです。")
