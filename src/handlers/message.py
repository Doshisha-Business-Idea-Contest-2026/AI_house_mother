"""Text message event handler.

Routing order (see ``docs/09_tasks.md`` and the Day 2 plan):

1. Reserved words (``キャンセル``, ``ヘルプ``, ``プロフィール``, etc.) always
   win: they clear any active session and trigger the target action.
2. If a session is active, the current state decides the routing target
   (profile flow / life consultation / etc.).
3. Otherwise, short text falls back to the main menu prompt while long
   text is treated as a life-consultation question.
"""
import logging

from linebot.v3.webhooks import MessageEvent, TextMessageContent

from src.config import handler
from src.handlers import student
from src.services import session, users
from src.services.line_reply import reply_text
from src.templates.flex.welcome import build_welcome_message
from src.templates.quick_reply import (
    main_menu_quick_reply,
    profile_start_quick_reply,
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
PROFILE_COMMANDS = {"プロフィール", "プロフ", "✍️ プロフィールを登録"}
WANT_TO_DO_COMMANDS = {"やりたい", "おすすめ", "🎯 やりたいこと相談"}
LIFE_COMMANDS = {"生活相談", "💬 生活相談", "相談"}
ROLE_SWITCH_COMMANDS = {"役割変更", "切り替え", "きりかえ"}
POST_COMMANDS = {"投稿", "経験", "✏️ 経験を投稿"}
INVITE_COMMANDS = {"招待", "コード", "\U0001F468‍\U0001F469‍\U0001F467 保護者連携"}

HELP_UNREGISTERED = (
    "まずは「学生」か「保護者」を選択してください。"
    "「はじめる」と送ると選択画面に戻ります。"
)

HELP_STUDENT = (
    "AI寮母の使い方 🏠\n"
    "🎯 やりたいこと相談 - あなたに合う活動を提案\n"
    "💬 生活相談 - 生活のお困りごとに答える\n"
    "✏️ 経験を投稿 - 参加した活動や利用したお店を記録 (Day 3)\n"
    "👤 プロフィール - 情報の確認・更新\n"
    "👨\u200d👩\u200d👧 保護者連携 - 招待コード発行 (Day 3)"
)

HELP_PARENT = (
    "AI寮母の使い方 🏠\n"
    "📊 今月のレポート - お子さんの頑張り確認 (Day 3)\n"
    "🔗 学生と連携 - 招待コードで学生と紐付け (Day 3)\n"
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
        welcome_text, qr = build_welcome_message()
        reply_text(event.reply_token, welcome_text, quick_reply=qr)
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
            event, user_id, "役割変更機能は準備中です。（Day 4 で実装予定）"
        )
        return

    if text in PROFILE_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.start_profile_flow(event)
        return

    if text == "あとで":
        session.clear_state(user_id)
        reply_text(
            event.reply_token,
            "了解しました。「プロフィール」といつでも送ってください。",
            quick_reply=main_menu_quick_reply("student"),
        )
        return

    if text in WANT_TO_DO_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.handle_want_to_do(event)
        return

    if text in LIFE_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.start_life_consultation(event)
        return

    if text in POST_COMMANDS:
        session.clear_state(user_id)
        _reply_placeholder(
            event, user_id, "✏️ 経験投稿機能は Day 3 で実装予定です。"
        )
        return

    if text in INVITE_COMMANDS:
        session.clear_state(user_id)
        if not _require_role(event, user_id, "student"):
            return
        student.start_invitation_flow(event)
        return

    # ------------------------------------------------------------------
    # 2) Session-driven routing.
    # ------------------------------------------------------------------
    state = session.get_state(user_id)
    if student.is_in_profile_flow(state):
        student.handle_profile_text(event, state)  # type: ignore[arg-type]
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
        if role != "student":
            welcome_text, qr = build_welcome_message()
            reply_text(event.reply_token, welcome_text, quick_reply=qr)
            return
        student.handle_life_consultation(event)
        return

    # Short unrecognised text → gentle prompt (§3.4).
    _reply_placeholder(
        event,
        user_id,
        "もう少し詳しく教えてください。もしくは下のメニューから選んでください👇",
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _reply_help(event: MessageEvent, user_id: str) -> None:
    role = users.get_role(user_id) if user_id else None
    if role is None:
        # Unregistered users get the welcome + role Quick Reply per §3.4.
        welcome_text, qr = build_welcome_message()
        reply_text(
            event.reply_token,
            f"{HELP_UNREGISTERED}\n\n{welcome_text}",
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
        welcome_text, qr = build_welcome_message()
        reply_text(event.reply_token, welcome_text, quick_reply=qr)
        return
    reply_text(
        event.reply_token,
        "メインメニューです。下のボタンから選んでください👇",
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
        welcome_text, qr = build_welcome_message()
        reply_text(
            event.reply_token,
            f"{text}\n\n{welcome_text}",
            quick_reply=qr,
        )
        return
    reply_text(event.reply_token, text, quick_reply=main_menu_quick_reply(role))


def _require_role(event: MessageEvent, user_id: str, required: str) -> bool:
    """Ensure the user has the ``required`` role; reply an explanation if not."""
    role = users.get_role(user_id)
    if role == required:
        return True
    if role is None:
        welcome_text, qr = build_welcome_message()
        reply_text(event.reply_token, welcome_text, quick_reply=qr)
        return False
    # role is the other one
    reply_text(
        event.reply_token,
        f"この機能は{'学生' if required == 'student' else '保護者'}向けです。",
    )
    return False
