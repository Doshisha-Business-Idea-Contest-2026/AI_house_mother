"""Parent-facing business flows.

This module owns the multi-turn dialogs available to parent users:
invitation code redemption (Day 3, FR-P2) and monthly report retrieval
(Day 3, FR-P3, Pull path — implemented incrementally in T3.4).

Handlers are dispatched here from ``handlers/message.py`` (session +
reserved words) and ``handlers/postback.py`` (menu:link_student /
menu:monthly_report / link:*). Nothing is registered directly with the
LINE WebhookHandler.
"""
from __future__ import annotations

import logging
from typing import Any

from linebot.v3.webhooks import MessageEvent, PostbackEvent

from src.services import invitations, monthly_report, parent_links, session, users
from src.services.line_reply import push_flex, push_text, reply_flex, reply_text
from src.templates.flex.monthly_report import build_monthly_report_bubble
from src.templates.flex.welcome import build_welcome_message
from src.templates.quick_reply import cancel_quick_reply, main_menu_quick_reply

logger = logging.getLogger(__name__)

CODE_LENGTH = invitations.CODE_LENGTH
CODE_ALPHABET_SET = set(invitations.CODE_ALPHABET)
MAX_LINK_FAIL = 5

LINK_PROMPT = (
    "🔑 お子さんから受け取った 6 桁のコードを入力してください（英数字、大文字）\n"
    "例: A3F7K9\n\n"
    "やめる場合は「キャンセル」と送ってください。"
)

_ERROR_MESSAGES: dict[str, str] = {
    "invalid_format": (
        "コードは 6 桁の英数字（大文字）で入力してください。\n"
        "使える文字: A-Z（I/O を除く）、2-9\n"
    ),
    "not_found": (
        "そのコードは見つかりませんでした。学生さんに新しいコードを"
        "発行してもらってください。"
    ),
    "expired": (
        "そのコードは有効期限が切れています。学生さんに新しいコードを"
        "発行してもらってください。"
    ),
    "used": (
        "そのコードは既に使われています。学生さんに新しいコードを"
        "発行してもらってください。"
    ),
    "self_link": (
        "ご自身が発行したコードは使用できません。"
        "別の LINE アカウントで保護者役として登録してください。"
    ),
}

_LINK_COMPLETED_STUDENT = (
    "👨‍👩‍👧 保護者の方が連携を完了しました。\n"
    "今月から「頑張ったこと」として保存した投稿が保護者に届きます✨"
)

_LINK_COMPLETED_PARENT = (
    "🎉 学生さんとの連携が完了しました！\n\n"
    "📊 これから「今月のレポート」から、学生さんが共有した頑張りが確認できます。"
)


# ---------------------------------------------------------------------------
# Session state predicate
# ---------------------------------------------------------------------------


def is_in_link_flow(state: dict[str, Any] | None) -> bool:
    """Return ``True`` when the user is entering an invitation code."""
    return state is not None and state["state"] == "link.code"


# ---------------------------------------------------------------------------
# Flow entry points
# ---------------------------------------------------------------------------


def start_link_flow(event: MessageEvent | PostbackEvent) -> None:
    """Prompt the parent to enter an invitation code."""
    user_id = event.source.user_id
    session.set_state(user_id, "link.code")
    reply_text(
        event.reply_token,
        LINK_PROMPT,
        quick_reply=cancel_quick_reply(),
        sender="system",
    )


def handle_link_postback(event: PostbackEvent, data: str) -> None:
    """Handle link:* postbacks. Only ``link:start`` is used today."""
    if data == "link:start":
        start_link_flow(event)
        return

    logger.warning("Unknown link postback: %s", data)
    role = users.get_role(event.source.user_id)
    _reply_placeholder(event, role, "未対応の操作です。")


# ---------------------------------------------------------------------------
# Text handler (from handlers/message.py session routing)
# ---------------------------------------------------------------------------


def handle_link_text(event: MessageEvent) -> None:
    """Validate and consume the invitation code entered by the parent.

    Failed attempts (bad format or any :func:`invitations.consume` error)
    increment the session ``fail_count``. After ``MAX_LINK_FAIL`` failures
    the session is wiped and the welcome message is returned so the
    parent can start over from role selection.
    """
    user_id = event.source.user_id
    raw = event.message.text.strip()
    code = raw.upper()

    if not _is_valid_format(code):
        _handle_link_failure(event, user_id, "invalid_format")
        return

    student_id, err = invitations.consume(code, user_id)
    if err != "ok" or student_id is None:
        _handle_link_failure(event, user_id, err)
        return

    parent_links.link(user_id, student_id)
    session.clear_state(user_id)

    # Notify the student and confirm to the parent.
    try:
        push_text(student_id, _LINK_COMPLETED_STUDENT, sender="notify")
    except Exception:
        logger.exception("push_text to student failed")

    reply_text(
        event.reply_token,
        _LINK_COMPLETED_PARENT,
        quick_reply=main_menu_quick_reply("parent"),
        sender="notify",
    )
    logger.info(
        "parent_link completed parent=%s student=%s",
        user_id[:8],
        student_id[:8],
    )


