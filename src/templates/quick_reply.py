"""Quick Reply builders shared across handlers.

Every builder returns a ``linebot.v3.messaging.QuickReply`` ready to be
attached to a ``TextMessage`` or ``FlexMessage``.
"""
from linebot.v3.messaging import (
    MessageAction,
    PostbackAction,
    QuickReply,
    QuickReplyItem,
)


# ---------------------------------------------------------------------------
# Reusable option data
# ---------------------------------------------------------------------------

INTEREST_TAGS: list[str] = [
    "地域活動",
    "ボランティア",
    "スポーツ",
    "音楽",
    "アート",
    "学問・研究",
    "ものづくり",
    "起業・ビジネス",
    "国際交流",
    "食・カフェ巡り",
]

GRADES: list[str] = ["1", "2", "3", "4", "M1", "M2"]


# ---------------------------------------------------------------------------
# Menu / navigation
# ---------------------------------------------------------------------------


def main_menu_quick_reply(role: str) -> QuickReply:
    """Return the top-level menu for the given ``role`` (student/parent)."""
    if role == "student":
        items = [
            QuickReplyItem(
                action=PostbackAction(
                    label="🎯 やりたいこと相談",
                    data="menu:want_to_do",
                    display_text="🎯 やりたいこと相談",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="💬 生活相談",
                    data="menu:life",
                    display_text="💬 生活相談",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="✏️ 経験を投稿",
                    data="menu:post",
                    display_text="✏️ 経験を投稿",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="👤 プロフィール",
                    data="menu:profile",
                    display_text="👤 プロフィール",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="👨\u200d👩\u200d👧 保護者連携",
                    data="menu:invite",
                    display_text="👨\u200d👩\u200d👧 保護者連携",
                )
            ),
            QuickReplyItem(
                action=MessageAction(label="❓ ヘルプ", text="ヘルプ")
            ),
        ]
    else:  # parent
        items = [
            QuickReplyItem(
                action=PostbackAction(
                    label="📊 今月のレポート",
                    data="menu:monthly_report",
                    display_text="📊 今月のレポート",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="🔗 学生と連携",
                    data="menu:link_student",
                    display_text="🔗 学生と連携",
                )
            ),
            QuickReplyItem(
                action=MessageAction(label="❓ ヘルプ", text="ヘルプ")
            ),
        ]
    return QuickReply(items=items)


def cancel_quick_reply() -> QuickReply:
    """A single 「キャンセル」 button for use during flows."""
    return QuickReply(
        items=[QuickReplyItem(action=MessageAction(label="🚫 キャンセル", text="キャンセル"))]
    )


# ---------------------------------------------------------------------------
# Profile flow
# ---------------------------------------------------------------------------


def profile_start_quick_reply() -> QuickReply:
    """Quick Reply shown right after role selection for students."""
    return QuickReply(
        items=[
            QuickReplyItem(
                action=PostbackAction(
                    label="✍️ プロフィールを登録",
                    data="menu:profile_start",
                    display_text="✍️ プロフィールを登録",
                )
            ),
            QuickReplyItem(
                action=MessageAction(label="あとで登録する", text="あとで")
            ),
        ]
    )


def grade_quick_reply() -> QuickReply:
    """Quick Reply listing supported grade options."""
    items: list[QuickReplyItem] = []
    labels = {
        "1": "🎓 1 年",
        "2": "🎓 2 年",
        "3": "🎓 3 年",
        "4": "🎓 4 年",
        "M1": "🎓 院 1",
        "M2": "🎓 院 2",
    }
    for grade in GRADES:
        items.append(
            QuickReplyItem(
                action=PostbackAction(
                    label=labels[grade],
                    data=f"profile:grade:{grade}",
                    display_text=labels[grade],
                )
            )
        )
    items.append(
        QuickReplyItem(action=MessageAction(label="🚫 キャンセル", text="キャンセル"))
    )
    return QuickReply(items=items)


def interests_quick_reply() -> QuickReply:
    """Quick Reply for interest-tag selection with a 完了 button.

    Only 13 items are allowed in a Quick Reply; we send 10 tags plus
    a done button plus a cancel button (12 total).
    """
    items: list[QuickReplyItem] = []
    for tag in INTEREST_TAGS:
        items.append(
            QuickReplyItem(
                action=PostbackAction(
                    label=tag,
                    data=f"profile:interest:{tag}",
                    display_text=tag,
                )
            )
        )
    items.append(
        QuickReplyItem(
            action=PostbackAction(
                label="✅ 完了",
                data="profile:interest_done",
                display_text="✅ 完了",
            )
        )
    )
    items.append(
        QuickReplyItem(action=MessageAction(label="🚫 キャンセル", text="キャンセル"))
    )
    return QuickReply(items=items)


