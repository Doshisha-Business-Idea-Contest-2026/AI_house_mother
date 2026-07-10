"""Text message event handler.

Routing order (see the reserved-word precedence table in
``docs/04_functional_spec.md`` §7):

1. Reserved words (``キャンセル``, ``ヘルプ``, ``プロフィール``, etc.) always
   win: they clear any active session and trigger the target action.
2. If a session is active, the current state decides the routing target
   (profile flow / life consultation / experience posting / parent link).
3. Otherwise, short text falls back to the main menu prompt while long
   text is treated as a life-consultation question.

Non-text messages (sticker / image / video / audio / file / location)
are routed via :func:`handle_non_text` per ``docs/04_functional_spec.md``
§3.4-b so the user never loses the Quick Reply thread after tapping a
sticker by accident.
"""

import logging

from linebot.v3.webhooks import (
    AudioMessageContent,
    FileMessageContent,
    ImageMessageContent,
    LocationMessageContent,
    MessageEvent,
    StickerMessageContent,
    TextMessageContent,
    VideoMessageContent,
)

from src.config import handler
from src.handlers import parent, student
from src.services import session, users
from src.services.line_reply import reply_flex, reply_text
from src.templates.flex.welcome import build_welcome_message
from src.templates.quick_reply import (
    cancel_quick_reply,
    main_menu_quick_reply,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reserved words. Each command triggers its own handler AFTER clearing
# whatever session was active.
# ---------------------------------------------------------------------------

CANCEL_COMMANDS = {"キャンセル", "やめる", "戻る"}
MENU_COMMANDS = {"メインメニュー", "menu"}
HELP_COMMANDS = {"ヘルプ", "使い方", "help", "Help", "HELP"}
RESTART_COMMANDS = {"はじめる", "始める", "スタート", "/start"}
PROFILE_COMMANDS = {"プロフィール", "プロフ"}
PROFILE_START_COMMANDS = {"✍️ プロフィールを登録", "プロフィール登録"}
WANT_TO_DO_COMMANDS = {"やりたい", "おすすめ", "🎯 やりたいこと相談"}
LIFE_COMMANDS = {"生活相談", "💬 生活相談", "相談"}
ROLE_SWITCH_COMMANDS = {"役割変更", "切り替え", "きりかえ"}
POST_COMMANDS = {"投稿", "経験", "✏️ 経験を投稿"}
INVITE_COMMANDS = {"招待", "コード", "\U0001f468‍\U0001f469‍\U0001f467 保護者連携"}
LINK_COMMANDS = {"連携", "🔗 学生と連携"}
MONTHLY_COMMANDS = {"レポート", "頑張ったこと", "📊 今月のレポート"}

HELP_UNREGISTERED = (
    "まずは「学生」か「保護者」を選択してください。"
    "「はじめる」と送ると選択画面に戻ります。"
)

HELP_STUDENT = (
    "AI寮母の使い方 🏠\n"
    "🎯 やりたいこと相談 - あなたに合う活動を提案\n"
    "💬 生活相談 - 生活のお困りごとに答える\n"
    "✏️ 経験を投稿 - 参加した活動や利用したお店を記録\n"
    "👤 プロフィール - 情報の確認・更新\n"
    "👨\u200d👩\u200d👧 保護者連携 - 招待コードを発行して保護者と紐付け\n"
    "❓ ヘルプ - この案内"
)

HELP_PARENT = (
    "AI寮母の使い方 🏠\n"
    "📊 今月のレポート - お子さんの頑張り確認\n"
    "🔗 学生と連携 - 招待コードで学生と紐付け\n"
    "❓ ヘルプ - この案内"
)


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event: MessageEvent) -> None:
    """Route text messages using the priority described in the module docstring."""
    text = event.message.text.strip()
    user_id = event.source.user_id
    logger.info("Text from %s: %s", user_id[:8] if user_id else "?", text[:80])

    # ------------------------------------------------------------------
    # 1) Reserved words — highest priority. Always clear stale session.
    # ------------------------------------------------------------------
    if text in CANCEL_COMMANDS:
        session.clear_state(user_id)
        _reply_placeholder(event, user_id, "操作をキャンセルしました。")
        return

    if text in RESTART_COMMANDS:
        session.clear_state(user_id)
        alt_text, contents, qr = build_welcome_message()
        reply_flex(
            event.reply_token,
            alt_text=alt_text,
            contents=contents,
            quick_reply=qr,
        )
        return

    if text in HELP_COMMANDS:
        session.clear_state(user_id)
        _reply_help(event, user_id)
        return

    if text in MENU_COMMANDS:
        session.clear_state(user_id)
        _reply_main_menu(event, user_id)
        return

    if text in ROLE_SWITCH_COMMANDS:
        session.clear_state(user_id)
        _reply_placeholder(
            event,
            user_id,
            "役割変更は本 MVP では未対応です。「はじめる」から選び直せます。",
        )
        return

    if text in PROFILE_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.handle_profile_view(event)
        return

    if text in PROFILE_START_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.start_profile_flow(event)
        return

    if text == "あとで":
        session.clear_state(user_id)
        reply_text(
            event.reply_token,
            "了解しました。「プロフィール登録」と送ればいつでも登録を始められます。",
            quick_reply=main_menu_quick_reply("student"),
        )
        return

    if text in WANT_TO_DO_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.start_want_to_do_menu(event)
        return

    if text in LIFE_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.start_life_consultation(event)
        return

    if text in POST_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.start_post_flow(event)
        return

    if text in INVITE_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.start_invitation_flow(event)
        return

    if text in LINK_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "parent"):
            return
        parent.start_link_flow(event)
        return

    if text in MONTHLY_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "parent"):
            return
        parent.handle_monthly_report(event)
        return

    # ------------------------------------------------------------------
    # 2) Session-driven routing.
    # ------------------------------------------------------------------
    state = session.get_state(user_id)
    if student.is_in_profile_flow(state):
        student.handle_profile_text(event, state)  # type: ignore[arg-type]
        return
    if student.is_in_post_flow(state):
        if not _require_role(event, user_id, "student"):
            return
        student.handle_post_text(event, state)  # type: ignore[arg-type]
        return
    if parent.is_in_link_flow(state):
        if not _require_role(event, user_id, "parent"):
            return
        parent.handle_link_text(event)
        return
    if student.is_in_life_flow(state):
        if not _require_role(event, user_id, "student"):
            return
        student.handle_life_consultation(event)
        return

    # ------------------------------------------------------------------
    # 3) Free-form fallback: long text → life consultation.
    # ------------------------------------------------------------------
    if len(text) >= 10:
        role = users.get_role(user_id)
        if role == "student":
            student.handle_life_consultation(event)
            return
        # Non-student (parent or unregistered) follows the §3.4 terminal-
        # reply rule: _reply_placeholder routes role=parent to the parent
        # menu and role=None to the welcome bubble, so a registered parent
        # is no longer bounced back to onboarding on free text.
        _reply_placeholder(
            event,
            user_id,
            "メッセージありがとうございます😊 下のメニューから選んでください👇",
        )
        return

    # Short unrecognised text → gentle prompt (§3.4).
    _reply_placeholder(
        event,
        user_id,
        "もう少し詳しく教えてください。もしくは下のメニューから選んでください👇",
    )


