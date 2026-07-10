# 06. AI 仕様

## 1. このドキュメントの目的

Gemini 2.0 Flash-Lite を用いた AI 機能の仕様を定義する。

- 使用モデル・呼び出し方式
- System Prompt 設計
- 各機能別のプロンプトテンプレート
- 回答制約（NG トピック）
- コスト・パフォーマンス設計
- エラー時のフォールバック

## 2. 使用モデル

### 2.1 モデル選定

- **モデル**: `gemini-2.0-flash-lite`
- **提供元**: Google AI Studio
- **理由**:
  - 無料枠が広い（コスト最重視）
  - 日本語応答の品質が実用水準
  - 応答レイテンシが低い（3〜5 秒目安）
  - Flash 系列は low-cost バリアントであり MVP 用途に最適

### 2.2 SDK

- `google-generativeai` の Python SDK を使用
- `pip install google-generativeai`

### 2.3 認証

- API キーは `.env` から `GEMINI_API_KEY` として読み込む
- グローバル規約により、API クライアントインスタンス名は `cl` を使う

```python
import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)
cl = genai.GenerativeModel("gemini-2.0-flash-lite")
```

### 2.4 呼び出しパラメータ

| パラメータ | 値 | 理由 |
| --- | --- | --- |
| `temperature` | 0.7 | 提案系は多様性、相談系は決定性のバランス |
| `top_p` | 0.9 | デフォルト |
| `max_output_tokens` | 800 | LINE メッセージ 300 文字 + Flex Message データが収まる範囲 |
| `timeout` (text / 対話 JSON) | 15 秒 | LINE Webhook 30 秒制約に対する安全マージン。`call_gemini` および `answer_life_question` の JSON 応答（`DEFAULT_TIMEOUT_S`） |
| `timeout` (propose_activities / propose_from_student_efforts) | 20 秒 | 800 output tokens の JSON 応答用に少し余裕を持たせる（`_PROPOSE_TIMEOUT_S`） |
| `timeout` (`summarize_month`) | 30 秒 | 月次バッチは systemd timer 起動で Webhook 外のため長め（`_BATCH_TIMEOUT_S`） |
| `timeout` (`finalize_post`) | 8 秒 | 確認カード前のインライン処理。既定より厳しめ（`_FINALIZE_TIMEOUT_S`） |

用途別に微調整する（下記各節参照）。**リトライは行わない**（§6.3）。

## 3. System Prompt 共通部分

すべての Gemini 呼び出しに前置きする共通 System Prompt。

