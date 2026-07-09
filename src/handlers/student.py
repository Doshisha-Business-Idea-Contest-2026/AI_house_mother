"""Student-facing business flows.

This module owns the multi-turn dialog logic for a student user:
profile registration, want-to-do consultation, life consultation,
experience posting and invitation code issuance.

The router entry points (``handlers/message.py`` and
``handlers/postback.py``) delegate here based on session state and
postback prefixes.
"""

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from linebot.v3.messaging import (
    MessageAction,
    PostbackAction,
    QuickReply,
    QuickReplyItem,
)
from linebot.v3.webhooks import MessageEvent, PostbackEvent

from src.services import (
    activity_store,
    context_search,
    coupons,
    gemini,
    invitations,
    posts,
    profiles,
    prompts,
    session,
    sponsored,
    usage_stats,
    users,
)
from src.services.line_reply import (
    push_flex,
    push_text,
    reply_flex,
    reply_text,
    show_loading,
)
from src.templates.flex.activity_carousel import build_activity_carousel
from src.templates.flex.coupon_carousel import build_coupon_carousel
from src.templates.flex.invitation_code import build_invitation_bubble
from src.templates.flex.profile_view import build_profile_view_bubble
from src.templates.quick_reply import (
    INTEREST_TAGS,
    POST_CATEGORIES,
    cancel_quick_reply,
    confirm_quick_reply,
    effort_quick_reply,
    grade_quick_reply,
    interests_quick_reply,
    invitation_menu_quick_reply,
    main_menu_quick_reply,
    post_area_quick_reply,
    post_category_quick_reply,
    post_confirm_quick_reply,
    post_share_parent_quick_reply,
    post_skip_quick_reply,
    profile_start_quick_reply,
    profile_view_quick_reply,
    want_to_do_menu_quick_reply,
)
from src.utils import text_format

logger = logging.getLogger(__name__)

_JST = ZoneInfo("Asia/Tokyo")

MAX_TEXT_LEN = 200
MIN_INTERESTS = 1


# ---------------------------------------------------------------------------
# Entry: profile registration
# ---------------------------------------------------------------------------


def handle_profile_view(event: MessageEvent | PostbackEvent) -> None:
    """Show the student's stored profile as a Flex bubble.

    Falls back to the registration prompt when no profile exists, so
    the caller does not need to double-check ``profiles.has_profile``.
    """
    user_id = event.source.user_id
    profile = profiles.get_profile(user_id)
    if profile is None:
        session.clear_state(user_id)
        reply_text(
            event.reply_token,
            "プロフィールがまだ登録されていません。\n登録すると、あなたに合った活動提案や生活相談ができます。",
            quick_reply=profile_start_quick_reply(),
        )
        return

    session.clear_state(user_id)
    reply_flex(
        event.reply_token,
        alt_text="👤 あなたのプロフィール",
        contents=build_profile_view_bubble(profile),
        quick_reply=profile_view_quick_reply(),
    )


def start_profile_flow(event: MessageEvent | PostbackEvent) -> None:
    """Kick off the profile registration flow."""
    user_id = event.source.user_id
    existing = profiles.get_profile(user_id)
    if existing:
        # allow re-registration but flag to the user
        reply_text(
            event.reply_token,
            "編集を始めます。今の内容はいったん置いておいて、最初から入力し直します（登録すると上書きされます）。\n\n🏫 まずは大学名を教えてください（例: 同志社大学）",
        )
    else:
        reply_text(
            event.reply_token,
            "プロフィール登録を始めます✨\n\n🏫 まずは大学名を教えてください（例: 同志社大学）",
        )
    session.set_state(user_id, "profile.university")


# ---------------------------------------------------------------------------
# Text handlers (dispatched by handlers/message.py)
# ---------------------------------------------------------------------------


def handle_profile_text(event: MessageEvent, state: dict[str, Any]) -> None:
    """Route text input to the right profile step based on session state."""
    user_id = event.source.user_id
    text = event.message.text.strip()

    if len(text) > MAX_TEXT_LEN:
        reply_text(
            event.reply_token,
            f"入力が長すぎます。{MAX_TEXT_LEN} 文字以内でお願いします。",
        )
        return

    step = state["state"]

    if step == "profile.university":
        _record(user_id, "university", text)
        session.set_state(user_id, "profile.faculty", **_context_snapshot(user_id))
        reply_text(
            event.reply_token,
            "ありがとうございます！\n📚 次に、学部を教えてください（例: 経済学部）",
        )
        return

    if step == "profile.faculty":
        _record(user_id, "faculty", text)
        session.set_state(user_id, "profile.grade", **_context_snapshot(user_id))
        reply_text(
            event.reply_token,
            "🎓 学年を選んでください",
            quick_reply=grade_quick_reply(),
        )
        return

    if step == "profile.effort":
        value = "" if text in ("スキップ", "skip", "Skip") else text
        _record(user_id, "recent_effort", value)
        session.set_state(user_id, "profile.want_to_do", **_context_snapshot(user_id))
        reply_text(
            event.reply_token,
            "🎯 やってみたいこと・興味のあることを教えてください（自由記述）",
        )
        return

    if step == "profile.want_to_do":
        _record(user_id, "want_to_do", text)
        _send_confirmation(event)
        return

    if step == "profile.grade":
        reply_text(
            event.reply_token,
            "学年は下のメニューから選んでください🎓",
            quick_reply=grade_quick_reply(),
        )
        return

    if step == "profile.interests":
        reply_text(
            event.reply_token,
            "興味のタグは下のメニューから選んでください（複数OK）。選び終わったら ✅ 完了 を押してください。",
            quick_reply=interests_quick_reply(),
        )
        return

    if step == "profile.confirm":
        reply_text(
            event.reply_token,
            "下のメニューで「登録する」か「やり直す」を選んでください。",
            quick_reply=confirm_quick_reply(),
        )
        return

    logger.warning("Unexpected profile step for text input: %s", step)


