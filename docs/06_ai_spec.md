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
| `timeout` | 25 秒 | LINE Webhook 30 秒制約に対する安全マージン |

用途別に微調整する（下記各節参照）。

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
- 実在する店舗・病院・施設について、古い情報の可能性があることを一言添える。
- ユーザー本人が登録した情報以外の個人情報を漏らさない。
- 情報源（`data/seed/*.json`）に存在しない具体情報（電話番号、営業時間、特定店舗名、特定日程）を断定しない。
- 情報源に該当が無い場合は、必ず公式窓口や #7119 等の一般的な連絡先へ誘導する。

【トーン】
- 親しみやすい寮母のような語り口（ですます調、絵文字は控えめに 1〜2 個）。
- 学生には気さくに、保護者には丁寧に。
- 断定を避け、選択肢を示す。

【情報源】
- ユーザーのプロフィール、過去の投稿、地域情報、先輩投稿を参照して回答する。
- 情報がない場合は「わからない」と正直に答える。
- 参照した先輩投稿がある場合、「先輩の体験より」と注記する。

【出力形式】
- 通常はテキストで簡潔に（200〜300 文字目安）。
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

**パラメータ調整**:
- `temperature`: 0.8（多様性を出す）
- `max_output_tokens`: 800

### 4.2 生活相談（FR-S5）

**目的**: 生活の困りごとに、地域情報と先輩投稿を参照して回答する。

**プロンプト構造**:

```
{system_prompt_common}

【今回の依頼】
学生から生活相談が届きました。地域情報と先輩投稿を参照して回答してください。

【学生プロフィール】
{profile_summary}

【関連情報の件数】
- stores: {stores_hits} 件
- areas: {areas_hits} 件
- senior_posts: {senior_posts_hits} 件
- total_hits: {total_hits} 件

【関連する地域情報・店舗・先輩投稿】
{context_summary}

【学生の発言】
{user_message}

【回答時の注意】
- 参照した先輩投稿がある場合、「先輩の体験より: ...」と 1 文添える。
- 医療的な内容なら「症状が続く場合は医療機関を受診してください」を必ず含める。
- 緊急を疑う場合は #7119（京都府救急安心センター）や 119 を案内する。
- 実在の店舗・病院名は「情報が古い可能性があります」と注記する。
- 300 文字以内でまとめる。
- **total_hits が 0 の場合**: 地名・電話番号・営業時間・特定の店舗名を絶対に断定しない。一般的な案内のみ書き、必ず「詳細は公式窓口でご確認ください」と誘導する（詳細は §5.3）。

回答:
```

**Context 選定ロジック**:
- ユーザー発言のキーワードを抽出（既存 LINE Bot でも使う簡易 tokenizer）
- `areas.json` / `stores.json` / `senior_posts.json` から関連度上位 5 件を渡す（`services/context_search.find_relevant_context` の I/F は §5.3.3）
- MVP では単純な部分文字列マッチで良い（RAG なし）
- `total_hits == 0` の場合は §5.3 の Zero-context 分岐が優先される

**パラメータ調整**:
- `temperature`: 0.5（決定性重視）
- `max_output_tokens`: 500

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

保護者向けの「今月のレポート」で、投稿を要約する場合に使う（オプション）。MVP では投稿をそのまま Flex Message で並べるだけでも良いが、以下のようにサマリー文を 1 段だけ付ける。

```
{system_prompt_common}

【今回の依頼】
保護者向けに、学生の当月の頑張ったことを 1〜2 文で温かく要約してください。

【学生名】{student_pseudonym}
【当月の投稿】
{posts_bullets}

【出力】
親しみを込めた 1〜2 文（100 文字以内）。「頑張っていますね」といった前向きな言葉で締める。
```

**パラメータ**: `temperature: 0.7`, `max_output_tokens: 200`

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

seed（`data/seed/*.json`）に情報がない話題（例: ゴミ出しの曜日、特定病院の営業時間、店舗の電話番号）を相談された際、Gemini が地名・電話番号・営業時間などをそれっぽく捏造することを防ぐ。上位の非機能要件は `docs/01_requirements.md §6.4`（NFR-Truth-1/2/3）を参照。

#### 5.3.2 判定条件

