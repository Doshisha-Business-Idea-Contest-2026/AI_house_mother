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
        f" [情報鮮度: {a.get('last_verified_at', '不明')}]"
        for a in areas
    )


def _summarise_stores(stores: list[dict[str, Any]]) -> str:
    if not stores:
        return "（該当なし）"
    return "\n".join(
        f"- {s['name']} ({s.get('category', '')}, {s.get('area', '')}): {s.get('description', '')}"
        f" [情報鮮度: {s.get('data_freshness_note', '不明')}]"
        for s in stores
    )


def _summarise_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "（該当なし）"
    return "\n".join(
        f"- {e['name']} ({e.get('category', '')}, {e.get('area', '')}): {e.get('description', '')} 日程: {e.get('schedule', '')}"
        f" [情報鮮度: {e.get('last_verified_at', '不明')}]"
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
        SYSTEM_PROMPT_COMMON + "\n\n【今回の依頼】\n"
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


def build_student_efforts_prompt(
    profile: dict[str, Any] | None,
    senior_posts: list[dict[str, Any]],
    student_posts: list[dict[str, Any]],
) -> str:
    """Prompt used by ``propose_from_student_efforts`` (docs/06 §4.1.1).

    ``student_posts`` are the anonymized runtime posts from
    :func:`posts.list_all_for_context`. Senior posts expose only
    ``author_pseudonym``. The output schema matches
    :func:`build_activity_prompt`, but the material is limited to what
    other students / seniors have actually done, and ``reference_type``
    is constrained to ``senior_post`` / ``generated``.
    """
    return (
        SYSTEM_PROMPT_COMMON + "\n\n【今回の依頼】\n"
        "学生が「ほかの学生の取り組みを知りたい」と言っています。\n"
        "以下の先輩投稿と、同じマンションの学生の経験投稿（匿名）を素材に、\n"
        "その学生が真似したり参加したりできる活動を 2〜3 件提案してください。\n\n"
        "【学生プロフィール】\n"
        + _summarise_profile(profile)
        + "\n\n【先輩の体験投稿】\n"
        + _summarise_senior_posts(senior_posts)
        + "\n\n【同じマンションの学生の経験投稿（匿名）】\n"
        + _summarise_student_posts(student_posts)
        + "\n\n【出力形式】\n"
        "以下の JSON 配列のみを返してください。各要素は必ず title/summary/why_recommend/"
        "reference_type を含めます。\n"
        "reference_type は素材由来なら senior_post、AI が組み立てた場合は generated。\n"
        "学生投稿は匿名情報なので、投稿者の名前・学年・大学などを推測して記載しないでください。\n"
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
        SYSTEM_PROMPT_COMMON + "\n\n【今回の依頼】\n"
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
        "- 実在の店舗・病院・施設を挙げる場合は、上記【関連する店舗】/【関連する地域情報】の各行末の\n"
        "  [情報鮮度: ...] の値をそのまま抜き出し、「※ (値)」の形で末尾に 1 文添える。\n"
        "  例: 「※2026-07 時点の情報。営業状況は変わっている可能性があります」\n"
        "- 300 文字以内でまとめる。\n" + zero_context_line + "\n【回答書式】\n"
        "- 冒頭の 1 文で結論・要点を先に述べる（結論先出し）。\n"
        "- 候補・手順・注意点が複数ある場合は行頭「・」の箇条書きにする。\n"
        "- Markdown 記号（-, *, #, **）は使わない。LINE は装飾を表示せず記号がそのまま残る。\n"
        "- 結論・箇条書き・締めのブロックの間は空行 1 つで区切る。\n" + "\n回答:"
    )


def build_activity_detail_prompt(
    profile: dict[str, Any] | None, activity: dict[str, Any]
) -> str:
    """Prompt used by ``answer_activity_detail`` (Flex card follow-up)."""
    return (
        SYSTEM_PROMPT_COMMON + "\n\n【今回の依頼】\n"
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


def build_month_summary_prompt(
    profile: dict[str, Any] | None,
    year_month: str,
    posts: list[dict[str, Any]],
    usage: dict[str, int],
) -> str:
    """Prompt for the AI 寮母 monthly report closing message (FR-P3).

    Args:
        profile: The student profile (may be ``None``).
        year_month: Target month in ``"YYYY-MM"``.
        posts: Current-month shared posts (only ``title`` is used to
            avoid duplicating the 60-char body preview shown on the Flex).
        usage: Current-month counters (``life`` / ``activity`` / ``post``
            / ``profile``, missing keys treated as 0).

    Returns:
        Prompt string ready for ``gemini.call_gemini``.
    """
    if posts:
        titles = "\n".join(f"- {p.get('title', '').strip()}" for p in posts)
    else:
        titles = "- （今月は共有された投稿がありません）"

    life = int(usage.get("life", 0))
    activity = int(usage.get("activity", 0))
    post_count = int(usage.get("post", 0))
    profile_count = int(usage.get("profile", 0))

    return (
        SYSTEM_PROMPT_COMMON + "\n\n【今回の依頼】\n"
        "保護者向けの月次レポートに添える、AI 寮母からの温かい 2〜3 文の総括を書いてください。\n\n"
        "【学生プロフィール（参考）】\n"
        + _summarise_profile(profile)
        + f"\n\n【対象月】{year_month}\n"
        "【当月に共有された頑張ったことのタイトル】\n"
        f"{titles}\n\n"
        "【当月の利用状況】\n"
        f"- 生活相談: {life}回\n"
        f"- やりたいこと相談: {activity}回\n"
        f"- 経験投稿: {post_count}回\n"
        f"- プロフィール更新: {profile_count}回\n\n"
        "【出力ルール】\n"
        "- 2〜3 文、合計 120 文字以内。プレーンテキストのみ（絵文字・箇条書き・見出しは使わない）。\n"
        "- 「〜な様子です」「〜されているようです」など推測の語尾を使い、断定しない。\n"
        "- 具体的な事実に触れて良いのは投稿タイトルまたは相談回数のいずれか 1 点まで。\n"
        "- 数値の解釈は前向きに（0 回でも「今月は静かに過ごされているようです」など）。\n"
        "- 医療診断、法律断定、緊急対応判断、成績評価、進路助言は書かない。\n"
        "- プロフィール以外の個人情報は書かない。\n\n"
        "総括:"
    )


def build_post_finalize_prompt(
    category: str,
    summary: str,
    learned: str,
    regret: str | None,
    advice: str | None,
    area: str | None,
    period_raw: str | None,
    today: str,
) -> str:
    """Prompt for ``gemini.finalize_post`` (FR-S6 / T4.15).

    Asks the model to (1) generate a concise title from the student's
    structured post, (2) normalize the free-text period into an absolute
    expression anchored on ``today``, and (3) judge the post's validity
    (``valid`` / ``reason``) so nonsensical / fabricated / lottery-farming
    posts can be rejected without an extra call. See ``docs/06_ai_spec.md``
    §4.5.

    Args:
        category: Post category value.
        summary: What happened (required).
        learned: What was learned (required).
        regret: Disappointment / caveats, or ``None`` if skipped.
        advice: Advice for the next person, or ``None`` if skipped.
        area: Free-text location, or ``None``.
        period_raw: The user's raw period words (e.g. "去年の10月"), or
            ``None`` if skipped.
        today: Reference date in ``"YYYY-MM-DD"`` (JST) used to resolve
            relative period expressions.

    Returns:
        Prompt string ready for ``gemini.finalize_post``.
    """

    def _or_none(value: str | None) -> str:
        text = (value or "").strip()
        return text if text else "（なし）"

    return (
        SYSTEM_PROMPT_COMMON + "\n\n【今回の依頼】\n"
        "学生の経験投稿から、(1) 40 文字以内の短いタイトル、(2) 期間表現の絶対化、"
        "(3) 投稿内容の妥当性判定、を行ってください。\n\n"
        f"【今日の日付】{today}（この日付を基準に相対表現を絶対表現へ変換する）\n\n"
        "【投稿内容】\n"
        f"- カテゴリ: {category}\n"
        f"- 期間（ユーザーの言葉）: {_or_none(period_raw)}\n"
        f"- 概要: {_or_none(summary)}\n"
        f"- 学び: {_or_none(learned)}\n"
        f"- 残念・注意: {_or_none(regret)}\n"
        f"- 次の人へ: {_or_none(advice)}\n"
        f"- 場所: {_or_none(area)}\n\n"
        "【出力ルール】\n"
        "- 必ず JSON オブジェクトのみを返す: "
        '{"title": "...", "period": "...", "valid": true, "reason": "..."}\n'
        "- title: 内容を表す簡潔な見出し。40 文字以内。絵文字・記号での装飾はしない。\n"
        "- period: 期間（ユーザーの言葉）を今日の日付基準で絶対表現へ変換する"
        "（例: 「去年の10月」→「2025年10月」、「先週末」→「2026年7月上旬」）。\n"
        "  期間が（なし）のときは空文字にする。判断できない相対表現（「大学1年の頃」等）は"
        "無理に断定せず、元の表現に近い形で返す。\n"
        "- valid: 投稿として妥当なら true、不正なら false（真偽値）。\n"
        "  false にするのは次のいずれかが明白な場合のみ: 単一文字の連打やキーボード乱打・"
        "意味をなさない文字列、荒唐無稽で明らかに虚偽の内容、中身の伴わない抽選/クーポン目的"
        "と判断できる投稿。\n"
        "  短くても内容が伴っていれば true。判断に迷う場合は必ず true（正当な投稿を弾かない）。\n"
        "- reason: valid が false のときのみ、日本語で簡潔に理由を書く（true のときは空文字）。\n"
        "- 投稿内容以外の事実を創作しない。個人を特定する情報は書かない。"
    )