# ---------------------------------------------------------------------------
# Postback handlers (dispatched by handlers/postback.py)
# ---------------------------------------------------------------------------


def handle_profile_postback(event: PostbackEvent, data: str) -> None:
    """Handle postback for the profile flow (``profile:*`` prefixes)."""
    user_id = event.source.user_id
    state = session.get_state(user_id)

    if state is None:
        reply_text(
            event.reply_token,
            "セッションが切れました。もう一度「プロフィール登録」と送るか、👤 プロフィール → ✏️ 編集する からやり直してください。",
        )
        return

    if data.startswith("profile:grade:"):
        grade = data.removeprefix("profile:grade:")
        _record(user_id, "grade", grade)
        session.set_state(user_id, "profile.interests", **_context_snapshot(user_id))
        reply_text(
            event.reply_token,
            "✨ 興味のあることを選んでください（複数選択OK）。選び終わったら ✅ 完了 を押してください",
            quick_reply=interests_quick_reply(),
        )
        return

    if data.startswith("profile:interest:"):
        tag = data.removeprefix("profile:interest:")
        if tag not in INTEREST_TAGS:
            reply_text(event.reply_token, "未対応のタグです。")
            return
        current = _get_context_value(user_id, "interests", [])
        if tag in current:
            current.remove(tag)
            action = "解除"
        else:
            current.append(tag)
            action = "追加"
        _record(user_id, "interests", current)
        selected_str = " / ".join(current) if current else "（まだ選択なし）"
        reply_text(
            event.reply_token,
            f"「{tag}」を{action}しました。\n現在選択中: {selected_str}\n他にあれば選ぶか、✅ 完了 を押してください",
            quick_reply=interests_quick_reply(),
        )
        return

    if data == "profile:interest_done":
        current = _get_context_value(user_id, "interests", [])
        if len(current) < MIN_INTERESTS:
            reply_text(
                event.reply_token,
                "少なくとも 1 つはタグを選んでください。",
                quick_reply=interests_quick_reply(),
            )
            return
        session.set_state(user_id, "profile.effort", **_context_snapshot(user_id))
        reply_text(
            event.reply_token,
            "💪 最近頑張っていることを教えてください（自由記述、なければ「スキップ」）",
            quick_reply=effort_quick_reply(),
        )
        return

    if data == "profile:confirm:yes":
        if state is None or state["state"] != "profile.confirm":
            reply_text(
                event.reply_token,
                "セッションが切れました。もう一度「プロフィール登録」と送るか、👤 プロフィール → ✏️ 編集する からやり直してください。",
            )
            return
        _finalize_profile(event)
        return

    if data == "profile:confirm:redo":
        session.clear_state(user_id)
        reply_text(
            event.reply_token,
            "もう一度最初から登録します。\n🏫 大学名を教えてください（例: 同志社大学）",
        )
        session.set_state(user_id, "profile.university")
        return

    logger.warning("Unknown profile postback: %s", data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record(user_id: str, field: str, value: Any) -> None:
    """Persist ``field`` into the current session's context dict."""
    state = session.get_state(user_id)
    if state is None:
        # Recreate an empty session with unknown current step; caller must set state next
        session.set_state(user_id, "profile.university", **{field: value})
        return
    context = dict(state["context"])
    context[field] = value
    # Keep the current state name; only mutate context
    session.set_state(user_id, state["state"], **context)


def _context_snapshot(user_id: str) -> dict[str, Any]:
    """Return the current session context as kwargs for set_state."""
    state = session.get_state(user_id)
    return dict(state["context"]) if state else {}


def _get_context_value(user_id: str, key: str, default: Any) -> Any:
    """Read a single value out of the session context."""
    state = session.get_state(user_id)
    if state is None:
        return default
    return state["context"].get(key, default)


def _send_confirmation(event: MessageEvent) -> None:
    """Send the review card summarising the collected profile."""
    user_id = event.source.user_id
    ctx = _context_snapshot(user_id)
    interests = " / ".join(ctx.get("interests", [])) or "（選択なし）"
    effort = ctx.get("recent_effort") or "（未入力）"
    summary = (
        "内容を確認してください:\n"
        f"🏫 大学: {ctx.get('university', '（未入力）')}\n"
        f"📚 学部: {ctx.get('faculty', '（未入力）')}\n"
        f"🎓 学年: {ctx.get('grade', '（未入力）')}\n"
        f"✨ 興味: {interests}\n"
        f"💪 最近頑張っていること: {effort}\n"
        f"🎯 やってみたいこと: {ctx.get('want_to_do', '（未入力）')}\n\n"
        "この内容で登録しますか？"
    )
    session.set_state(user_id, "profile.confirm", **ctx)
    reply_text(event.reply_token, summary, quick_reply=confirm_quick_reply())


def _finalize_profile(event: PostbackEvent) -> None:
    """Persist the profile from session context and confirm to the user."""
    user_id = event.source.user_id
    ctx = _context_snapshot(user_id)
    profile = {
        "university": ctx.get("university", ""),
        "faculty": ctx.get("faculty", ""),
        "grade": ctx.get("grade", ""),
        "interests": ctx.get("interests", []),
        "recent_effort": ctx.get("recent_effort", ""),
        "want_to_do": ctx.get("want_to_do", ""),
    }
    profiles.save_profile(user_id, profile)
    usage_stats.record(user_id, "profile")
    session.clear_state(user_id)

    role = users.get_role(user_id) or "student"
    reply_text(
        event.reply_token,
        "プロフィール登録完了です🎉\n\n下のメニューから使いたい機能を選んでください。",
        quick_reply=main_menu_quick_reply(role),
    )
    logger.info("Profile saved for %s", user_id[:8])


# ---------------------------------------------------------------------------
# Want-to-do consultation (FR-S4)
# ---------------------------------------------------------------------------


ACTIVITY_QUICK_REPLY_ITEMS = [
    QuickReplyItem(
        action=PostbackAction(
            label="🔄 他の案も見る",
            data="menu:want_to_do",
            display_text="🔄 他の案も見る",
        )
    ),
    QuickReplyItem(
        action=PostbackAction(
            label="🏠 メインメニュー",
            data="menu:main",
            display_text="🏠 メインメニュー",
        )
    ),
]


def _activity_quick_reply() -> QuickReply:
    return QuickReply(items=list(ACTIVITY_QUICK_REPLY_ITEMS))


def _require_profile_or_prompt(
    event: MessageEvent | PostbackEvent,
) -> dict[str, Any] | None:
    """Return the caller's profile, or reply with the registration nudge.

    Shared gate for the want-to-do hub and both of its branches. Returns
    ``None`` (after sending a reply) when the profile is missing so the
    caller can bail out early.
    """
    user_id = event.source.user_id
    profile = profiles.get_profile(user_id)
    if profile is None:
        reply_text(
            event.reply_token,
            "まずは 👤 プロフィール登録をお願いします。\nあなたに合った提案ができるようになります。",
            quick_reply=profile_start_quick_reply(),
        )
        return None
    return profile


def start_want_to_do_menu(event: MessageEvent | PostbackEvent) -> None:
    """Show the "やりたいこと相談" hub (docs/04 §4.3).

    No Gemini call here: the student first picks an angle (other
    students' efforts vs local events) via Quick Reply, and only the
    chosen branch invokes Gemini.
    """
    if _require_profile_or_prompt(event) is None:
        return
    reply_text(
        event.reply_token,
        "どんな切り口で探しますか？🔎\n先輩や仲間の取り組みからも、地域のイベントからも探せます。",
        quick_reply=want_to_do_menu_quick_reply(),
    )


def _send_activity_carousel(
    user_id: str,
    activities: list[dict[str, Any]],
    alt_text: str,
    profile: dict[str, Any],
) -> None:
    """Persist proposals and push the carousel + follow-up Quick Reply.

    Shared tail for both want-to-do branches. ``activities`` must be
    non-empty (branches fall back to seed before calling this). A matching
    sponsored PR entry (FR-S9) is deterministically prepended when the
    profile qualifies; sponsored entries bypass ``activity_store`` since
    their postbacks resolve via ``sponsor_id`` directly.
    """
    keys = activity_store.remember(user_id, activities)
    session.set_state(user_id, "activity.viewing", activity_keys=keys)

    match = sponsored.match_for_profile(profile)
    flex = build_activity_carousel(activities, keys, sponsored=match)
    push_flex(user_id, alt_text=alt_text, contents=flex)
    push_text(
        user_id,
        "気になる提案があれば、カード内のボタンを押してください👇",
        quick_reply=_activity_quick_reply(),
    )


def handle_want_events(event: MessageEvent | PostbackEvent) -> None:
    """Want-to-do branch A: propose local events/activities (FR-S4)."""
    profile = _require_profile_or_prompt(event)
    if profile is None:
        return

    user_id = event.source.user_id
    usage_stats.record(user_id, "activity")
    # Show the LINE loading indicator so the user sees a native
    # "typing" animation while we wait for Gemini. reply_token is
    # intentionally left unused; the carousel goes out via push below.
    show_loading(user_id)

    try:
        activities = gemini.propose_activities(profile)
    except Exception:
        logger.exception("propose_activities crashed")
        activities = []

    if not activities:
        push_text(
            user_id,
            "うまく提案を思いつけませんでした。少し時間を空けてもう一度お試しください🙇",
            quick_reply=main_menu_quick_reply("student"),
        )
        return

    _send_activity_carousel(
        user_id,
        activities,
        alt_text="🎯 やりたいこと相談：あなたへのおすすめ",
        profile=profile,
    )


def handle_want_students(event: MessageEvent | PostbackEvent) -> None:
    """Want-to-do branch B: propose from other students' efforts (FR-S4).

    Uses senior posts (seed) plus anonymized runtime experience posts.
    Even with zero runtime posts, Gemini/the seed fallback still returns
    proposals, so an empty result only happens on a hard failure.
    """
    profile = _require_profile_or_prompt(event)
    if profile is None:
        return

    user_id = event.source.user_id
    usage_stats.record(user_id, "activity")
    show_loading(user_id)

    try:
        activities = gemini.propose_from_student_efforts(profile)
    except Exception:
        logger.exception("propose_from_student_efforts crashed")
        activities = []

    if not activities:
        push_text(
            user_id,
            "うまく提案を思いつけませんでした。少し時間を空けてもう一度お試しください🙇",
            quick_reply=main_menu_quick_reply("student"),
        )
        return

    _send_activity_carousel(
        user_id,
        activities,
        alt_text="🎯 やりたいこと相談：先輩・仲間の取り組み",
        profile=profile,
    )


def handle_activity_detail(event: PostbackEvent, key: str) -> None:
    """Handle the "詳しく聞く" button for an activity carousel item."""
    user_id = event.source.user_id
    activity = activity_store.resolve(key)
    if activity is None:
        reply_text(
            event.reply_token,
            "対象の情報を復元できませんでした（時間が経ちすぎたようです）。もう一度「やりたいこと相談」を試してください。",
            quick_reply=_activity_quick_reply(),
        )
        return

    profile = profiles.get_profile(user_id)
    # docs/04 §3.6: replace the text ack with the native loading indicator.
    show_loading(user_id)
    try:
        detail = gemini.answer_activity_detail(profile, activity)
    except Exception:
        logger.exception("answer_activity_detail failed")
        detail = (
            f"「{activity.get('title', '')}」の詳しい情報を取得できませんでした。"
            "担当団体に直接お問い合わせください。"
        )
    push_text(user_id, detail, quick_reply=_activity_quick_reply())


def handle_activity_participated(event: PostbackEvent, key: str) -> None:
    """Handle the "参加した" button. Acks the tap and points at ✏️ 経験を投稿."""
    activity = activity_store.resolve(key)
    if activity is None:
        reply_text(
            event.reply_token,
            "対象の情報を復元できませんでした（時間が経ちすぎたようです）。改めて「やりたいこと相談」を試してください。",
            quick_reply=_activity_quick_reply(),
        )
        return

    reply_text(
        event.reply_token,
        (
            f"「{activity.get('title', '')}」に参加した記録を受け付けました！✨\n"
            "詳しく投稿したい場合は「✏️ 経験を投稿」から記録できます。"
        ),
        quick_reply=_activity_quick_reply(),
    )


def handle_sponsored_interest(event: PostbackEvent, sponsor_id: str) -> None:
    """Handle the "興味あり" button on a sponsored PR bubble (FR-S9).

    Records the tap for the sponsor's engagement metrics and acks the
    student. The apply URL itself is opened by the separate URI button, so
    this only needs to confirm the interest and point at the seed values.
    """
    entry = sponsored.get_by_id(sponsor_id)
    if entry is None:
        reply_text(
            event.reply_token,
            "対象の案内を復元できませんでした。もう一度「やりたいこと相談」を試してください。",
            quick_reply=_activity_quick_reply(),
        )
        return

    sponsored.record_interest(event.source.user_id, sponsor_id)
    reply_text(
        event.reply_token,
        (
            f"「{entry.get('title', '')}」への興味を受け付けました！✨\n"
            "詳細・応募はカード内の「詳細・応募はこちら」から確認できます。\n"
            "※この案内は協賛企業からの提供です。"
        ),
        quick_reply=_activity_quick_reply(),
    )


# ---------------------------------------------------------------------------
# Life consultation (FR-S5)
# ---------------------------------------------------------------------------


LIFE_QUICK_REPLY_ITEMS = [
    QuickReplyItem(
        action=PostbackAction(
            label="🏠 メインメニュー",
            data="menu:main",
            display_text="🏠 メインメニュー",
        )
    ),
    QuickReplyItem(action=MessageAction(label="🚫 相談を終える", text="キャンセル")),
]


_EMERGENCY_LIFE_REPLY = (
    "つらいですね…すぐに話せる相手として、\n"
    "・京都いのちの電話: 075-864-4343\n"
    "・よりそいホットライン: 0120-279-338\n"
    "電話が難しければ、身近な人に一言だけでも伝えてみてください。\n"
    "あなたを大切に思う人がいます。"
)

_EMERGENCY_MEDICAL_REPLY = (
    "🚨 緊急の場合は 119 に通報してください。\n"
    "救急かどうか判断に迷うときは #7119（京都府救急安心センター）で相談できます。"
)

_EMERGENCY_CRIME_REPLY = (
    "警察への相談をおすすめします。\n" "・緊急: 110\n" "・相談: #9110"
)


def _life_quick_reply() -> QuickReply:
    return QuickReply(items=list(LIFE_QUICK_REPLY_ITEMS))


def start_life_consultation(event: MessageEvent | PostbackEvent) -> None:
    """Prompt the student to describe their concern (from the menu)."""
    user_id = event.source.user_id
    session.set_state(user_id, "life.waiting")
    reply_text(
        event.reply_token,
        "💬 生活のお困りごとをどうぞ。「熱っぽくて病院を探しています」のように自由に書いてください。",
        quick_reply=_life_quick_reply(),
    )


def reprompt_life_non_text(event: MessageEvent) -> None:
    """Nudge a life-flow user who sent a sticker/image/etc. back to text.

    Called from the router in ``handlers/message.py::handle_non_text``
    so ``_life_quick_reply`` stays module-private.
    """
    reply_text(
        event.reply_token,
        "テキストで質問を送ってください。中断する場合は「🚫 相談を終える」を押してね。",
        quick_reply=_life_quick_reply(),
    )


def handle_life_consultation(event: MessageEvent) -> None:
    """Process a life-consultation message and reply.

    Emergency keywords short-circuit the Gemini call and route to canned
    guidance instead. Otherwise Gemini is invoked; when the seed context
    is empty (``total_hits == 0``) the reply is wrapped with a
    Zero-context disclaimer and, for medical topics, the #7119 followup
    (see docs/06_ai_spec.md §5.3).
    """
    user_id = event.source.user_id
    text = event.message.text.strip()

    emergency = context_search.detect_emergency(text)
    if emergency == "life":
        session.clear_state(user_id)
        reply_text(
            event.reply_token,
            _EMERGENCY_LIFE_REPLY,
            quick_reply=_life_quick_reply(),
        )
        return
    if emergency == "medical":
        session.clear_state(user_id)
        reply_text(
            event.reply_token,
            _EMERGENCY_MEDICAL_REPLY,
            quick_reply=_life_quick_reply(),
        )
        return
    if emergency == "crime":
        session.clear_state(user_id)
        reply_text(
            event.reply_token,
            _EMERGENCY_CRIME_REPLY,
            quick_reply=_life_quick_reply(),
        )
        return

    usage_stats.record(user_id, "life")
    # docs/04 §3.6: show the native loading indicator while we search and
    # call Gemini; the Gemini response goes out below as a push.
    show_loading(user_id)

    profile = profiles.get_profile(user_id)
    result = context_search.find_relevant_context(text)
    zero_context = context_search.should_add_disclaimer(result)
    medical_intent = context_search.detect_medical_intent(text)
    total_hits = result["total_hits"]

    try:
        answer = gemini.answer_life_question(
            profile, text, result, total_hits=total_hits
        )
    except Exception:
        logger.exception("answer_life_question crashed")
        answer = (
            "うまく答えを考えられませんでした。少し時間を空けてもう一度お試しください🙇"
        )

    disclaimer_shown = zero_context
    medical_followup_shown = zero_context and medical_intent

    # docs/06 §4.2 / docs/04 §4.4: LINE does not render Markdown, so strip
    # Gemini's Markdown residue and join disclaimer / body / followup with a
    # single blank line before sending as one text bubble.
    answer = text_format.normalize_markdown(answer)
    blocks: list[str] = []
    if disclaimer_shown:
        blocks.append(prompts.ZERO_CONTEXT_DISCLAIMER)
    blocks.append(answer)
    if medical_followup_shown:
        blocks.append(prompts.MEDICAL_FOLLOWUP)
    final = text_format.join_blocks(blocks)

    logger.info(
        "life_consultation user=%s total_hits=%d zero_context=%s "
        "disclaimer_shown=%s medical_followup_shown=%s "
        "student_posts_hits=%d matched_categories=%s",
        user_id[:8] if user_id else "?",
        total_hits,
        zero_context,
        disclaimer_shown,
        medical_followup_shown,
        len(result["student_posts"]),
        sorted(result["matched_categories"]),
    )

    push_text(user_id, final, quick_reply=_life_quick_reply())
    # Keep the session so follow-up questions are still routed to life consultation.
    session.set_state(user_id, "life.waiting")


# ---------------------------------------------------------------------------
# Invitation code (FR-S7)
# ---------------------------------------------------------------------------


def start_invitation_flow(event: MessageEvent | PostbackEvent) -> None:
    """Issue a fresh 6-character invitation code and reply as Flex.

    Any prior pending code for the same student is revoked inside
    ``invitations.issue_code`` so only one active code exists at a time.
    Session state is cleared afterwards; the follow-up navigation is
    driven by the Quick Reply attached to the Flex message (invitation
    menu: re-issue / main menu).
    """
    user_id = event.source.user_id
    session.clear_state(user_id)
    try:
        record = invitations.issue_code(user_id)
    except RuntimeError:
        logger.exception(
            "issue_code failed for user=%s", user_id[:8] if user_id else "?"
        )
        reply_text(
            event.reply_token,
            "コードの発行に失敗しました🙇 少し時間を空けてもう一度お試しください。",
            quick_reply=main_menu_quick_reply("student"),
        )
        return

    code = record["code"]
    bubble = build_invitation_bubble(code, record["expires_at"])
    alt_text = f"🔑 保護者連携コード: {code}（24 時間有効）"
    reply_flex(
        event.reply_token,
        alt_text=alt_text,
        contents=bubble,
        quick_reply=invitation_menu_quick_reply(),
    )
    logger.info(
        "invitation_issued user=%s code_len=%d",
        user_id[:8] if user_id else "?",
        len(code),
    )


# ---------------------------------------------------------------------------
# Experience posting (FR-S6, 6-step dialog)
# ---------------------------------------------------------------------------


_POST_CATEGORY_LABELS: dict[str, str] = {
    value: label for label, value in POST_CATEGORIES
}
_POST_STEP_ORDER: tuple[str, ...] = (
    "post.category",
    "post.period",
    "post.summary",
    "post.learned",
    "post.regret",
    "post.advice",
    "post.area",
    "post.share_parent",
    "post.confirm",
    "post.title_edit",
)

# docs/04 §4.5: the five structured free-text steps that replaced the old
# single ``post.body`` blob. ``_POST_STEP_META`` drives validation/record,
# ``_POST_NEXT`` the transition, and ``_POST_ENTRY_PROMPTS`` the question
# shown when advancing INTO a step (the period question itself is emitted
# from the post.category branch). ``post.period`` records under
# ``period_raw``; the LLM produces the normalized ``period`` at finalize
# (T4.15, docs/06 §4.5).
_POST_TEXT_STEPS: frozenset[str] = frozenset(
    {"post.period", "post.summary", "post.learned", "post.regret", "post.advice"}
)
_POST_STEP_META: dict[str, dict[str, Any]] = {
    "post.period": {
        "key": "period_raw",
        "required": False,
        "max": posts.MAX_PERIOD_LEN,
    },
    "post.summary": {
        "key": "summary",
        "required": True,
        "max": posts.MAX_SUMMARY_LEN,
        "reprompt": "概要を 1 文字以上で入力してください。",
    },
    "post.learned": {
        "key": "learned",
        "required": True,
        "max": posts.MAX_LEARNED_LEN,
        "reprompt": "学べたことを 1 文字以上で入力してください。",
    },
    "post.regret": {"key": "regret", "required": False, "max": posts.MAX_REGRET_LEN},
    "post.advice": {"key": "advice", "required": False, "max": posts.MAX_ADVICE_LEN},
}
_POST_NEXT: dict[str, str] = {
    "post.period": "post.summary",
    "post.summary": "post.learned",
    "post.learned": "post.regret",
    "post.regret": "post.advice",
    "post.advice": "post.area",
}
_POST_AREA_PROMPT = (
    "📍 場所や店名を教えてください（例: 下鴨神社、進々堂 京大北門前）。\n"
    "場所がなければ「なし」または「skip」と送ってください。"
)
_POST_ENTRY_PROMPTS: dict[str, tuple[str, Any]] = {
    "post.summary": (
        "✏️ 何をしましたか？できごとの概要を教えてください。",
        cancel_quick_reply,
    ),
    "post.learned": (
        "💡 その経験で学べたこと・良かったことは何ですか？",
        cancel_quick_reply,
    ),
    "post.regret": (
        "😥 残念だったこと・注意しておくべき点はありますか？\n"
        "なければ「スキップ」と送ってください。",
        post_skip_quick_reply,
    ),
    "post.advice": (
        "📣 次に同じことをやる人へのアドバイスがあれば教えてください。\n"
        "なければ「スキップ」と送ってください。",
        post_skip_quick_reply,
    ),
    "post.area": (_POST_AREA_PROMPT, post_area_quick_reply),
}


def start_post_flow(event: MessageEvent | PostbackEvent) -> None:
    """Kick off the experience posting dialog for a student (docs/04 §4.5)."""
    user_id = event.source.user_id
    session.set_state(user_id, "post.category")
    reply_text(
        event.reply_token,
        (
            "✏️ 経験投稿を始めます。\n"
            "まずはカテゴリを選んでください。\n"
            "（途中で「キャンセル」と送るとやめられます）"
        ),
        quick_reply=post_category_quick_reply(),
    )


def handle_post_text(event: MessageEvent, state: dict[str, Any]) -> None:
    """Handle free-text input for the post flow's text steps.

    Covers the five structured steps in :data:`_POST_TEXT_STEPS` (period /
    summary / learned / regret / advice), ``post.area`` and the optional
    ``post.title_edit`` re-entry (T4.15). Quick Reply / Postback steps are
    nudged via :func:`_reprompt_post_step`.
    """
    user_id = event.source.user_id
    text = event.message.text.strip()
    step = state["state"]

    if step in _POST_TEXT_STEPS:
        _handle_post_field_text(event, step, text)
        return

    if step == "post.title_edit":
        if not text:
            reply_text(
                event.reply_token,
                "タイトルを 1 文字以上で入力してください。",
                quick_reply=cancel_quick_reply(),
            )
            return
        _record(user_id, "title", text[: posts.MAX_TITLE_LEN])
        _send_post_confirmation(event)
        return

    if step == "post.area":
        _record(user_id, "area", text)
        session.set_state(user_id, "post.share_parent", **_context_snapshot(user_id))
        reply_text(
            event.reply_token,
            (
                "\U0001f468‍\U0001f469‍\U0001f467 保護者に「頑張ったこと」として共有しますか？\n"
                "共有しないを選ぶと、この投稿は保護者には届きません。"
            ),
            quick_reply=post_share_parent_quick_reply(),
        )
        return

    if step in {"post.category", "post.share_parent", "post.confirm"}:
        # These are Quick Reply / Postback steps; nudge the user.
        _reprompt_post_step(event, step)
        return

    logger.warning("Unexpected post step for text input: %s", step)


def _handle_post_field_text(event: MessageEvent, step: str, text: str) -> None:
    """Record one structured field and advance to the next post step.

    Required steps (summary / learned) re-prompt on empty input.
    Skippable steps (period / regret / advice) map skip tokens to
    ``None`` via :func:`posts._normalize_skippable`. On success the next
    step's entry prompt (from :data:`_POST_ENTRY_PROMPTS`) is sent.
    """
    user_id = event.source.user_id
    meta = _POST_STEP_META[step]
    max_len: int = meta["max"]

    if meta["required"]:
        if not text:
            reply_text(
                event.reply_token,
                meta["reprompt"],
                quick_reply=cancel_quick_reply(),
            )
            return
        value: str | None = text[:max_len]
    else:
        normalized = posts._normalize_skippable(text)
        value = normalized[:max_len] if normalized is not None else None

    _record(user_id, meta["key"], value)
    next_state = _POST_NEXT[step]
    session.set_state(user_id, next_state, **_context_snapshot(user_id))
    prompt_text, quick_reply_factory = _POST_ENTRY_PROMPTS[next_state]
    reply_text(
        event.reply_token,
        prompt_text,
        quick_reply=quick_reply_factory(),
    )


def handle_post_postback(event: PostbackEvent, data: str) -> None:
    """Handle ``post:*`` postbacks for the experience posting flow."""
    user_id = event.source.user_id
    state = session.get_state(user_id)

    if state is None or not state["state"].startswith("post."):
        reply_text(
            event.reply_token,
            "セッションが切れました。もう一度「✏️ 経験を投稿」からやり直してください。",
            quick_reply=main_menu_quick_reply("student"),
        )
        return

    if data.startswith("post:category:"):
        category = data.removeprefix("post:category:")
        if category not in posts.CATEGORY_VALUES:
            reply_text(
                event.reply_token,
                "そのカテゴリには対応していません。",
                quick_reply=post_category_quick_reply(),
            )
            return
        _record(user_id, "category", category)
        session.set_state(user_id, "post.period", **_context_snapshot(user_id))
        reply_text(
            event.reply_token,
            (
                "🗓️ いつ・どのくらいの期間の話ですか？（例: 先週末、去年の10月）\n"
                "特になければ「スキップ」と送ってください。"
            ),
            quick_reply=post_skip_quick_reply(),
        )
        return

    if data.startswith("post:share:"):
        choice = data.removeprefix("post:share:")
        if choice not in {"yes", "no"}:
            reply_text(
                event.reply_token,
                "共有の選択肢は「共有する」か「共有しない」です。",
                quick_reply=post_share_parent_quick_reply(),
            )
            return
        _record(user_id, "share_with_parent", choice == "yes")
        _run_post_finalize(event)
        return

    if data == "post:title:edit":
        session.set_state(user_id, "post.title_edit", **_context_snapshot(user_id))
        reply_text(
            event.reply_token,
            f"✏️ 新しいタイトルを入力してください（{posts.MAX_TITLE_LEN} 文字以内）。",
            quick_reply=cancel_quick_reply(),
        )
        return

    if data == "post:confirm:yes":
        _finalize_post(event)
        return

    if data == "post:confirm:redo":
        session.clear_state(user_id)
        start_post_flow(event)
        return

    logger.warning("Unknown post postback: %s", data)


def _reprompt_post_step(event: MessageEvent, step: str) -> None:
    """Nudge the user to interact with the current post step's Quick Reply."""
    if step == "post.category":
        reply_text(
            event.reply_token,
            "下のメニューからカテゴリを選んでください。",
            quick_reply=post_category_quick_reply(),
        )
    elif step == "post.share_parent":
        reply_text(
            event.reply_token,
            "下のメニューで「共有する」か「共有しない」を選んでください。",
            quick_reply=post_share_parent_quick_reply(),
        )
    elif step == "post.confirm":
        reply_text(
            event.reply_token,
            "下のメニューで「投稿する」か「やり直す」を選んでください。",
            quick_reply=post_confirm_quick_reply(),
        )


def _build_post_confirmation_text(ctx: dict[str, Any]) -> str:
    """Render the review-card text from the collected post context.

    Shows the AI-generated title and the normalized period; when the raw
    words differ from the normalized value both are shown so the student
    can catch a bad normalization before posting (T4.15, docs/04 §4.5).
    """
    category_label = _POST_CATEGORY_LABELS.get(
        ctx.get("category", ""), ctx.get("category", "")
    )
    area_normalized = posts._normalize_area(ctx.get("area"))
    area_display = area_normalized if area_normalized is not None else "（指定なし）"
    share_label = "共有する" if ctx.get("share_with_parent", False) else "共有しない"

    def _field(value: str | None) -> str:
        return value if value else "（スキップ）"

    period = (ctx.get("period") or "").strip()
    period_raw = (ctx.get("period_raw") or "").strip()
    if period and period_raw and period != period_raw:
        period_display = f"{period}（元: {period_raw}）"
    elif period:
        period_display = period
    elif period_raw:
        period_display = period_raw
    else:
        period_display = "（スキップ）"

    return (
        "内容を確認してください:\n"
        f"📂 カテゴリ: {category_label}\n"
        f"📝 タイトル（AI 提案）: {ctx.get('title', '')}\n"
        f"🗓️ いつ: {period_display}\n"
        f"✏️ やったこと: {ctx.get('summary', '')}\n"
        f"💡 学び: {ctx.get('learned', '')}\n"
        f"😥 残念・注意: {_field(ctx.get('regret'))}\n"
        f"📣 次の人へ: {_field(ctx.get('advice'))}\n"
        f"📍 場所: {area_display}\n"
        f"\U0001f468‍\U0001f469‍\U0001f467 保護者共有: {share_label}\n\n"
        "この内容で投稿しますか？（タイトルは変更できます）"
    )


def _run_post_finalize(event: PostbackEvent) -> None:
    """Run the LLM finalize call, then push the confirmation card.

    Triggered right after the parent-share choice, when all fields are
    collected. Shows a Loading Indicator while ``gemini.finalize_post``
    generates the title and normalizes the period, then stores both in
    the session and pushes the review card (T4.15, docs/06 §4.5).
    ``finalize_post`` never raises for API problems, but we still guard
    defensively so the flow always reaches ``post.confirm``.
    """
    user_id = event.source.user_id
    ctx = _context_snapshot(user_id)
    show_loading(user_id)

    today = datetime.now(_JST).strftime("%Y-%m-%d")
    summary_text = ctx.get("summary", "")
    period_raw = ctx.get("period_raw")
    try:
        result = gemini.finalize_post(
            category=ctx.get("category", "other"),
            summary=summary_text,
            learned=ctx.get("learned", ""),
            regret=ctx.get("regret"),
            advice=ctx.get("advice"),
            area=ctx.get("area"),
            period_raw=period_raw,
            today=today,
        )
        title = result["title"]
        period = result["period"]
    except Exception:
        logger.exception("finalize_post failed; using fallback")
        title = (summary_text or "").strip()[: posts.MAX_TITLE_LEN]
        period = (period_raw or "").strip()

    _record(user_id, "title", title)
    _record(user_id, "period", period)
    ctx = _context_snapshot(user_id)
    session.set_state(user_id, "post.confirm", **ctx)
    push_text(
        user_id,
        _build_post_confirmation_text(ctx),
        quick_reply=post_confirm_quick_reply(),
    )


def _send_post_confirmation(event: PostbackEvent) -> None:
    """Re-show the review card via reply (used after a title edit)."""
    user_id = event.source.user_id
    ctx = _context_snapshot(user_id)
    session.set_state(user_id, "post.confirm", **ctx)
    reply_text(
        event.reply_token,
        _build_post_confirmation_text(ctx),
        quick_reply=post_confirm_quick_reply(),
    )


def _finalize_post(event: PostbackEvent) -> None:
    """Persist the post from session context and confirm to the student."""
    user_id = event.source.user_id
    ctx = _context_snapshot(user_id)
    try:
        record = posts.add_post(
            line_user_id=user_id,
            category=ctx.get("category", "other"),
            title=ctx.get("title", ""),
            summary=ctx.get("summary", ""),
            learned=ctx.get("learned", ""),
            area=ctx.get("area"),
            share_with_parent=bool(ctx.get("share_with_parent", False)),
            period=ctx.get("period"),
            period_raw=ctx.get("period_raw"),
            regret=ctx.get("regret"),
            advice=ctx.get("advice"),
        )
    except ValueError:
        logger.exception("posts.add_post rejected input")
        reply_text(
            event.reply_token,
            "投稿の保存に失敗しました🙇 少し時間を空けてもう一度お試しください。",
            quick_reply=main_menu_quick_reply("student"),
        )
        session.clear_state(user_id)
        return

    usage_stats.record(user_id, "post")
    session.clear_state(user_id)
    share_line = (
        "保護者に「頑張ったこと」として届きます✨"
        if record["share_with_parent"]
        else "この投稿は保護者には共有されません。"
    )
    reply_text(
        event.reply_token,
        f"投稿を保存しました🎉（{record['post_id']}）\n{share_line}",
        quick_reply=main_menu_quick_reply("student"),
    )
    logger.info(
        "post_finalized user=%s post_id=%s share=%s",
        user_id[:8],
        record["post_id"],
        record["share_with_parent"],
    )

    # FR-S10 (docs/04 §4.8): every third post awards a coupon batch. The
    # carousel is pushed after the reply, following the existing carousel
    # push convention. Awarding failures must never break the post flow.
    try:
        awarded = coupons.award_if_due(user_id)
        if awarded:
            push_flex(
                user_id,
                alt_text="🎫 クーポンが届きました",
                contents=build_coupon_carousel(awarded),
            )
    except Exception:
        logger.exception("coupon award failed; post itself is already saved")


# ---------------------------------------------------------------------------
# Public helper for the outer router (used by message.py to decide to skip)
# ---------------------------------------------------------------------------


def is_in_profile_flow(state: dict[str, Any] | None) -> bool:
    """Return ``True`` when ``state`` belongs to the profile registration flow."""
    return state is not None and state["state"].startswith("profile.")


def is_in_life_flow(state: dict[str, Any] | None) -> bool:
    """Return ``True`` when the user is in the life-consultation flow."""
    return state is not None and state["state"] == "life.waiting"


def is_in_post_flow(state: dict[str, Any] | None) -> bool:
    """Return ``True`` when the user is in the experience post flow."""
    return state is not None and state["state"] in _POST_STEP_ORDER