`context_search.find_relevant_context(user_message)` の戻り値の総ヒット数（`total_hits`）が **0 件** の場合を Zero-context とする。MVP では単純な `total_hits == 0` 判定のみ。擬似的な部分文字列ヒット（1 件だけ無関係なマッチが返る等）は本スコープ外とし、Day 4 の Post-hoc 正規表現チェック（T4.9）で拾う。

#### 5.3.3 I/F 定義

`src/services/context_search.py` に以下を実装する:

```python
from typing import TypedDict

class ContextSearchResult(TypedDict):
    stores: list[dict]
    areas: list[dict]
    senior_posts: list[dict]
    total_hits: int              # sum(len(stores) + len(areas) + len(senior_posts))
    matched_categories: set[str] # 収集された seed のカテゴリ (例 {"medical", "government"})


def find_relevant_context(user_message: str, top_k: int = 5) -> ContextSearchResult:
    """Return matched seed items grouped by kind plus aggregate stats."""


def should_add_disclaimer(result: ContextSearchResult) -> bool:
    """MVP: total_hits == 0 で真。将来的な閾値変更のためのラッパー。"""
    return result["total_hits"] == 0


def detect_medical_intent(user_message: str) -> bool:
    """Return True when the message contains medical-context keywords.

    Distinct from :func:`detect_emergency` — this catches non-emergency
    medical topics like 'クリニックを探したい'.
    """
```

**互換性のメモ**: Day 2 で既に `find_relevant_context` は生の `dict[str, list[dict]]` を返す実装がプッシュ済み。T2.hallu の実装フェーズで `ContextSearchResult` に置き換える。呼び出し側の `handle_life_consultation` と `answer_life_question` を同時に更新する必要があるため、T2.hallu のコミットに全部含める。

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
   - Gemini 応答テキストの先頭に `ZERO_CONTEXT_DISCLAIMER` を連結
   - `detect_medical_intent` が真なら末尾に `MEDICAL_FOLLOWUP` を追加
3. `should_add_disclaimer(result)` が偽なら通常応答（先輩投稿を引用しやすい設計）

#### 5.3.7 `static_fallback` との違い

`reference_type: "static_fallback"` は **Gemini API 障害時に seed からランダム候補を返す**モード（`§4.1 呼び出し後の処理`）で、原因は「AI 側の停止」。Zero-context は **情報源に該当が無い** 状態で、原因は「seed 未カバー」。両者はユーザーに提示する disclaimer が異なるため、実装上も別処理として扱う:

| ケース | 原因 | disclaimer | 誘導先 |
| --- | --- | --- | --- |
| `static_fallback` | Gemini 障害 | 「AI が応答できなかったので、代わりに seed からピックしました」（実装は Day 4 で調整）| なし |
| Zero-context | seed 未カバー | `ZERO_CONTEXT_DISCLAIMER` | 公式窓口 + 必要なら `MEDICAL_FOLLOWUP` |

#### 5.3.8 ログ

`answer_life_question` の返却時に、以下フラグを journald ログに記録する（詳細は `docs/04_functional_spec.md §3.3`）:

- `zero_context: bool` — `should_add_disclaimer(result)` の値
- `disclaimer_shown: bool` — 応答に `ZERO_CONTEXT_DISCLAIMER` を付与したか
- `medical_followup_shown: bool` — `MEDICAL_FOLLOWUP` を付与したか
- `reference_types: list[str]` — やりたいこと相談の場合の各カード `reference_type`

## 6. パフォーマンス設計

### 6.1 タイムアウト

- Gemini SDK 呼び出しに 25 秒の client-side timeout を設定
- 25 秒を超えたら「もう少し時間がかかっています…」の中間 push message を送り、その後結果を続けて送る

### 6.2 キャッシュ

- 地域情報・店舗情報・イベント情報は起動時にメモリに読み込む
- 更新は再起動で反映（MVP 期間は動的更新不要）
- Gemini 応答自体はキャッシュしない（プロフィール依存で毎回異なるため）

### 6.3 レートリミット対策

- Gemini Flash-Lite の無料枠を確認して開発時は 1 分あたりの呼び出し回数を制限
- 429 エラー時は 5 秒待って 1 回リトライ、それでも失敗したらフォールバック文言を返す

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
- **429 (レート制限)**: 5 秒待って 1 回リトライ、失敗ならフォールバック文言
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
