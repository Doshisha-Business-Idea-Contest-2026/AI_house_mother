"""Postback event handler.

Handles all ``PostbackAction`` data payloads coming from Quick Reply and
Flex Message buttons. The prefix before the first ``:`` identifies which
sub-handler owns the action.

Supported prefixes:

- ``role:{student|parent}``  — initial role selection
- ``menu:*``                  — main menu / navigation
- ``profile:*``               — profile registration flow
- ``activity:*``              — activity carousel detail / participation
- ``invite:regenerate``       — student invitation code re-issue
- ``post:*``                  — experience posting flow
- ``link:*``                  — parent link entry / confirmation
"""
import logging

from linebot.v3.webhooks import PostbackEvent

from src.config import handler
from src.handlers import parent, student
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
    "連携コードをお持ちであれば、下のメニューの「🔗 学生と連携」から入力できます。"
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
            sender="system",
        )
        return

    if data == "role:parent":
        users.save_user(user_id, "parent")
        reply_text(
            event.reply_token,
            PARENT_CONFIRM,
            quick_reply=main_menu_quick_reply("parent"),
            sender="system",
        )
        return

    if data.startswith("menu:"):
        _handle_menu(event, data)
        return

    if data.startswith("profile:"):
        # Guard: user must be a student.
        role = users.get_role(user_id)
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        student.handle_profile_postback(event, data)
        return

    if data.startswith("activity:"):
        role = users.get_role(user_id)
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        _handle_activity(event, data)
        return

    if data.startswith("invite:"):
        role = users.get_role(user_id)
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        _handle_invite(event, data)
        return

    if data.startswith("post:"):
        role = users.get_role(user_id)
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        student.handle_post_postback(event, data)
        return

    if data.startswith("link:"):
        role = users.get_role(user_id)
        if role != "parent":
            _reply_wrong_role(event, role, "parent")
            return
        parent.handle_link_postback(event, data)
        return

    logger.warning("Unknown postback data: %s", data)
    _reply_placeholder(event, users.get_role(user_id), "未対応の操作です。")


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
            _reply_wrong_role(event, role, "student")
            return
        student.start_profile_flow(event)
        return

    if action == "profile":
        # Profile view/edit is not implemented yet; treat the button as a
        # shortcut to restart profile registration.
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        student.start_profile_flow(event)
        return

    if action == "want_to_do":
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        student.handle_want_to_do(event)
        return

    if action == "life":
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        student.start_life_consultation(event)
        return

    if action == "post":
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        student.start_post_flow(event)
        return

    if action == "invite":
        if role != "student":
            _reply_wrong_role(event, role, "student")
            return
        student.start_invitation_flow(event)
        return

    if action == "monthly_report":
        if role != "parent":
            _reply_wrong_role(event, role, "parent")
            return
        parent.handle_monthly_report(event)
        return

    if action == "link_student":
        if role != "parent":
            _reply_wrong_role(event, role, "parent")
            return
        parent.start_link_flow(event)
        return

    if action == "main":
        if role is None:
            welcome_text, qr = build_welcome_message()
            reply_text(
                event.reply_token, welcome_text, quick_reply=qr, sender="system"
            )
            return
        reply_text(
            event.reply_token,
            "メインメニューです👇",
            quick_reply=main_menu_quick_reply(role),
            sender="system",
        )
        return

    logger.warning("Unknown menu action: %s", action)
    _reply_placeholder(event, role, "未対応の操作です。")


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
            sender="system",
        )
        return
    reply_text(
        event.reply_token,
        text,
        quick_reply=main_menu_quick_reply(role),
        sender="system",
    )


def _reply_wrong_role(
    event: PostbackEvent, actual_role: str | None, required_role: str
) -> None:
    """Reply when a postback arrives from the wrong role.

    - ``actual_role`` is ``None`` → send the welcome message so an
      unregistered user can pick a role from scratch.
    - ``actual_role`` differs from ``required_role`` → keep the user on
      their current role's main menu and explain the mismatch (so a
      logged-in parent tapping a student-only Flex button is not
      bounced back to onboarding, and vice-versa).
    """
    if actual_role is None:
        welcome_text, qr = build_welcome_message()
        reply_text(
            event.reply_token, welcome_text, quick_reply=qr, sender="system"
        )
        return

    label = "学生" if required_role == "student" else "保護者"
    reply_text(
        event.reply_token,
        (
            f"この操作は{label}アカウント向けです。\n"
            "役割を変える場合は「はじめる」と送って選び直してください。"
        ),
        quick_reply=main_menu_quick_reply(actual_role),
        sender="system",
    )
