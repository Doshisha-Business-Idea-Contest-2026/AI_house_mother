"""Text message event handler.

Day 1 scope is intentionally minimal:

- ``ヘルプ`` / ``使い方`` / ``help`` → role-aware help text.
- ``役割変更`` / ``切り替え`` → placeholder until T4.3.
- Anything else → an echo confirming receipt.

Later days will introduce profile, activity suggestion, life
consultation, invitation code, and monthly report flows.
"""
import logging

from linebot.v3.webhooks import MessageEvent, TextMessageContent

from src.config import handler
from src.services import users
from src.services.line_reply import reply_text
from src.templates.flex.welcome import build_welcome_message

logger = logging.getLogger(__name__)

HELP_COMMANDS = {"ヘルプ", "使い方", "help", "Help", "HELP"}
ROLE_SWITCH_COMMANDS = {"役割変更", "切り替え", "きりかえ"}

HELP_UNREGISTERED = (
    "まずは「学生」か「保護者」を選択してください。"
    "「はじめる」と送ると選択画面に戻ります。"
)

HELP_STUDENT = (
    "AI寮母の使い方 🏠\n"
    "🎯 やりたいこと相談 — あなたに合う活動を提案\n"
    "💬 生活相談 — 生活のお困りごとに答える\n"
    "✏️ 経験を投稿 — 参加した活動や利用したお店を記録\n"
    "👤 プロフィール — 情報の確認・更新\n"
    "👨\u200d👩\u200d👧 保護者連携 — 招待コード発行\n"
    "（Day 2 以降で順次実装予定）"
)

HELP_PARENT = (
    "AI寮母の使い方 🏠\n"
    "📊 今月のレポート — お子さんの頑張り確認\n"
    "🔗 学生と連携 — 招待コードで学生と紐付け\n"
    "（Day 3 以降で順次実装予定）"
)

ROLE_SWITCH_PLACEHOLDER = "役割変更機能は準備中です。（Day 4 で実装予定）"

RESTART_COMMANDS = {"はじめる", "始める", "スタート", "/start"}


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event: MessageEvent) -> None:
    """Route text messages to help, role-switch, restart, or echo."""
    text = event.message.text.strip()
    user_id = event.source.user_id
    logger.info("Text from %s: %s", user_id[:8] if user_id else "?", text[:80])

    if text in RESTART_COMMANDS:
        welcome_text, qr = build_welcome_message()
        reply_text(event.reply_token, welcome_text, quick_reply=qr)
        return

    if text in HELP_COMMANDS:
        role = users.get_role(user_id) if user_id else None
        if role is None:
            reply_text(event.reply_token, HELP_UNREGISTERED)
        elif role == "student":
            reply_text(event.reply_token, HELP_STUDENT)
        else:
            reply_text(event.reply_token, HELP_PARENT)
        return

    if text in ROLE_SWITCH_COMMANDS:
        reply_text(event.reply_token, ROLE_SWITCH_PLACEHOLDER)
        return

    reply_text(
        event.reply_token,
        f"受け取りました: {text}\n（詳しい応答は Day 2 以降で実装します）",
    )