```
あなたは「AI寮母」という LINE Bot のアシスタントです。
京都・同志社大学周辺の学生マンションに住む学生と、その保護者をサポートします。

以下のルールを厳守してください:

【禁止事項】
- 医療行為の診断や処方をしない。症状の説明を受けたら「症状が続くなら医療機関を受診してください」に誘導する。
- 法律相談に断定的に答えない。「弁護士や行政窓口に相談してください」と誘導する。
- 緊急事態（119/110 事案）は即座に該当窓口を案内する。
- **seed の areas / stores / events は同志社今出川周辺の実在情報**。回答に含める際は、レコードの `data_freshness_note` または `last_verified_at` を参照し、「◯年◯月時点の情報のため、営業状況等が変わっている可能性があります」旨を必ず一言添える（NFR-Truth-4）。
- ユーザー本人が登録した情報以外の個人情報を漏らさない。
- 情報源（`data/seed/*.json`）に存在しない具体情報（電話番号、営業時間、特定店舗名、特定日程）を断定しない。
- 情報源に該当が無い場合は、必ず公式窓口や #7119 等の一般的な連絡先へ誘導する。

【トーン】
- 親しみやすい寮母のような語り口（ですます調、絵文字は控えめに 1〜2 個）。
- 学生には気さくに、保護者には丁寧に。
- 断定を避け、選択肢を示す。

【情報源】
- ユーザーのプロフィール、地域情報、先輩投稿（seed）、および他の学生が投稿した経験（ランタイム `posts.json`）を参照して回答する。
- 情報がない場合は「わからない」と正直に答える。
- 参照した先輩投稿・学生投稿がある場合、「先輩の体験より」と注記する。**投稿者を特定・推測しない**（匿名化して渡す。詳細は §5.3）。

【出力形式】
- 通常はテキストで簡潔に（200〜300 文字目安）。
- LINE は Markdown を表示しないので `#`/`**`/`-`/`*` 等の記号装飾を使わない。強調は文章で表現し、箇条書きは行頭「・」で書く。
- 提案系の依頼では JSON 形式で返答（別途指示があった場合）。
```

## 4. 機能別プロンプト

### 4.1 やりたいこと相談（FR-S4）

**目的**: 学生プロフィールと地域データから 2〜3 件の活動を提案し、JSON で返す。

**呼び出しコンテキスト**:
- 学生プロフィール
- 地域情報（`areas.json`）
- 店舗情報（`stores.json`）
- イベント情報（`events.json`）
- 先輩投稿の一部（`senior_posts.json`）
- 直近の会話履歴（あれば）

**プロンプト構造**:

```
{system_prompt_common}

【今回の依頼】
学生から「何かやりたい」と相談を受けています。
以下のプロフィールと地域データから、2〜3 件の活動を提案してください。

【学生プロフィール】
- 大学: {university}
- 学部: {faculty}
- 学年: {grade}
- 興味: {interests}
- 最近頑張っていること: {recent_effort}
- やってみたいこと: {want_to_do}

【地域情報】
{areas_summary}

【店舗情報】
{stores_summary}

【イベント・ボランティア】
{events_summary}

【先輩の体験投稿（参考）】
{senior_posts_summary}

【出力形式】
以下の JSON 配列のみを返してください。前置きや説明は不要です。

[
    {
        "title": "活動名（40文字以内）",
        "summary": "概要（2 文程度、120 文字以内）",
        "location": "場所（あれば）",
        "when": "時期・頻度（あれば）",
        "why_recommend": "なぜこの学生に合うか（1 文、80 文字以内）",
        "reference_type": "event" | "volunteer" | "store" | "senior_post" | "generated"
    }
]

2〜3 件、必ず出力してください。
```

`reference_type` の値の詳細（`static_fallback` を含む全 6 種）は `docs/05_data_model.md` §7 を参照。

**呼び出し後の処理**:
- JSON パース失敗時はテキスト応答にフォールバック
- 2 件未満の場合は追加で 1 件を生成型 (`"reference_type": "generated"`) で補完
- 各提案を Flex Message カルーセルに変換
- `reference_type: "generated"` の提案は Flex Message の Header に「AI 提案（要確認）」等の視覚ラベルを付与し、seed 由来の提案と区別する（詳細は `docs/04_functional_spec.md §4.3`）
- Gemini API 障害等で 0 件が返った場合、seed からランダム 2 件を `reference_type: "static_fallback"` で返す（詳細は `§5.3.7`）
- **スポンサーPR枠（FR-S9）は Gemini 非関与**: 協賛イベント（`data/seed/sponsored.json`）はプロンプトに渡さず、Gemini が 2〜3 件を返した後にコード側で決定論的にマッチング挿入する（`reference_type: "sponsored"`、`docs/04_functional_spec.md §4.3`）。Gemini に掲載内容を要約・言い換えさせないことで、開催日・応募条件の改変・捏造を防ぐ（NFR-Truth）。したがって `sponsored` は本節の出力形式スキーマにも `_ACTIVITY_JSON_SCHEMA` の enum にも含めない。

**パラメータ調整**:
- `temperature`: 0.8（多様性を出す）
- `max_output_tokens`: 800

#### 4.1.1 「ほかの学生の取り組み」ブランチ（FR-S4 / §4.3 ハブのブランチ B）

**目的**: やりたいこと相談ハブで「👥 ほかの学生の取り組みを見る」を選んだ場合に、
先輩投稿と他の学生の経験投稿（匿名）を素材に 2〜3 件の活動提案を JSON で返す。SECI
モデルの「実践知の継承」を体現する導線。出力形式・後処理・Flex 変換は §4.1 と共通。

**呼び出しコンテキスト**（§4.1 との差分）:
- 学生プロフィール
- 先輩投稿（`senior_posts.json`、`author_pseudonym` のみ）
- 他の学生の経験投稿（`data/posts.json` を匿名化した allow-list。title / body / area /
  category / created_at のみ。`line_user_id` 等は渡さない。§4.2 の匿名化ポリシー準拠）

**プロンプト構造**（差分のみ）:

```
{system_prompt_common}

【今回の依頼】
学生が「ほかの学生の取り組みを知りたい」と言っています。
以下の先輩投稿と、同じマンションの学生の経験投稿（匿名）を素材に、
その学生が真似したり参加したりできる活動を 2〜3 件提案してください。

【学生プロフィール】
{profile_summary}

【先輩の体験投稿】
{senior_posts_summary}

【同じマンションの学生の経験投稿（匿名）】
{student_posts_summary}

【出力形式】
（§4.1 と同一の JSON 配列。reference_type は senior_post / generated のいずれか）
```

- 学生投稿は匿名情報として扱い、投稿者の名前・学年・大学などを推測して記載しない。
- 実行時の学生投稿が 0 件でも先輩投稿 seed から必ず 2〜3 件を返す
  （フォールバックは `reference_type: "senior_post"`）。
- `reference_type` は素材由来を優先し `senior_post`、AI が組み立てた場合は `generated`。
- パラメータは §4.1 と同じ（`temperature` 0.8 / `max_output_tokens` 800）。

### 4.2 生活相談（FR-S5）

**目的**: 生活の困りごとに、地域情報と先輩投稿を参照して回答する。

**プロンプト構造**:

```
{system_prompt_common}

【今回の依頼】
学生から生活相談が届きました。地域情報・先輩投稿・過去の学生投稿を参照して回答してください。

【学生プロフィール】
{profile_summary}

【関連情報の件数】
- stores: {stores_hits} 件
- areas: {areas_hits} 件
- senior_posts: {senior_posts_hits} 件
- student_posts: {student_posts_hits} 件
- total_hits: {total_hits} 件

【関連する地域情報・店舗・先輩投稿】
{context_summary}

【同じマンションの学生の経験投稿（匿名）】
{student_posts_summary}

【学生の発言】
{user_message}

【回答時の注意】
- 参照した先輩投稿・学生投稿がある場合のみ、`answer` の末尾に「🗣️ 先輩の体験から」の見出し行を置いてその内容を引用する。該当が無ければこの見出しごと省略する。**投稿者を特定・推測しない**（例:「〇年生の先輩が...」等の憶測は禁止）。
- 学生投稿は「同じマンションの先輩の投稿」として扱い、匿名で引用する。
- 医療的な内容なら「症状が続く場合は医療機関を受診してください」を必ず含める。
- 緊急を疑う場合は #7119（京都府救急安心センター）や 119 を案内する。
- 実在の店舗・病院名を出す場合は、seed レコードの `data_freshness_note` または `last_verified_at` の値を使い、「◯年◯月時点。営業状況は変わっている可能性があります」等の鮮度注記を必ず併記する（NFR-Truth-4）。
- 300 文字以内でまとめる。
- **total_hits が 0 の場合**: 地名・電話番号・営業時間・特定の店舗名を絶対に断定しない。一般的な案内のみ書き、必ず「詳細は公式窓口でご確認ください」と誘導する（詳細は §5.3）。

【回答書式（JSON 構造化出力）】
以下 3 キーを持つ JSON オブジェクトだけを出力する（前後に地の文やコードフェンスを付けない）。回答は「共感 → 本文 → 締め」の順に空行 1 つで連結され、単一の LINE テキストメッセージとして送られる。
- この回答は親しみやすさ重視のため、上記トーンの「絵文字は控えめ」よりも**多めに絵文字を使う**（ブロックごとに 1〜3 個目安。過剰な連発や意味のない絵文字は避ける）。
- "empathy": 共感・受け止めの 1〜2 文。気持ちに寄り添う絵文字（😢💦🙂 等）を 1〜2 個添える。つらさ・不安・体調など感情が読み取れる相談のときだけ書き、事務的な質問（店舗・手続き等）では空文字 "" にする。
- "answer": 回答本体。冒頭 1 文で結論・要点を先に述べる（結論先出し）。候補・手順・注意点を挙げるときは「💡 AI からのアドバイス」の見出し行を置き、**各行の行頭に内容へ合った絵文字（🏥📍💡✅📞 等）を付けた箇条書き**にする（「・」は使わない）。さらに【関連する先輩投稿】や【同じマンションの学生の経験投稿】に該当がある場合のみ、続けて「🗣️ 先輩の体験から」の見出し行を置きその内容を 1〜2 文で引用する（該当が無ければこの見出しごと省略）。実在の店舗・施設を挙げた場合は上記の [情報鮮度: ...] の値を「※ (値)」の形で末尾に添える。
- "closing": 気遣いの一言と必要な誘導（受診・#7119 等）。行頭に絵文字（💊🆘📞 等）を置いて 1〜2 行にする。無ければ空文字 "" でよい。
- Markdown 記号（-, *, #, **）は使わない。LINE は装飾を表示せず記号がそのまま残るため、区切りは絵文字と改行で表現する。
- empathy / answer / closing を合計して 300 字以内に収める。

出力例:
{"empathy": "熱っぽいんですね😢 それはつらいですよね。近くの病院、一緒に探しましょう🏥", "answer": "37 度台なら、まず近くの内科クリニックの受診が安心です✨\n\n💡 AI からのアドバイス\n🏥 今出川周辺には徒歩圏の内科が複数あります\n📞 迷ったら #7119 に電話して相談しましょう\n\n🗣️ 先輩の体験から\n土曜の午前も空いていて待ち時間が短かったそうです", "closing": "💊 症状が続くときは無理せず受診してくださいね\n🆘 緊急なら #7119 へ"}
```

> **送信前整形**（実装注記）: Gemini の JSON 応答は `services/gemini._parse_life_json` で `empathy` / `answer` / `closing` に分解する。各フィールドを整形ヘルパー `src/utils/text_format.py` で Markdown 痕跡除去（`- `/`* ` の行頭を「・」へ、`**`/`` ` `` マーカー除去）・改行正規化したうえで、「共感 → 本文 → 締め」の順に `text_format.join_blocks` で空行 1 つ区切りに連結し、`services/line_reply.push_text` で**単一のテキストメッセージ**として送信する（詳細は `docs/04_functional_spec.md §4.4`、Zero-context 時の組み立ては §5.3.6）。

**Context 選定ロジック**:
- ユーザー発言のキーワードを抽出（既存 LINE Bot でも使う簡易 tokenizer）
- **seed**: `areas.json` / `stores.json` / `senior_posts.json` から関連度上位 5 件を渡す
- **runtime**: `data/posts.json` の全投稿から匿名化した (`title`, `body`, `area`, `category`, `created_at`) のみを対象に、関連度上位 5 件を渡す（`services/posts.list_all_for_context()`）
- 詳細な I/F は `services/context_search.find_relevant_context` の §5.3.3 を参照
- MVP では単純な部分文字列マッチで良い（RAG なし）
- `total_hits == 0` の場合は §5.3 の Zero-context 分岐が優先される。学生投稿の増加によって Zero-context 発火頻度は自然に下がる（この方向は SECI モデルの継承サイクルに整合）

**匿名化ポリシー**（SECI モデル継承の中核ルール）:

- Gemini に渡すのは学生投稿の `title` / `body` / `area` / `category` / `created_at` のみ。
- `line_user_id`、投稿者のプロフィール（大学名・学部・学年・興味など）、`post_id` は一切渡さない。
- `share_with_parent` フラグは **保護者への月次サマリー用**であり、他学生への共有可否とは独立。学生投稿は全件が生活相談 context の対象となる（`share_with_parent=false` の投稿も含む）。
- 投稿者本人を後の学生からリバース識別できないよう、上記フィールド以外の紐付け情報は伝播させない。
- T4.14 で経験投稿は 5 問（`period` / `summary` / `learned` / `regret` / `advice`）に構造化されたが、Gemini に渡す本文はこれらを連結した合成 `body` に集約する。構造化フィールドを個別に渡すことはせず、上記アローリスト（5 フィールド）は**変更しない**（`docs/05_data_model.md §4.3` / §8）。構造化により `body` 内の情報粒度が揃うため、匿名化契約を保ったまま context 品質だけが向上する。

**パラメータ調整**:
- `temperature`: 0.5（決定性重視）
- `max_output_tokens`: 500
- `response_mime_type`: `application/json`（やりたいこと相談・finalize と同形。JSON 構造化出力を強制）

### 4.3 「詳しく聞く」（FR-S4 のフォローアップ）

活動カード内の「詳しく聞く」ボタンで、対象活動について追加情報を返す。

```
{system_prompt_common}

【今回の依頼】
学生が以下の活動について詳しく知りたがっています。

【対象活動】
{activity_title}
{activity_summary}
{activity_reference_type}
{original_source}

【学生プロフィール】
{profile_summary}

【回答時の注意】
- どうやって参加するか、準備物、注意点を簡潔にまとめる。
- 情報がない部分は「担当者に問い合わせてみてください」と誘導する。
- 300 文字以内。

回答:
```

**パラメータ**: `temperature: 0.5`, `max_output_tokens: 500`

### 4.4 月次サマリー生成（FR-P3）

保護者向けの「今月のレポート」の末尾に添える **AI寮母より** の月次総括コメント。実装は `services/gemini.py::summarize_month` と `services/prompts.py::build_month_summary_prompt`（`docs/04_functional_spec.md §5.3` 参照）。

**入力**（共有同意範囲のみ）: 当月の `share_with_parent=true` 投稿タイトルと、`usage_stats.json` の当月カウント（生活・活動相談、経験投稿、プロフィール更新の回数）。**投稿本文は入力しない**（Flex に直接載せる 60 字プレビューと二重化しないため）。

```
{system_prompt_common}

【今回の依頼】
保護者向けの月次レポートに添える、AI 寮母からの温かい 2〜3 文の総括を書いてください。

【学生プロフィール（参考）】{profile_summary_1_line}
【当月（{year_month}）に共有された頑張ったことのタイトル】
{posts_bullets_or_none}

【当月の利用状況】
- 生活相談: {life}回
- やりたいこと相談: {activity}回
- 経験投稿: {post}回
- プロフィール更新: {profile}回

【出力ルール】
- 2〜3 文、合計 120 文字以内。
- 「〜な様子です」「〜されているようです」など、AI が学生の様子を推測する語尾を使う（断定しない）。
- 投稿タイトルや相談回数から具体的な事実を1つだけ拾って触れて良い（例:「経験投稿を続けられている様子です」）。
- 数値の解釈は前向きに（0 回でも「今月は静かに過ごされているようです」など）。
- 医療診断、法律断定、緊急対応判断、成績評価、進路助言は禁止。プロフィール以外の個人情報を書かない。
- 記号での装飾（絵文字・箇条書き・見出し）は使わない。プレーンテキストのみ。
```

**パラメータ**: `temperature: 0.6`, `max_output_tokens: 200`, `timeout: 8s`（`DEFAULT_TIMEOUT_S`）

**フォールバック**（`services/gemini.py::summarize_month` 側）:

- 当月投稿 0 件かつ相談合計（生活＋活動）3 回未満のときは Gemini を呼ばず、定型文「今月もお子さんは元気に過ごされている様子です。」を返す。
- `GEMINI_MOCK_MODE` 有効時は「（mock）今月も前向きに過ごされている様子です。」を返す。
- Gemini 応答が空文字列または例外時は上記定型文にフォールバック。

### 4.5 経験投稿ファイナライズ（title 生成 + period 正規化 + 妥当性判定、FR-S6 / T4.15）

経験投稿（`docs/04_functional_spec.md §4.5`）の全項目収集後、`post.share_parent` 選択直後に **1 回だけ**呼び、確認カードに載せる title を生成し、相対的な period 表現を絶対表現へ正規化し、あわせて**投稿内容の妥当性（`valid`）を判定する**。実装は `services/gemini.py::finalize_post` と `services/prompts.py::build_post_finalize_prompt`。呼び出し中は `show_loading` で Loading Indicator を表示し、確認カードは push で後送する。

**妥当性判定（`valid` / `reason`）**: 抽選・クーポン目的の無意味な投稿が蓄積データ（保護者月次・他学生への SECI context）を汚染するのを防ぐため、この 1 回の呼び出しに妥当性チェックを相乗りさせる（追加の LLM 呼び出しは行わない）。`valid == false` の投稿は**保存しない**（確認カードへ進めず、固定警告文を返して終了する。ただし抽選 FR-S11 は引かせる。`docs/04_functional_spec.md §4.5` / §4.9）。判定は**誤検知を厳に避ける**方針とする（正当な投稿を弾く方がデモで致命的なため）。

**入力**: 学生本人の投稿内容（`category` / `summary` / `learned` / `regret` / `advice` / `area` / 生入力 `period_raw`）と、投稿時点の日付 `today`（＝`created_at` の JST 日付）。

```
{system_prompt_common}

【今回の依頼】
学生の経験投稿から、(1) 40 文字以内の短いタイトル、(2) 期間表現の絶対化、(3) 投稿内容の妥当性判定、を行ってください。

【今日の日付】{today}（この日付を基準に相対表現を絶対表現へ変換する）

【投稿内容】
- カテゴリ: {category}
- 期間（ユーザーの言葉）: {period_raw}
- 概要: {summary}
- 学び: {learned}
- 残念・注意: {regret}
- 次の人へ: {advice}
- 場所: {area}

【出力ルール】
- 必ず JSON オブジェクトのみを返す: {"title": "...", "period": "...", "valid": true, "reason": "..."}
- title: 内容を表す簡潔な見出し。40 文字以内。絵文字・記号での装飾はしない。
- period: {period_raw} を {today} 基準で絶対表現へ変換（例: 「去年の10月」→「2025年10月」、「先週末」→「2026年7月上旬」）。
  {period_raw} が空なら空文字。判断できない相対表現（「大学1年の頃」等）は無理に断定せず、元の表現に近い形で返す。
- valid: 投稿として妥当なら true、不正なら false（真偽値）。
  - false にするのは次のいずれかが明白な場合のみ: 単一文字の連打やキーボード乱打・意味をなさない文字列、荒唐無稽で明らかに虚偽の内容、中身の伴わない抽選/クーポン目的と判断できる投稿。
  - 短くても内容が伴っていれば true。判断に迷う場合は必ず true（正当な投稿を弾かない）。
- reason: valid が false のときのみ、日本語で簡潔に理由を書く（true のときは空文字でよい）。
- 投稿内容以外の事実を創作しない。個人を特定する情報は書かない。
```

**JSON 出力スキーマ**: `{"title": string, "period": string, "valid": boolean, "reason": string}`。`services/gemini.py` の活動提案（§4.1）と同じく SDK の JSON モード（`response_mime_type: "application/json"` + `response_schema`）で受け取る。

**パラメータ**: `temperature: 0.3`（決定性重視）, `max_output_tokens: 160`, `timeout: 8s`。

**フォールバック**（フローを止めない。`services/gemini.py::finalize_post` が常に有効な dict を返す）:

- `GEMINI_MOCK_MODE` 有効時・例外・空応答・JSON パース失敗時は、title = `summary` の冒頭 40 文字、period = `period_raw`（正規化せずそのまま）、**`valid = true`**（＝弾かず通す）を返す。
- title が空や 40 文字超で返った場合も上記ルールで補正する。
- `valid` が欠落・非真偽値で返った場合も `true` にフォールバックする（誤検知回避）。

**プライバシー/正確性**: 入力は学生本人の投稿のみで、他者の個人情報は渡さない。正規化はあくまで表示・保存の補助であり、プロフィール依存の曖昧表現（「大学1年の頃」等）は now 基準だけでは絶対化しきれないため、LLM のベストエフォートとする（プロフィール投入は将来拡張）。

## 5. NG トピックとフォールバック

### 5.1 明示的 NG トピック

以下のトピックが検出された場合、Gemini 呼び出しの前に定型応答を返すか、System Prompt に強い制約を追加する。

| キーワード例 | 定型応答 |
| --- | --- |
| `死にたい`, `消えたい`, `自殺` | 「つらいですね…すぐに話せる相手として、いのちの電話 0570-783-556 や、京都いのちの電話 075-864-4343 に相談してみてください。あなたを大切に思う人がいます。」+ 通常の会話を促す |
| `救急`, `119`, `倒れた`, `動けない` | 「緊急の場合はすぐに 119 に通報してください。応急救護が必要な場合は #7119（京都府救急安心センター）で相談できます。」 |
| `犯罪`, `盗まれた`, `暴力` | 「警察に相談することをおすすめします。緊急なら 110、相談なら #9110 が便利です。」 |

これらは Gemini を通さずに Python 側で先にマッチさせる。

### 5.2 Gemini 側の制約

System Prompt で明示している以下の禁止事項は、応答内容を post-hoc でチェックし、問題があれば「他の情報源を確認してください」と応答を差し替える。

- 特定の薬品名の推奨（例: 「ロキソニンを飲みましょう」）
- 特定の医療機関を「絶対に大丈夫」と保証する表現
- 特定の弁護士・法律事務所を推奨する表現
- 個人が特定できる情報の暴露

MVP 期間では、簡易的な正規表現チェックで十分（実装は Day 4 の T4.9 で対応予定）。

### 5.3 ハルシネーション対策（Zero-context 分岐）

#### 5.3.1 目的

seed（`data/seed/*.json`）にもランタイム学生投稿（`data/posts.json`）にも情報がない話題（例: ゴミ出しの曜日、特定病院の営業時間、店舗の電話番号）を相談された際、Gemini が地名・電話番号・営業時間などをそれっぽく捏造することを防ぐ。上位の非機能要件は `docs/01_requirements.md §6.4`（NFR-Truth-1/2/3）を参照。

#### 5.3.2 判定条件

`context_search.find_relevant_context(user_message)` の戻り値の総ヒット数（`total_hits = stores + areas + senior_posts + student_posts`）が **0 件** の場合を Zero-context とする。MVP では単純な `total_hits == 0` 判定のみ。擬似的な部分文字列ヒット（1 件だけ無関係なマッチが返る等）は本スコープ外とし、Day 4 の Post-hoc 正規表現チェック（T4.9）で拾う。

学生投稿の増加により Zero-context の発火頻度は徐々に下がる（SECI モデルの継承サイクルによる自然な情報蓄積）。

#### 5.3.3 I/F 定義

`src/services/context_search.py` に以下を実装する:

```python
from typing import TypedDict

class ContextSearchResult(TypedDict):
    stores: list[dict]
    areas: list[dict]
    senior_posts: list[dict]
    student_posts: list[dict]     # 匿名化済み: title/body/area/category/created_at のみ
    total_hits: int               # sum(len(stores) + len(areas) + len(senior_posts) + len(student_posts))
    matched_categories: set[str]  # 収集された seed のカテゴリ (例 {"medical", "government"})


def find_relevant_context(user_message: str, top_k: int = 5) -> ContextSearchResult:
    """Return matched items grouped by kind plus aggregate stats.

    seed の 3 コレクション（stores / areas / senior_posts）に加えて、
    ランタイムの ``posts.list_all_for_context()`` で得られる匿名化済み
    学生投稿を student_posts として同じスコアリングで rank する。
    """


def should_add_disclaimer(result: ContextSearchResult) -> bool:
    """MVP: total_hits == 0 で真。将来的な閾値変更のためのラッパー。"""
    return result["total_hits"] == 0


def detect_medical_intent(user_message: str) -> bool:
    """Return True when the message contains medical-context keywords.

    Distinct from :func:`detect_emergency` — this catches non-emergency
    medical topics like 'クリニックを探したい'.
    """
```

**匿名化の保証**: `student_posts` の各要素は `posts.list_all_for_context()` が返す辞書のみを含む。`line_user_id`・投稿者プロフィール・`post_id` は絶対に含めない。呼び出し側（`gemini.answer_life_question` の prompt 組み立て）でも上記フィールド以外を参照しないよう docs §4.2 の匿名化ポリシーに従う。

**互換性のメモ**: Day 2 で既に `find_relevant_context` は生の `dict[str, list[dict]]` を返す実装がプッシュ済み、T2.hallu で `ContextSearchResult` に置き換え済み。T4.10（学生投稿継承）で `student_posts` フィールドと `posts.list_all_for_context` を追加し、`handle_life_consultation` / `answer_life_question` の呼び出しも同時に更新する。

#### 5.3.4 応答テンプレート

`src/services/prompts.py` にモジュール定数として保持する:

```python
ZERO_CONTEXT_DISCLAIMER = (
    "ごめんなさい、この話題については先輩の投稿や地域の情報がまだ届いていません🙏\n"
    "以下は一般的なご案内なので、正確な情報は公式窓口でご確認くださいね。\n"
)

MEDICAL_FOLLOWUP = (
    "\n\n体調のご相談は #7119（京都府救急安心センター）でも相談できますよ。\n"
    "京都市の医療機関検索サイトも参考になります。"
)
```

文言変更時は本セクションと定数を同時に更新する。トーンは System Prompt §3 の「親しみやすい寮母のような語り口（ですます調、絵文字は控えめに 1〜2 個）」に揃える。

#### 5.3.5 医療キーワード追加誘導

Zero-context の生活相談で、以下いずれかのキーワードを検出した場合、`MEDICAL_FOLLOWUP` を disclaimer + 一般案内の直後に追加する:

- 「病院」「クリニック」「診療所」「熱」「体調」「薬」「症状」「痛」「怪我」「風邪」「めまい」「吐き気」

「痛」は活用形（「痛い」「痛くて」「痛かった」「頭痛」）を包括的に拾うためのルート形として登録する。「痛快」等の少数の false-positive は許容する（Zero-context 時のみ発火するため実害が小さい）。この判定は `context_search.detect_medical_intent(user_message: str) -> bool` として新設。既存の `detect_emergency` とは別関数（緊急ではない医療系相談を拾う）。

#### 5.3.6 応答組み立て順

1. `context_search.find_relevant_context(user_message)` を呼ぶ
2. `should_add_disclaimer(result)` が真なら:
   - Gemini へは §4.2 のプロンプトで `total_hits == 0` を明示、「地名・電話番号・営業時間・特定の店舗名を絶対に断定しない」制約を強制
   - メッセージ先頭に `ZERO_CONTEXT_DISCLAIMER` を連結する（この場合 `empathy` は省略し、disclaimer が受け止めの役割を兼ねる）
   - `detect_medical_intent` が真ならメッセージ末尾に `MEDICAL_FOLLOWUP` を連結する
3. `should_add_disclaimer(result)` が偽なら通常応答（`empathy` / `answer` / `closing` をそのまま連結。先輩投稿を引用しやすい設計）

ブロック連結順（空フィールドは脱落。空行 1 つ区切りで単一テキストメッセージにする。実装は `handlers/student.handle_life_consultation`）:

| 順 | 通常時 | Zero-context 時 |
| --- | --- | --- |
| 1 | `empathy`（空なら脱落） | `ZERO_CONTEXT_DISCLAIMER` |
| 2 | `answer` | `answer` |
| 3 | `closing` | `closing` |
| 4 | —— | `MEDICAL_FOLLOWUP`（医療系のときのみ） |

#### 5.3.7 `static_fallback` との違い

`reference_type: "static_fallback"` は **Gemini API 障害時に seed からランダム候補を返す**モード（`§4.1 呼び出し後の処理`）で、原因は「AI 側の停止」。Zero-context は **情報源に該当が無い** 状態で、原因は「seed 未カバー」。両者はユーザーに提示する disclaimer が異なるため、実装上も別処理として扱う:

| ケース | 原因 | disclaimer | 誘導先 |
| --- | --- | --- | --- |
| `static_fallback` | Gemini 障害 | 「AI が応答できなかったので、代わりに seed からピックしました」（実装は Day 4 で調整）+ seed が実在情報の場合は `data_freshness_note` / `last_verified_at` を必ず併記 | なし |
| Zero-context | seed 未カバー | `ZERO_CONTEXT_DISCLAIMER` | 公式窓口 + 必要なら `MEDICAL_FOLLOWUP` |

#### 5.3.8 ログ

`answer_life_question` の返却時に、以下フラグを journald ログに記録する（詳細は `docs/04_functional_spec.md §3.3`）:

- `zero_context: bool` — `should_add_disclaimer(result)` の値
- `disclaimer_shown: bool` — 応答に `ZERO_CONTEXT_DISCLAIMER` を付与したか
- `medical_followup_shown: bool` — `MEDICAL_FOLLOWUP` を付与したか
- `reference_types: list[str]` — やりたいこと相談の場合の各カード `reference_type`
- `student_posts_hits: int` — 生活相談で参照した学生投稿の件数（T4.10 追加）

## 6. パフォーマンス設計

### 6.1 タイムアウト

- Gemini SDK 呼び出しは用途別に 4 段の client-side timeout を設定（§2.4 の表参照）:
  - 対話系（text / life 相談 JSON / 活動詳細）: 15 秒（`DEFAULT_TIMEOUT_S`）
  - 提案系 JSON（`propose_activities` / `propose_from_student_efforts`）: 20 秒（`_PROPOSE_TIMEOUT_S`）
  - 月次バッチ（`summarize_month`）: 30 秒（`_BATCH_TIMEOUT_S`、Webhook 外）
  - 投稿確定（`finalize_post`）: 8 秒（`_FINALIZE_TIMEOUT_S`）
- Webhook 30 秒制約に対する余裕を確保するため対話系は 15 秒に抑え、**リトライは行わない**（§6.3）。失敗時は即フォールバック文言を返す
- **待機中の表示**: 通常の待機は Loading Indicator（`docs/04_functional_spec.md §3.6`、`show_loading(user_id)`）で可視化する。テキストの中間応答（「少し考えます…」等）は使わない。

### 6.2 キャッシュ

- 地域情報・店舗情報・イベント情報は起動時にメモリに読み込む
- 更新は再起動で反映（MVP 期間は動的更新不要）
- Gemini 応答自体はキャッシュしない（プロフィール依存で毎回異なるため）

### 6.3 レートリミット対策

- Gemini Flash-Lite の無料枠を確認して開発時は 1 分あたりの呼び出し回数を制限
- 429 (`ResourceExhausted`) / 504 (`DeadlineExceeded`) / その他例外はいずれも **リトライせず即フォールバック**（合計予算が Webhook 30 秒に収まらないため）。ログには `[GEMINI_FALLBACK] ...` プレフィクスで残す

## 7. コスト管理

### 7.1 見積もり

- Flash-Lite の料金 (2026-04 時点、実行前に要確認):
  - Input: $0.075 / 1M tokens
  - Output: $0.30 / 1M tokens
- 1 リクエスト平均 1500 input + 400 output tokens → 約 $0.00023 / 呼び出し
- MVP 期間中 1000 回呼び出しても 30 円以下

### 7.2 実装上の節約

- 地域情報は summary（1〜2 文）で渡し、全文は渡さない
- 会話履歴は直近 3 ターン程度に絞る
- Gemini 呼び出しが必須でない箇所（例: ヘルプ表示）は静的テンプレートで済ませる

## 8. エラー・フォールバック

### 8.1 呼び出し失敗時

- **API キー無効**: サーバー起動時に検知して停止
- **429 (レート制限)**: リトライせずフォールバック文言（§6.3）
- **タイムアウト**: 「今、頭がぼんやりしてます…もう一度話しかけてください🙇」
- **500 系エラー**: 「うまく答えを考えられませんでした。少し時間を空けてもう一度お試しください。」
- **その他例外**: ログに詳細を残し、ユーザーには汎用エラー文言

### 8.2 JSON パース失敗（提案系）

- JSON でない応答を受け取ったら、テキスト応答モードに切り替えて「今日のおすすめ 3 選」形式で返す
- ログに raw response を残す

### 8.3 空応答

- Gemini が空文字列を返した場合、「うまく思いつかなかったです。もう少し詳しく教えてください」と質問を促す

## 9. モニタリング

MVP 期間は最低限のログでよい。

- Gemini 呼び出し回数を journal ログにカウント
- エラー率を目視で追う
- レスポンスタイムの p50 / p95 を目安で把握

本格運用時は Prometheus/Grafana 等の導入を検討。

## 10. Prompt バージョニング

- プロンプトテンプレートは Python コード内の定数として管理
- `services/prompts.py` に集約
- 大きく変更した場合はコミットメッセージで明示
- 別バージョンを試したい場合は `.env` の `PROMPT_VERSION` で切り替え可能にする（余裕があれば）

## 11. 将来の拡張（MVP 対象外）

- RAG（ベクトル検索による関連情報取得）
- Function Calling（構造化された返答）
- 会話履歴の長期記憶
- 多言語対応（現在は日本語のみ）
- 音声応答（Text-to-Speech）

## 12. 変更履歴

| 日付 | 変更内容 | 記入者 |
| --- | --- | --- |
| 2026-07-05 | 初版作成 | kmch4n |
| 2026-07-05 | §5.3 Zero-context 分岐仕様を新設、§3 禁止事項に情報源制約を追加、§4.1/§4.2 に reference_type と件数ラベルを追記 | kmch4n |
| 2026-07-09 | §4.4 月次サマリー生成プロンプトを実装ベースに刷新: 入力を当月共有投稿タイトル＋利用回数のみに限定、断定禁止・NG トピック明記、3 段フォールバック（少実績時 / mock / 空応答）を規定（FR-P3 拡張の docs-first） | kmch4n |
| 2026-07-10 | §4.2 生活相談を JSON 構造化出力（empathy / answer / closing）に変更し `response_mime_type: application/json` を追加、§5.3.6 に「共感 → 本文 → 締め」最大 3 吹き出しの割り付け表を追記（可読性・温かみ改善の docs-first） | kmch4n |
| 2026-07-10 | §4.2 生活相談の回答書式を絵文字リッチ化: 共感・締めに絵文字を添え、箇条書きを「・」から内容に合った行頭絵文字（🏥🗣️💊 等）のアンカーに変更（親しみやすさ強化の docs-first） | kmch4n |
| 2026-07-10 | §4.2 `answer` を「💡 AI からのアドバイス」と「🗣️ 先輩の体験から」の見出し付き 2 セクション構成に変更（先輩の体験は先輩投稿・学生投稿が存在するときだけ表示） | kmch4n |
| 2026-07-10 | §4.2 / §5.3.6 生活相談の応答を最大 3 吹き出しの分割から**単一テキストメッセージ**へ戻す。絵文字リッチ化で 1 メッセージ内でも可読性・温かみが確保できたため（分割は不要と判断） | kmch4n |
