"""Student-facing business flows.

This module owns the multi-turn dialog logic for a student user:
profile registration (Day 2), want-to-do consultation (Day 2), life
consultation (Day 2). Later days will add experience posting and
parent invitation code issuance.

The router entry points (``handlers/message.py`` and
``handlers/postback.py``) delegate here based on session state and
postback prefixes.
"""
import logging
from typing import Any

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
    gemini,
    profiles,
    prompts,
    session,
    users,
)
from src.services.line_reply import push_flex, push_text, reply_flex, reply_text
from src.templates.flex.activity_carousel import build_activity_carousel
from src.templates.quick_reply import (
    INTEREST_TAGS,
    confirm_quick_reply,
    effort_quick_reply,
    grade_quick_reply,
    interests_quick_reply,
    main_menu_quick_reply,
    profile_start_quick_reply,
)

logger = logging.getLogger(__name__)

MAX_TEXT_LEN = 200
MIN_INTERESTS = 1


# ---------------------------------------------------------------------------
# Entry: profile registration
# ---------------------------------------------------------------------------


def start_profile_flow(event: MessageEvent | PostbackEvent) -> None:
    """Kick off the profile registration flow."""
    user_id = event.source.user_id
    existing = profiles.get_profile(user_id)
    if existing:
        # allow re-registration but flag to the user
        reply_text(
            event.reply_token,
            "既に登録済みのプロフィールがあります。\nもう一度登録し直す場合、これまでの内容は上書きされます。\n\n🏫 大学名を教えてください（例: 同志社大学）",
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
            "学年は下のボタンから選んでください🎓",
            quick_reply=grade_quick_reply(),
        )
        return

    if step == "profile.interests":
        reply_text(
            event.reply_token,
            "興味のタグは下のボタンから選んでください（複数OK）。選び終わったら ✅ 完了 を押してください",
            quick_reply=interests_quick_reply(),
        )
        return

    if step == "profile.confirm":
        reply_text(
            event.reply_token,
            "下のボタンで「登録する」か「やり直す」を選んでください",
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
            "セッションが切れてしまいました。もう一度「プロフィール」と送ってやり直してください。",
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
                "セッションが切れました。もう一度「プロフィール」からやり直してください。",
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
    session.clear_state(user_id)

    role = users.get_role(user_id) or "student"
    reply_text(
        event.reply_token,
        "プロフィール登録完了です🎉\n\nメニューから使いたい機能を選んでください。\n（🎯 やりたいこと相談 は Day 2 完成、他は順次追加中）",
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


def handle_want_to_do(event: MessageEvent | PostbackEvent) -> None:
    """Trigger the "やりたいこと相談" flow (FR-S4)."""
    user_id = event.source.user_id
    profile = profiles.get_profile(user_id)
    if profile is None:
        reply_text(
            event.reply_token,
            "まずは 👤 プロフィール登録をお願いします。\nあなたに合った提案ができるようになります。",
            quick_reply=profile_start_quick_reply(),
        )
        return

    # Acknowledge immediately, then push the actual proposal so the
    # reply_token is not consumed while we wait for Gemini.
    reply_text(event.reply_token, "🤔 あなたに合いそうな活動を考えています…少しだけお待ちください")

    try:
        activities = gemini.propose_activities(profile)
    except Exception:
        logger.exception("propose_activities crashed")
        activities = []

    if not activities:
        push_text(
            user_id,
            "うまく提案を思いつけませんでした。少し時間を空けてもう一度お試しください🙇",
        )
        return

    keys = activity_store.remember(user_id, activities)
    session.set_state(user_id, "activity.viewing", activity_keys=keys)

    flex = build_activity_carousel(activities, keys)
    push_flex(
        user_id,
        alt_text="🎯 やりたいこと相談：あなたへのおすすめ",
        contents=flex,
    )
    push_text(
        user_id,
        "気になる提案があれば、カード内のボタンを押してください👇",
        quick_reply=_activity_quick_reply(),
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
    reply_text(event.reply_token, f"📖 「{activity.get('title', '')}」について調べています…")
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
    """Handle the "参加した" button (Day 2 acks only; Day 3 records to posts.json)."""
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
            "詳しい体験投稿は Day 3 で追加予定です。今日はここまでで OK です。"
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
    "警察への相談をおすすめします。\n"
    "・緊急: 110\n"
    "・相談: #9110"
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
        reply_text(event.reply_token, _EMERGENCY_LIFE_REPLY, quick_reply=_life_quick_reply())
        return
    if emergency == "medical":
        session.clear_state(user_id)
        reply_text(event.reply_token, _EMERGENCY_MEDICAL_REPLY, quick_reply=_life_quick_reply())
        return
    if emergency == "crime":
        session.clear_state(user_id)
        reply_text(event.reply_token, _EMERGENCY_CRIME_REPLY, quick_reply=_life_quick_reply())
        return

    reply_text(event.reply_token, "💭 少し考えます…")

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
        answer = "うまく答えを考えられませんでした。少し時間を空けてもう一度お試しください🙇"

    disclaimer_shown = zero_context
    medical_followup_shown = zero_context and medical_intent

    parts: list[str] = []
    if disclaimer_shown:
        parts.append(prompts.ZERO_CONTEXT_DISCLAIMER)
    parts.append(answer)
    if medical_followup_shown:
        parts.append(prompts.MEDICAL_FOLLOWUP)
    final = "".join(parts)

    logger.info(
        "life_consultation user=%s total_hits=%d zero_context=%s "
        "disclaimer_shown=%s medical_followup_shown=%s "
        "matched_categories=%s",
        user_id[:8] if user_id else "?",
        total_hits,
        zero_context,
        disclaimer_shown,
        medical_followup_shown,
        sorted(result["matched_categories"]),
    )

    push_text(user_id, final, quick_reply=_life_quick_reply())
    # Keep the session so follow-up questions are still routed to life consultation.
    session.set_state(user_id, "life.waiting")


# ---------------------------------------------------------------------------
# Public helper for the outer router (used by message.py to decide to skip)
# ---------------------------------------------------------------------------


def is_in_profile_flow(state: dict[str, Any] | None) -> bool:
    """Return ``True`` when ``state`` belongs to the profile registration flow."""
    return state is not None and state["state"].startswith("profile.")


def is_in_life_flow(state: dict[str, Any] | None) -> bool:
    """Return ``True`` when the user is in the life-consultation flow."""
    return state is not None and state["state"] == "life.waiting"
