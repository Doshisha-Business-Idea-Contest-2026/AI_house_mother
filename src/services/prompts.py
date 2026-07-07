"""Prompt templates for Gemini.

Centralising these strings keeps the AI behaviour reviewable in one
place. See ``docs/06_ai_spec.md`` for design notes.
"""
from typing import Any


SYSTEM_PROMPT_COMMON = """あなたは「AI寮母」という LINE Bot のアシスタントです。
京都・同志社大学周辺の学生マンションに住む学生と、その保護者をサポートします。

以下のルールを厳守してください:

【禁止事項】
- 医療行為の診断や処方をしない。症状の説明を受けたら「症状が続くなら医療機関を受診してください」に誘導する。
- 法律相談に断定的に答えない。「弁護士や行政窓口に相談してください」と誘導する。
- 緊急事態（119/110 事案）は即座に該当窓口を案内する。
- 実在する店舗・病院・施設について、古い情報の可能性があることを一言添える。
- ユーザー本人が登録した情報以外の個人情報を漏らさない。
- 情報源（`data/seed/*.json`）に存在しない具体情報（電話番号、営業時間、特定店舗名、特定日程）を断定しない。
- 情報源に該当が無い場合は、必ず公式窓口や #7119 等の一般的な連絡先へ誘導する。

【トーン】
- 親しみやすい寮母のような語り口（ですます調、絵文字は控えめに 1〜2 個）。
- 学生には気さくに、保護者には丁寧に。
- 断定を避け、選択肢を示す。

【情報源】
- ユーザーのプロフィール、地域情報、先輩投稿（seed）、および他の学生が投稿した経験（匿名）を参照して回答する。
- 情報がない場合は「わからない」と正直に答える。
- 参照した先輩投稿・学生投稿がある場合、「先輩の体験より」と注記する。
- 学生投稿は匿名情報として提供されるので、投稿者の名前・学年・大学などを推測して記載しない。
"""


# See docs/06_ai_spec.md §5.3.4. Prepend to any Zero-context reply so
# the user knows the bot lacks a real source for this topic.
ZERO_CONTEXT_DISCLAIMER = (
    "ごめんなさい、この話題については先輩の投稿や地域の情報がまだ届いていません🙏\n"
    "以下は一般的なご案内なので、正確な情報は公式窓口でご確認くださいね。\n\n"
)


# Appended to a Zero-context reply when the message hints at a medical
# topic (see docs/06_ai_spec.md §5.3.5).
MEDICAL_FOLLOWUP = (
    "\n\n体調のご相談は #7119（京都府救急安心センター）でも相談できますよ。\n"
    "京都市の医療機関検索サイトも参考になります。"
)