# ---------------------------------------------------------------------------
# Non-text fallback (§3.4-b): keep the Quick Reply thread alive when the
# user sends a sticker / image / video / audio / file / location. Stacking
# @handler.add for each type registers the same function in the SDK's
# per-type dispatch table.
# ---------------------------------------------------------------------------


@handler.add(MessageEvent, message=StickerMessageContent)
@handler.add(MessageEvent, message=ImageMessageContent)
@handler.add(MessageEvent, message=VideoMessageContent)
@handler.add(MessageEvent, message=AudioMessageContent)
@handler.add(MessageEvent, message=FileMessageContent)
@handler.add(MessageEvent, message=LocationMessageContent)
def handle_non_text(event: MessageEvent) -> None:
    """Reply with a role/session-aware nudge so no non-text goes silent."""
    user_id = event.source.user_id
    kind = type(event.message).__name__.replace("MessageContent", "").lower()
    logger.info("Non-text from %s: kind=%s", user_id[:8] if user_id else "?", kind)

    state = session.get_state(user_id)

    if student.is_in_life_flow(state):
        student.reprompt_life_non_text(event)
        return

    if (
        student.is_in_profile_flow(state)
        or student.is_in_post_flow(state)
        or parent.is_in_link_flow(state)
    ):
        reply_text(
            event.reply_token,
            "テキストで送ってください。中断する場合は「キャンセル」と送ってください。",
            quick_reply=cancel_quick_reply(),
        )
        return

    role = users.get_role(user_id)
    if role == "student":
        reply_text(
            event.reply_token,
            "メッセージありがとうございます😊\n下のメニューから使いたい機能を選んでください👇",
            quick_reply=main_menu_quick_reply("student"),
        )
        return
    if role == "parent":
        reply_text(
            event.reply_token,
            "メッセージありがとうございます😊\n下のメニューから使いたい機能を選んでください👇",
            quick_reply=main_menu_quick_reply("parent"),
        )
        return

    alt_text, contents, qr = build_welcome_message(
        prefix="メッセージありがとうございます。まずは役割を教えてください。"
    )
    reply_flex(
        event.reply_token,
        alt_text=alt_text,
        contents=contents,
        quick_reply=qr,
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _reply_help(event: MessageEvent, user_id: str) -> None:
    role = users.get_role(user_id) if user_id else None
    if role is None:
        # Unregistered users get the welcome + role Quick Reply per §3.4.
        alt_text, contents, qr = build_welcome_message(prefix=HELP_UNREGISTERED)
        reply_flex(
            event.reply_token,
            alt_text=alt_text,
            contents=contents,
            quick_reply=qr,
        )
    elif role == "student":
        reply_text(
            event.reply_token,
            HELP_STUDENT,
            quick_reply=main_menu_quick_reply("student"),
        )
    else:
        reply_text(
            event.reply_token,
            HELP_PARENT,
            quick_reply=main_menu_quick_reply("parent"),
        )


def _reply_main_menu(event: MessageEvent, user_id: str) -> None:
    role = users.get_role(user_id) if user_id else None
    if role is None:
        alt_text, contents, qr = build_welcome_message()
        reply_flex(
            event.reply_token,
            alt_text=alt_text,
            contents=contents,
            quick_reply=qr,
        )
        return
    reply_text(
        event.reply_token,
        "メインメニューです。下のメニューから選んでください👇",
        quick_reply=main_menu_quick_reply(role),
    )


def _reply_placeholder(event: MessageEvent, user_id: str, text: str) -> None:
    """Send a terminal reply with the role-appropriate main menu Quick Reply.

    Implements the §3.4 terminal-reply rule of docs/04_functional_spec.md:
    cancel / placeholder / error replies must never leave the user
    stranded without a next-action prompt. Unregistered users are
    redirected to the welcome message with the role selection QR.
    """
    role = users.get_role(user_id) if user_id else None
    if role is None:
        alt_text, contents, qr = build_welcome_message(prefix=text)
        reply_flex(
            event.reply_token,
            alt_text=alt_text,
            contents=contents,
            quick_reply=qr,
        )
        return
    reply_text(
        event.reply_token,
        text,
        quick_reply=main_menu_quick_reply(role),
    )


def _require_role(event: MessageEvent, user_id: str, required: str) -> bool:
    """Ensure the user has the ``required`` role; reply an explanation if not."""
    role = users.get_role(user_id)
    if role == required:
        return True
    if role is None:
        alt_text, contents, qr = build_welcome_message()
        reply_flex(
            event.reply_token,
            alt_text=alt_text,
            contents=contents,
            quick_reply=qr,
        )
        return False
    # role is the other one — keep the user oriented in their own menu so
    # a mistap doesn't strand them (docs/04 §3.4). Mirrors the pattern in
    # postback._reply_wrong_role.
    label = "学生" if required == "student" else "保護者"
    reply_text(
        event.reply_token,
        (
            f"この操作は{label}アカウント向けです。\n"
            "役割を変える場合は「はじめる」と送って選び直してください。"
        ),
        quick_reply=main_menu_quick_reply(role),
    )
    return False