# ---------------------------------------------------------------------------
# Monthly report (Pull path — placeholder; full impl arrives in T3.4)
# ---------------------------------------------------------------------------


def handle_monthly_report(event: MessageEvent | PostbackEvent) -> None:
    """Show the parent this month's summary (Pull path, FR-P3).

    Behaviour:
        * Unlinked parents receive a nudge to run the invitation flow.
        * For a single linked student, the report is delivered inline as
          a reply (Flex bubble or a plain text if the month is empty).
        * For multiple linked students, the first report is returned as
          a reply and any remaining are pushed sequentially.
    """
    user_id = event.source.user_id
    student_ids = parent_links.list_students_for_parent(user_id)
    if not student_ids:
        reply_text(
            event.reply_token,
            (
                "まだ学生さんと連携していません。\n"
                "先に「🔗 学生と連携」から招待コードを入力してください。"
            ),
            quick_reply=main_menu_quick_reply("parent"),
            sender="system",
        )
        return

    first_id, *rest = student_ids
    _reply_report_for(event, first_id, use_reply_token=True)
    for other_id in rest:
        _push_report_for(user_id, other_id)


def _reply_report_for(
    event: MessageEvent | PostbackEvent,
    student_user_id: str,
    *,
    use_reply_token: bool,
) -> None:
    report = monthly_report.build_current_month_report(student_user_id)
    if not report["posts"]:
        text = (
            f"📊 {report['student_display']}の今月（{report['year_month']}）"
            "はまだ頑張ったことの記録がありません。\n"
            "少し様子を見てあげてくださいね😊"
        )
        if use_reply_token:
            reply_text(
                event.reply_token,
                text,
                quick_reply=main_menu_quick_reply("parent"),
                sender="friendly",
            )
        return

    bubble = build_monthly_report_bubble(
        student_display=report["student_display"],
        year_month=report["year_month"],
        posts=report["posts"],
    )
    alt_text = (
        f"📊 {report['student_display']}の今月（{report['year_month']}）"
        f" 頑張ったこと {len(report['posts'])} 件"
    )
    if use_reply_token:
        reply_flex(
            event.reply_token,
            alt_text=alt_text,
            contents=bubble,
            quick_reply=main_menu_quick_reply("parent"),
            sender="friendly",
        )


def _push_report_for(parent_user_id: str, student_user_id: str) -> None:
    report = monthly_report.build_current_month_report(student_user_id)
    if not report["posts"]:
        push_text(
            parent_user_id,
            (
                f"📊 {report['student_display']}の今月（{report['year_month']}）"
                "はまだ頑張ったことの記録がありません。"
            ),
            sender="notify",
        )
        return
    bubble = build_monthly_report_bubble(
        student_display=report["student_display"],
        year_month=report["year_month"],
        posts=report["posts"],
    )
    alt_text = (
        f"📊 {report['student_display']}の今月（{report['year_month']}）"
        f" 頑張ったこと {len(report['posts'])} 件"
    )
    push_flex(
        parent_user_id, alt_text=alt_text, contents=bubble, sender="notify"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_format(code: str) -> bool:
    if len(code) != CODE_LENGTH:
        return False
    return all(ch in CODE_ALPHABET_SET for ch in code)


def _handle_link_failure(event: MessageEvent, user_id: str, err: str) -> None:
    fail_count = session.increment_fail(user_id)
    message = _ERROR_MESSAGES.get(err, "コードを確認できませんでした。")
    if fail_count >= MAX_LINK_FAIL:
        session.clear_state(user_id)
        welcome_text, qr = build_welcome_message()
        reply_text(
            event.reply_token,
            f"{message}\n\n何度もエラーが続いたので、最初からやり直しましょう。\n\n{welcome_text}",
            quick_reply=qr,
            sender="system",
        )
        return

    remaining = MAX_LINK_FAIL - fail_count
    hint = f"\n\n（残り {remaining} 回で最初からやり直しになります）"
    reply_text(
        event.reply_token,
        f"{message}{hint}\n\n{LINK_PROMPT}",
        quick_reply=cancel_quick_reply(),
        sender="system",
    )


def _reply_placeholder(
    event: PostbackEvent, role: str | None, text: str
) -> None:
    """Terminal reply with role-aware Quick Reply (mirrors postback.py §3.4)."""
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