def _summarise_profile(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "（未登録）"
    interests = " / ".join(profile.get("interests") or []) or "（未設定）"
    return (
        f"- 大学: {profile.get('university', '(未設定)')}\n"
        f"- 学部: {profile.get('faculty', '(未設定)')}\n"
        f"- 学年: {profile.get('grade', '(未設定)')}\n"
        f"- 興味: {interests}\n"
        f"- 最近頑張っていること: {profile.get('recent_effort') or '(未設定)'}\n"
        f"- やってみたいこと: {profile.get('want_to_do') or '(未設定)'}"
    )


def _summarise_areas(areas: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"- {a['name']} ({a.get('category', '')}): {a.get('description', '')}"
        for a in areas
    )


def _summarise_stores(stores: list[dict[str, Any]]) -> str:
    if not stores:
        return "（該当なし）"
    return "\n".join(
        f"- {s['name']} ({s.get('category', '')}, {s.get('area', '')}): {s.get('description', '')}"
        for s in stores
    )


def _summarise_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "（該当なし）"
    return "\n".join(
        f"- {e['name']} ({e.get('category', '')}, {e.get('area', '')}): {e.get('description', '')} 日程: {e.get('schedule', '')}"
        for e in events
    )


def _summarise_senior_posts(posts: list[dict[str, Any]]) -> str:
    if not posts:
        return "（該当なし）"
    return "\n".join(
        f"- {p.get('author_pseudonym', '先輩')}「{p.get('title', '')}」: {p.get('body', '')[:200]}"
        for p in posts
    )


def _summarise_student_posts(posts: list[dict[str, Any]]) -> str:
    """Format anonymized student posts for the life-consultation prompt.

    Only the allow-listed fields (title / body / area / category /
    created_at) from :func:`posts.list_all_for_context` are shown here.
    Nothing that could point back to an author is added — no user id,
    no profile snippet, no post_id.
    """
    if not posts:
        return "（該当なし）"
    lines: list[str] = []
    for p in posts:
        title = p.get("title", "")
        body_preview = (p.get("body") or "")[:200]
        area = p.get("area") or ""
        category = p.get("category") or ""
        header = f"- 【{category}】「{title}」"
        if area:
            header += f" (場所: {area})"
        lines.append(f"{header}\n  → {body_preview}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Function-level prompt builders
# ---------------------------------------------------------------------------


def build_activity_prompt(
    profile: dict[str, Any] | None,
    areas: list[dict[str, Any]],
    stores: list[dict[str, Any]],
    events: list[dict[str, Any]],
    senior_posts: list[dict[str, Any]],
) -> str:
    """Prompt used by ``propose_activities``."""
    return (
        SYSTEM_PROMPT_COMMON
        + "\n\n【今回の依頼】\n"
        "学生から「何かやりたい」と相談を受けています。\n"
        "以下のプロフィールと地域データから、2〜3 件の活動を提案してください。\n\n"
        "【学生プロフィール】\n"
        + _summarise_profile(profile)
        + "\n\n【地域情報】\n"
        + _summarise_areas(areas)
        + "\n\n【学生向け店舗（興味に応じて抽出）】\n"
        + _summarise_stores(stores)
        + "\n\n【地域イベント・ボランティア（全件）】\n"
        + _summarise_events(events)
        + "\n\n【関連する先輩投稿】\n"
        + _summarise_senior_posts(senior_posts)
        + "\n\n【出力形式】\n"
        "以下の JSON 配列のみを返してください。各要素は必ず title/summary/why_recommend/reference_type を含めます。\n"
        "reference_type は event/volunteer/store/senior_post/generated のいずれか。\n"
        "2〜3 件、必ず出力してください。\n"
    )


def build_life_consultation_prompt(
    profile: dict[str, Any] | None,
    user_message: str,
    stores: list[dict[str, Any]],
    areas: list[dict[str, Any]],
    senior_posts: list[dict[str, Any]],
    student_posts: list[dict[str, Any]],
    *,
    total_hits: int,
) -> str:
    """Prompt used by ``answer_life_question``.

    ``student_posts`` are the anonymized runtime posts from
    :func:`posts.list_all_for_context`. The prompt injects them as
    "同じマンションの学生の経験投稿" and instructs Gemini to quote them
    without inferring the author (see docs/06_ai_spec.md §4.2).

    When ``total_hits == 0`` the prompt includes an explicit constraint
    that forbids Gemini from fabricating phone numbers, opening hours,
    or specific store names (see docs/06_ai_spec.md §5.3).
    """
    zero_context = total_hits == 0
    zero_context_line = (
        "- **total_hits が 0 なので情報源に該当がありません。地名・電話番号・"
        "営業時間・特定の店舗名を絶対に断定せず、一般論のみで答え、"
        "必ず『詳細は公式窓口でご確認ください』と誘導してください。**\n"
        if zero_context
        else ""
    )

    return (
        SYSTEM_PROMPT_COMMON
        + "\n\n【今回の依頼】\n"
        "学生から生活相談が届きました。地域情報・先輩投稿・過去の学生投稿を参照して回答してください。\n\n"
        "【学生プロフィール】\n"
        + _summarise_profile(profile)
        + "\n\n【関連情報の件数】\n"
        f"- stores: {len(stores)} 件\n"
        f"- areas: {len(areas)} 件\n"
        f"- senior_posts: {len(senior_posts)} 件\n"
        f"- student_posts: {len(student_posts)} 件\n"
        f"- total_hits: {total_hits} 件\n"
        + "\n【関連する店舗】\n"
        + _summarise_stores(stores)
        + "\n\n【関連する地域情報】\n"
        + _summarise_areas(areas)
        + "\n\n【関連する先輩投稿】\n"
        + _summarise_senior_posts(senior_posts)
        + "\n\n【同じマンションの学生の経験投稿（匿名）】\n"
        + _summarise_student_posts(student_posts)
        + f"\n\n【学生の発言】\n{user_message}\n\n"
        "【回答時の注意】\n"
        "- 参照した先輩投稿・学生投稿がある場合、「先輩の体験より: ...」と 1 文添える。\n"
        "- 学生投稿は匿名情報なので、投稿者の名前・学年・大学などを推測して記載しない。\n"
        "- 医療的な内容なら「症状が続く場合は医療機関を受診してください」を必ず含める。\n"
        "- 緊急を疑う場合は #7119（京都府救急安心センター）や 119 を案内する。\n"
        "- 実在の店舗・病院名は「情報が古い可能性があります」と注記する。\n"
        "- 300 文字以内でまとめる。\n"
        + zero_context_line
        + "\n回答:"
    )


def build_activity_detail_prompt(
    profile: dict[str, Any] | None, activity: dict[str, Any]
) -> str:
    """Prompt used by ``answer_activity_detail`` (Flex card follow-up)."""
    return (
        SYSTEM_PROMPT_COMMON
        + "\n\n【今回の依頼】\n"
        "学生が以下の活動について詳しく知りたがっています。\n\n"
        "【対象活動】\n"
        f"タイトル: {activity.get('title', '')}\n"
        f"概要: {activity.get('summary', '')}\n"
        f"場所: {activity.get('location', '不明')}\n"
        f"時期: {activity.get('when', '不明')}\n"
        f"種別: {activity.get('reference_type', '')}\n\n"
        "【学生プロフィール】\n"
        + _summarise_profile(profile)
        + "\n\n【回答時の注意】\n"
        "- どうやって参加するか、準備物、注意点を簡潔にまとめる。\n"
        "- 情報がない部分は「担当者に問い合わせてみてください」と誘導する。\n"
        "- 300 文字以内。\n\n"
        "回答:"
    )
