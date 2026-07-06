"""Postback event handler.

Handles all ``PostbackAction`` data payloads coming from Quick Reply and
Flex Message buttons. The prefix before the first ``:`` identifies which
sub-handler owns the action.

Prefixes supported so far:

- ``role:{student|parent}`` — initial role selection (Day 1)
- ``menu:*``                  — main menu / navigation (Day 2)
- ``profile:*``               — profile registration flow (Day 2)
"""
import logging

from linebot.v3.webhooks import PostbackEvent

from src.config import handler
from src.handlers import student
from src.services import users
from src.services.line_reply import reply_text
from src.templates.flex.welcome import build_welcome_message
from src.templates.quick_reply import (
    main_menu_quick_reply,
    profile_start_quick_reply,
)

logger = logging.getLogger(__name__)


STUDENT_CONFIRM = (
    "こんにちは、学生さん！🎓\n"
    "まずはプロフィールを教えてもらえると、あなたに合った提案ができます。"
)

PARENT_CONFIRM = (
    "こんにちは、保護者の方！👨\u200d👩\u200d👧\n"
    "お子さんから招待コードを受け取っていますか？（コード入力機能は Day 3 で実装予定）"
)


@handler.add(PostbackEvent)
def handle_postback(event: PostbackEvent) -> None:
    """Route postback data to the appropriate sub-handler by prefix."""
    user_id = event.source.user_id
    data = event.postback.data
    logger.info("Postback from %s: %s", user_id[:8] if user_id else "?", data)

    if data == "role:student":
        users.save_user(user_id, "student")
        reply_text(
            event.reply_token,
            STUDENT_CONFIRM,
            quick_reply=profile_start_quick_reply(),
        )
        return

    if data == "role:parent":
        users.save_user(user_id, "parent")
        reply_text(
            event.reply_token,
            PARENT_CONFIRM,
            quick_reply=main_menu_quick_reply("parent"),
        )
        return

    if data.startswith("menu:"):
        _handle_menu(event, data)
        return

    if data.startswith("profile:"):
        # Guard: user must be a student.
        role = users.get_role(user_id)
        if role != "student":
            _reply_placeholder(event, role, "この操作は学生アカウント向けです。")
            return
        student.handle_profile_postback(event, data)
        return

    if data.startswith("activity:"):
        role = users.get_role(user_id)
        if role != "student":
            _reply_placeholder(event, role, "この操作は学生アカウント向けです。")
            return
        _handle_activity(event, data)
        return

    if data.startswith("invite:"):
        role = users.get_role(user_id)
        if role != "student":
            _reply_placeholder(event, role, "この操作は学生アカウント向けです。")
            return
        _handle_invite(event, data)
        return

    logger.warning("Unknown postback data: %s", data)
    _reply_placeholder(event, users.get_role(user_id), "未対応のアクションです。")


def _handle_invite(event: PostbackEvent, data: str) -> None:
    if data == "invite:regenerate":
        student.start_invitation_flow(event)
        return

    logger.warning("Unknown invite postback: %s", data)
    _reply_placeholder(
        event, users.get_role(event.source.user_id), "未対応の操作です。"
    )


def _handle_activity(event: PostbackEvent, data: str) -> None:
    if data.startswith("activity:detail:"):
        key = data.removeprefix("activity:detail:")
        student.handle_activity_detail(event, key)
        return

    if data.startswith("activity:participated:"):
        key = data.removeprefix("activity:participated:")
        student.handle_activity_participated(event, key)
        return

    logger.warning("Unknown activity postback: %s", data)
    _reply_placeholder(
        event, users.get_role(event.source.user_id), "未対応の操作です。"
    )


# ---------------------------------------------------------------------------
# menu handlers
# ---------------------------------------------------------------------------


def _handle_menu(event: PostbackEvent, data: str) -> None:
    user_id = event.source.user_id
    action = data.removeprefix("menu:")
    role = users.get_role(user_id)

    if action == "profile_start":
        if role != "student":
            welcome_text, qr = build_welcome_message()
            reply_text(event.reply_token, welcome_text, quick_reply=qr)
            return
        student.start_profile_flow(event)
        return

    if action == "profile":
        # Placeholder until profile view/edit is designed; for now, restart flow.
        if role != "student":
            reply_text(event.reply_token, "この機能は学生アカウント向けです。")
            return
        student.start_profile_flow(event)
        return

    if action == "want_to_do":
        if role != "student":
            welcome_text, qr = build_welcome_message()
            reply_text(event.reply_token, welcome_text, quick_reply=qr)
            return
        student.handle_want_to_do(event)
        return

    if action == "life":
        if role != "student":
            welcome_text, qr = build_welcome_message()
            reply_text(event.reply_token, welcome_text, quick_reply=qr)
            return
        student.start_life_consultation(event)
        return

    if action == "post":
        _reply_placeholder(
            event, role, "✏️ 経験投稿機能は Day 3 で実装予定です。"
        )
        return

    if action == "invite":
        if role != "student":
            welcome_text, qr = build_welcome_message()
            reply_text(event.reply_token, welcome_text, quick_reply=qr)
            return
        student.start_invitation_flow(event)
        return

    if action == "monthly_report":
        _reply_placeholder(
            event, role, "📊 月次レポート機能は Day 3 で実装予定です。"
        )
        return

    if action == "link_student":
        _reply_placeholder(event, role, "🔗 学生連携機能は Day 3 で実装予定です。")
        return

    if action == "main":
        if role is None:
            welcome_text, qr = build_welcome_message()
            reply_text(event.reply_token, welcome_text, quick_reply=qr)
            return
        reply_text(
            event.reply_token,
            "メインメニューです👇",
            quick_reply=main_menu_quick_reply(role),
        )
        return

    logger.warning("Unknown menu action: %s", action)
    _reply_placeholder(event, role, "未対応のアクションです。")


def _reply_placeholder(
    event: PostbackEvent, role: str | None, text: str
) -> None:
    """Terminal reply with role-aware Quick Reply (docs §3.4)."""
    if role is None:
        welcome_text, qr = build_welcome_message()
        reply_text(
            event.reply_token,
            f"{text}\n\n{welcome_text}",
            quick_reply=qr,
        )
        return
    reply_text(event.reply_token, text, quick_reply=main_menu_quick_reply(role))