def effort_quick_reply() -> QuickReply:
    """Quick Reply for the recent-effort step (allows skipping)."""
    return QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label="スキップ", text="スキップ")),
            QuickReplyItem(action=MessageAction(label="🚫 キャンセル", text="キャンセル")),
        ]
    )


def confirm_quick_reply() -> QuickReply:
    """Quick Reply used to confirm or restart the profile flow."""
    return QuickReply(
        items=[
            QuickReplyItem(
                action=PostbackAction(
                    label="✅ 登録する",
                    data="profile:confirm:yes",
                    display_text="✅ 登録する",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="🔄 やり直す",
                    data="profile:confirm:redo",
                    display_text="🔄 やり直す",
                )
            ),
            QuickReplyItem(action=MessageAction(label="🚫 キャンセル", text="キャンセル")),
        ]
    )


# ---------------------------------------------------------------------------
# Experience posting flow (student side)
# ---------------------------------------------------------------------------


POST_CATEGORIES: list[tuple[str, str]] = [
    ("🏛️ 地域イベント", "event"),
    ("🧹 ボランティア", "volunteer"),
    ("🍜 お店・カフェ", "store"),
    ("🏥 病院・薬局", "medical"),
    ("📋 手続き・生活の知恵", "tips"),
    ("✨ その他", "other"),
]


def post_category_quick_reply() -> QuickReply:
    """Quick Reply listing the 6 post categories + cancel."""
    items: list[QuickReplyItem] = []
    for label, value in POST_CATEGORIES:
        items.append(
            QuickReplyItem(
                action=PostbackAction(
                    label=label,
                    data=f"post:category:{value}",
                    display_text=label,
                )
            )
        )
    items.append(
        QuickReplyItem(action=MessageAction(label="🚫 キャンセル", text="キャンセル"))
    )
    return QuickReply(items=items)


def post_area_quick_reply() -> QuickReply:
    """Quick Reply offering to skip the area step or cancel."""
    return QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label="なし", text="なし")),
            QuickReplyItem(action=MessageAction(label="🚫 キャンセル", text="キャンセル")),
        ]
    )


def post_share_parent_quick_reply() -> QuickReply:
    """Quick Reply asking whether to share the post with linked parents."""
    return QuickReply(
        items=[
            QuickReplyItem(
                action=PostbackAction(
                    label="\U0001F468‍\U0001F469‍\U0001F467 共有する",
                    data="post:share:yes",
                    display_text="\U0001F468‍\U0001F469‍\U0001F467 共有する",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="🙅 共有しない",
                    data="post:share:no",
                    display_text="🙅 共有しない",
                )
            ),
            QuickReplyItem(
                action=MessageAction(label="🚫 キャンセル", text="キャンセル")
            ),
        ]
    )


def post_confirm_quick_reply() -> QuickReply:
    """Quick Reply used at the final review step of the post flow."""
    return QuickReply(
        items=[
            QuickReplyItem(
                action=PostbackAction(
                    label="✅ 投稿する",
                    data="post:confirm:yes",
                    display_text="✅ 投稿する",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="🔄 やり直す",
                    data="post:confirm:redo",
                    display_text="🔄 やり直す",
                )
            ),
            QuickReplyItem(
                action=MessageAction(label="🚫 キャンセル", text="キャンセル")
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Invitation flow (student side)
# ---------------------------------------------------------------------------


def invitation_menu_quick_reply() -> QuickReply:
    """Quick Reply attached to the invitation code delivery message.

    Lets the student re-issue a fresh code (invalidating the previous
    pending one) or jump back to the main menu without triggering a
    life-consultation Gemini call by accident.
    """
    return QuickReply(
        items=[
            QuickReplyItem(
                action=PostbackAction(
                    label="🔄 新しいコードを発行",
                    data="invite:regenerate",
                    display_text="新しいコードを発行",
                )
            ),
            QuickReplyItem(
                action=PostbackAction(
                    label="🏠 メインメニュー",
                    data="menu:main",
                    display_text="メインメニュー",
                )
            ),
        ]
    )
