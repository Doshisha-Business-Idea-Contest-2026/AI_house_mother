# 04. 機能仕様

## 1. このドキュメントの目的

`01_requirements.md` の機能要件（FR-XX）と `03_user_stories.md` のユーザーストーリー（US-XX）を、実装可能な粒度まで詳細化する。

- 会話遷移（LINE Bot なので「画面遷移」ではなく「対話ステート遷移」で表現）
- 入出力の具体仕様
- Quick Reply / Flex Message のテンプレート方針
- エラーハンドリング

## 2. 前提

### 2.1 会話ステート管理

- ユーザーごとにインメモリでセッションを保持
- キー: `line_user_id`（ハッシュ化してログに出す）
- タイムアウト: 10 分（既存 `kcb_linebot` と同じ）
- タイムアウト後はセッションが破棄され、次回発話時にステートリセット
- 永続化が必要な情報（プロフィール、投稿、招待コード等）は JSON ファイルへ書き出す

### 2.2 メインメニュー

役割選択後の主要導線として、リッチメニュー or Quick Reply で以下を常時表示する。

**学生用**:
- 🎯 やりたいこと相談
- 💬 生活相談
- ✏️ 経験を投稿
- 👤 プロフィール
- 👨‍👩‍👧 保護者連携
- ❓ ヘルプ

**保護者用**:
- 📊 今月のレポート
- 🔗 学生と連携
- 👤 プロフィール（連携済み学生の一覧）
- ❓ ヘルプ

**Day 4 時点の運用**: リッチメニュー本実装（画像作成 + LINE API 登録）は決勝プレゼン後に持ち越し（`docs/09_tasks.md` T4.2）。当面は `main_menu_quick_reply(role)` の Quick Reply で全機能に到達できる状態を保つ。

## 3. 共通仕様

### 3.1 メッセージ長

- テキスト応答: 300 文字以内を目安。長くなる場合は Flex Message で分割。
- Flex Message のカルーセルは最大 10 バブル。

### 3.2 エラーハンドリング

| エラー種別 | ユーザー向け応答 | 補足 |
| --- | --- | --- |
| Gemini API タイムアウト | 「今、頭がぼんやりしてます…もう一度話しかけてください🙇」 | §3.4 に従い main menu QR を付与 |
| Gemini API エラー | 「うまく答えを考えられませんでした。少し時間を空けてもう一度お試しください。」 | §3.4 に従い main menu QR を付与 |
| プロフィール未登録 | 「まずはプロフィールを教えてください！ → 👤 プロフィール」 | プロフィール開始用の QR を付与 |
| 招待コード無効 | 「そのコードは見つかりませんでした。有効期限切れかもしれません。」 | §3.4 に従い main menu QR を付与 |
| 招待コード期限切れ | 「そのコードは有効期限が切れています。学生に新しいコードを発行してもらってください。」 | §3.4 に従い main menu QR を付与 |
| セッションタイムアウト | 「少し時間が空きましたね。もう一度最初からお願いします。」 | §3.4 に従い main menu QR を付与 |
| 関連情報 0 件 (Zero-context) | `ZERO_CONTEXT_DISCLAIMER`（`docs/06_ai_spec.md §5.3.4`）+ 一般案内 + 必要なら `MEDICAL_FOLLOWUP` | 生活相談 QR（`🏠 メインメニュー` / `🚫 相談を終える`）を付与 |
| 未知のコマンド | 「うまく理解できませんでした。「ヘルプ」で使い方を確認できます。」 | §3.4 に従い main menu QR を付与 |
| キャンセル発話 (`キャンセル` / `やめる` / `戻る`) | 「操作をキャンセルしました。」 | §3.4 に従い main menu QR を付与 |
| 未実装機能 placeholder (Day X で実装予定 系) | 「〇〇機能は Day X で実装予定です。」 | §3.4 に従い main menu QR を付与 |

### 3.3 ロギング

- 全ての Webhook 受信を INFO レベルで記録
- Gemini 呼び出しはリクエスト・レスポンスの要約を DEBUG レベルで記録
- エラーは ERROR レベル、スタックトレース付き
- LINE user_id は SHA-256 の先頭 8 文字にハッシュ化

**生活相談・活動提案の Gemini 呼び出しに残すフラグ**（`docs/06_ai_spec.md §5.3.8` と同期）:

| フィールド | 型 | 意味 |
| --- | --- | --- |
| `zero_context` | bool | `context_search.should_add_disclaimer(result)` の値（生活相談用） |
| `disclaimer_shown` | bool | 応答冒頭に `ZERO_CONTEXT_DISCLAIMER` を付与したか |
| `medical_followup_shown` | bool | 末尾に `MEDICAL_FOLLOWUP` を付与したか |
| `reference_types` | list[str] | やりたいこと相談の場合の各カードの `reference_type` |

**月次サマリー Push の構造化ログフィールド**（Day 3 T3.4-b、`scripts/push_monthly_reports.py` から出力）:

| フィールド | 型 | 意味 |
| --- | --- | --- |
| `monthly_push_batch_id` | string | 実行ごとに一意な batch id（`"MRB-" + executed_at ISO`） |
| `parent_hash` | string | 送信先保護者 LINE userId の SHA-256 先頭 8 桁 |
| `student_hash` | string | 対象学生 LINE userId の SHA-256 先頭 8 桁 |
| `year_month` | string | 集計対象年月（`"YYYY-MM"`） |
| `post_count` | int | Flex に含まれた投稿件数（0 は skip、送信自体しない） |
| `status` | string | `"sent"` / `"empty"` / `"error"` |
| `error_reason` | string \| null | LINE API エラー等の失敗理由（成功時 null） |

デモ後の集計・監査のため INFO レベルで残す。個人情報にはあたらないため、user_id ハッシュと合わせて構造化ログとして出力する。

### 3.4 終端応答の Quick Reply 付与ルール

**目的**: LINE Bot の会話 UI ではユーザーが自由入力すると迷いやすく、「次に何をすべきか」を毎回明示するために、会話が一区切りつく応答（終端応答）には必ず選択肢を提示する。

**適用対象**:

- リザーブワード応答: `キャンセル` / `やめる` / `戻る` / `メインメニュー`
- placeholder 応答: 「〜は準備中です」「〜は Day X で実装予定」等
- エラー応答: セッション切れ、不明コマンド、Gemini エラーフォールバック等
- 会話フローの完了応答: プロフィール登録完了、招待コード発行完了、月次レポート表示後 など
- **push_text / push_flex 経由の非同期通知**（保護者連携完了の学生側通知、月次サマリーの scheduled push、`handle_want_events` / `handle_want_students` の Gemini フォールバックなど）: reply_token が使えず「次に何をすべきか」がユーザー側の履歴で完全に流れ落ちるため、reply 系より優先的に QR を付ける

**ルール**:

| 状態 | 付与する Quick Reply |
| --- | --- |
| ユーザーが役割登録済み（student） | `main_menu_quick_reply("student")`（🎯 やりたいこと相談 / 💬 生活相談 / ✏️ 経験を投稿 / 👤 プロフィール / 👨‍👩‍👧 保護者連携 / ❓ ヘルプ） |
| ユーザーが役割登録済み（parent） | `main_menu_quick_reply("parent")`（📊 今月のレポート / 🔗 学生と連携 / ❓ ヘルプ） |
| ユーザー未登録（role = None） | `build_welcome_message()` の welcome text + 学生/保護者選択 Quick Reply |
| 生活相談セッション中 | 「🏠 メインメニュー」「🚫 相談を終える」の 2 択 Quick Reply（`_life_quick_reply()`） |
| プロフィール入力フロー中 | 各ステートの入力用 Quick Reply（例: 学年選択、興味タグ、確認）を優先し、共通 QR は付与しない |

**例外**:

- 対話フロー中の「次の入力を促す応答」（例: 「大学名を教えてください」）は、free-form テキスト入力を期待するため main menu QR を付けない代わりに、キャンセル可能な案内文を含める
- 中間メッセージ（Gemini 呼び出し中の「考え中…」など）は、直後に本応答が続くため QR 不要

**実装上の指針**:

- ヘルパー関数 `_reply_placeholder(event, user_id, text)` を `src/handlers/message.py` に用意し、複数箇所の重複を減らす
- 未登録ユーザーは `_reply_placeholder` の代わりに welcome を返す共通処理に流す

### 3.4-b 非テキストメッセージのフォールバック（Day 4 追加）

**問題**: スタンプ・画像・動画・音声・ファイル・位置情報が届いても Bot が完全無応答だと、直前応答に付いていた Quick Reply が UI 上から流れて見えなくなり、ユーザーが次の操作を見失う。

**方針**: 6 種の非テキストメッセージすべてに対して `src/handlers/message.py::handle_non_text` を単一ハンドラとして登録し、session/role に応じて以下のいずれかを返す。

| 状況 | 応答 |
| --- | --- |
| session が active（プロフィール登録・投稿・保護者連携などのフロー中） | 「テキストで送ってください。中断する場合は「キャンセル」と送ってください。」+ `cancel_quick_reply()` |
| 生活相談セッション中 | 生活相談用の 2 択 QR（`_life_quick_reply()`）を再提示 + 「テキストで質問を送ってください。」 |
| session なし・学生 | 「メッセージありがとうございます😊 メニューから使いたい機能を選んでください。」+ `main_menu_quick_reply("student")` |
| session なし・保護者 | 同上 + `main_menu_quick_reply("parent")` |
| 役割未登録（role = None） | welcome Flex を再送（プレフィックス「メッセージありがとうございます。まずは役割を教えてください。」） |

**登録するイベント**:

`@handler.add(MessageEvent, message=<T>)` を以下 6 種で共通関数に多重登録する。

- `StickerMessageContent`
- `ImageMessageContent`
- `VideoMessageContent`
- `AudioMessageContent`
- `FileMessageContent`
- `LocationMessageContent`

**Gemini は呼ばない**: 内容の解釈は不要で、あくまで「次の操作を明示する」ためのフォールバック。呼び出しコストとハルシネーションリスクを避ける。

### 3.5 Loading indicator による中間応答の可視化

**目的**: Gemini 呼び出しなど 2 秒以上の待機が発生する箇所で、テキストの中間応答（「少し考えます…」等）に代えて LINE Messaging API の Loading Indicator を表示する。ユーザーには「Bot が入力中…」のアニメーションが提示され、テキストのゴミが残らず、モバイルで自然な UX になる（[LINE Developers ブログ 2024-04-17](https://developers.line.biz/ja/news/2024/04/17/loading-indicator/)）。

**LINE API**:

- Endpoint: `POST /v2/bot/chat/loading/start`
- SDK: `linebot.v3.messaging.MessagingApi.show_loading_animation(ShowLoadingAnimationRequest(chat_id, loading_seconds))`
- `chat_id` (必須): 表示対象ユーザー LINE userId
- `loading_seconds` (任意): 5〜60 秒、**5 の倍数** に限る（省略時サーバー既定 20 秒）
- Bot は `chat_id` に対して push 権限を持っている必要がある（既に稼働中の設定で満たす）
- **`reply_token` を消費しない**（reply_message とは独立ルート）

**プロジェクトの運用ルール**:

- `loading_seconds` の既定は **20 秒**。根拠: Gemini flash-lite の平均応答時間 3〜8 秒、想定最大 15 秒に対して余裕を持たせつつ、LINE Webhook 30 秒 timeout と 60 秒上限との衝突を避ける。
- 実装は `src/services/line_reply.py::show_loading(line_user_id, loading_seconds=20, raise_on_error=False)` に集約する。
- API 呼び出しが失敗（LINE 側障害・レート制限）しても Gemini 応答の push は必ず継続する（`raise_on_error=False` 既定）。中間表示が出ない実害は本応答が届くことで十分に緩和される。

**適用箇所**（Day 4 T4.11 で置き換え済み）:

| Handler | 削除する中間 reply | 追加する呼び出し |
| --- | --- | --- |
| `handlers/student.py::handle_life_consultation` | 「💭 少し考えます…」 | `show_loading(user_id)` |
| `handlers/student.py::handle_want_events` / `handle_want_students` | 「🤔 あなたに合いそうな活動を考えています…」 | `show_loading(user_id)` |
| `handlers/student.py::handle_activity_detail` | 「📖 「{title}」について調べています…」 | `show_loading(user_id)` |

いずれも緊急定型やエラー系の分岐が済んだ**直後、Gemini 呼び出しの直前**に配置する。緊急定型は待機時間が発生しないため Loading Indicator は不要。

## 4. 学生機能

### 4.1 FR-S1 / US-S01: 初回役割選択

**トリガー**: 友だち追加イベント、または `/start` `始める` `はじめる` 送信

**フロー**:

```
[bot] AI寮母へようこそ🏠 まずはあなたのことを教えてください。
      あなたはどちらですか？
      [Quick Reply]
        - 👨‍🎓 学生です
        - 👨‍👩‍👧 保護者です
```

**「学生です」選択後**:

```
[bot] こんにちは、学生さん！🎓
      まずはプロフィールを教えてもらえると、あなたに合った提案ができます。
      [Quick Reply]
        - ✍️ プロフィールを登録する
        - あとで登録する
```

**「保護者です」選択後**:

```
[bot] こんにちは、保護者の方！👨‍👩‍👧
      お子さんから招待コードを受け取っていますか？
      [Quick Reply]
        - 🔑 コードを入力する
        - まだもらっていない
```

**入力**: Postback（Quick Reply の data 属性で識別）

**永続化**:
- `data/users.json` にレコード追加
- `role: "student" | "parent"` を保存

### 4.2 FR-S2 / US-S02: 学生プロフィール登録・閲覧

**閲覧トリガー**（Day 4 改修）: 「👤 プロフィール」ボタン、または `プロフィール` `プロフ` 発話

- **登録済みユーザー**: `templates/flex/profile_view.py::build_profile_view_bubble` で自分の情報を Flex bubble として返す。Quick Reply `profile_view_quick_reply()` は `✏️ 編集する`（postback: `menu:profile_start`）と `🏠 メインメニュー`（postback: `menu:main`）の 2 項目。
- **未登録ユーザー**: 「プロフィールがまだ登録されていません」の system reply + `profile_start_quick_reply()`（`✍️ プロフィールを登録` / `あとで登録する`）。

**登録・再登録トリガー**: `✍️ プロフィールを登録`（postback: `menu:profile_start`）、または閲覧画面から `✏️ 編集する` を選択

- 登録済みユーザーが再登録に進んだ場合、`start_profile_flow` は「もう一度登録すると内容が上書きされます」旨を明示してから `profile.university` ステートに入る。

**対話ステート**:

| ステート | Bot 発話 | ユーザー入力 |
| --- | --- | --- |
| profile.university | 大学名を教えてください（例: 同志社大学） | テキスト |
| profile.faculty | 学部を教えてください | テキスト |
| profile.grade | 学年を教えてください（1〜4 or 院1・院2） | Quick Reply |
| profile.interests | 興味のあることを選んでください（複数OK） | Quick Reply の連続選択 |
| profile.effort | 最近頑張っていることを教えてください（未入力なら「スキップ」） | テキスト |
| profile.want_to_do | やってみたいこと・興味のあることを自由に教えてください | テキスト |
| profile.confirm | 内容を確認して登録しますか？ | Quick Reply（登録する / やり直す） |

**興味関心タグ候補**（Quick Reply）:
- 地域活動
- ボランティア
- スポーツ
- 音楽
- アート
- 学問・研究
- ものづくり
- 起業・ビジネス
- 国際交流
- 食・カフェ巡り

**入力キャンセル**: 対話中に「キャンセル」「やめる」で中断可能

**永続化**:
- `data/profiles.json` に学生プロフィールを保存
- キー: `line_user_id`

### 4.3 FR-S4 / US-S03: やりたいこと相談（主軸機能）

**トリガー**: 「🎯 やりたいこと相談」、または `やりたい` `おすすめ` 発話

**前提チェック**: プロフィール未登録なら FR-S2 に誘導（ハブ入場時に確認）

**フロー**:

トリガー直後は Gemini を呼ばず、まず**切り口を選ぶハブ**を Quick Reply で即応答する。
ユーザーが選んだブランチでのみ Gemini を呼び、活動カルーセルを返す。

```
[bot] （ハブ: 即応答、Gemini 未呼び出し）
      どんな切り口で探しますか？🔎

      [Quick Reply]
        - 👥 ほかの学生の取り組みを見る
        - 🏛️ 地域イベントを見る
        - 🏠 メインメニュー
```

**ブランチ A「🏛️ 地域イベントを見る」**（従来動作を維持）:

```
[bot] （プロフィール + 地域データ〈地域情報/店舗/イベント/先輩投稿〉を Gemini に渡す）
      提案を考えています…🤔

      [Flex Message カルーセル: 2〜3 バブル]
      ┌─────────────────────┐
      │ 🎯 提案 1                │
      │ [活動名]                 │
      │ [概要 2 文]              │
      │ 📍 場所 / 🕒 時期        │
      │ [ボタン: 詳しく聞く]     │
      │ [ボタン: 参加した]       │
      └─────────────────────┘
      ...

      [Quick Reply]
        - 🔄 他の案も見る（→ ハブに戻る）
        - メインメニュー
```

**ブランチ B「👥 ほかの学生の取り組みを見る」**（新規: SECI モデルの実践知導線）:

```
[bot] （プロフィール + 先輩投稿 seed + 匿名化した経験投稿を Gemini に渡す）
      先輩や仲間の取り組みをまとめています…🤔

      [Flex Message カルーセル: 2〜3 バブル]
      （バブル構造はブランチ A と共通。reference_type は senior_post / generated）

      [Quick Reply]
        - 🔄 他の案も見る（→ ハブに戻る）
        - メインメニュー
```

ブランチ B の入力は先輩投稿（seed）＋他の学生の経験投稿（匿名化）。投稿は匿名情報として
渡し、投稿者を特定できる情報（`line_user_id` 等）は渡さない（`06_ai_spec.md` §4.2 準拠）。
実行時の学生投稿が 0 件でも、先輩投稿 seed でフォールバックして必ずカルーセルを返す。

**「🔄 他の案も見る」**: どちらのブランチからでもハブ（切り口選択）に戻り、角度を選び直せる。

**Gemini 呼び出しへの入力**: `06_ai_spec.md` を参照

**「詳しく聞く」選択後**: 該当活動について追加情報を AI が回答

**「参加した」選択後**: 経験投稿フロー（FR-S6）に遷移、対象活動情報を pre-fill

**`reference_type: "generated"` の視覚ラベル**（NFR-Truth-1 対応）:

- Gemini が seed に完全一致するレコードなしで発想した提案は Flex Message の Header 上部に「🧭 AI 提案（要確認）」のサブラベルを付ける
- seed 由来（`event` / `volunteer` / `store` / `senior_post`）の提案とは背景色または見出しで区別
- ユーザーが「AI が組み立てた提案」なのか「先輩投稿由来」なのかを一目で判別できるようにする
- 実装場所: `src/templates/flex/activity_carousel.py`

**スポンサーPR枠の挿入（FR-S9）**:

やりたいこと相談の活動提案に、協賛企業イベント（就活・選考前提ハッカソン・ビジネスアイデア大会等）を PR 枠として掲載する。第3の収益源（`00_product_context.md §10.7`）の実証。ブランチ A / B の両方に適用する。

- **決定論的挿入**: Gemini が 2〜3 件を返した**後**に、コード側で `data/seed/sponsored.json` の案件をマッチングして挿入する。Gemini にはスポンサー情報を渡さない（日付・応募条件の言い換え・捏造を防ぐ）。
- **マッチング**: `active: true` の案件を学生プロフィールの `faculty` / `grade` / `interests` と `target`（`faculties` / `grades` / `interest_tags`）で突き合わせ、合致スコアの最上位 1 件を選ぶ。**合致案件が無ければ PR 枠は表示しない**（的外れな広告を強制しない）。
- **表示枠**: マッチした 1 件を**カルーセル先頭に別枠追加**する。通常提案は最大 3 件のまま（合計最大 4 バブル）。カルーセル上限は 10 バブル（§3.1）なので余裕がある。
- **視覚表示**（NFR-Truth 準拠）: `reference_type: "sponsored"` として、専用ヘッダー色（既存の青・緑・橙系と区別できるゴールド系）＋ヘッダーに「🏢 PR（協賛）」バッジを付与し、通常提案と一目で区別する。bubble 末尾に開示文「この案内は協賛企業からの提供です」と、既存の鮮度注記「※情報は変わっている可能性があります」を表示する。掲載テキストは seed の値をそのまま表示する。
- **ボタン**: 「詳細・応募はこちら」（URI アクション → seed の `apply_url`）＋「興味あり」（postback `sponsored:interest:{sponsor_id}` → クリックを計測）。通常カードの「詳しく聞く」「参加した」は付けない。
- **トラッキング**: 「興味あり」クリックを `data/sponsored_engagement.json` に記録する（`05_data_model.md §4.12`）。企業への効果指標・発表での反応数提示に用いる。LINE user_id はハッシュ化して保存し、生値は残さない。
- **実装場所**: マッチング・挿入は `src/services/`（新規、例 `sponsored.py`）、Flex は `src/templates/flex/activity_carousel.py`、postback 処理は `src/handlers/postback.py`。
- **enum**: `reference_type: "sponsored"` はコード注入型（`static_fallback` と同様に Gemini の JSON schema enum には追加しない）。詳細は `05_data_model.md §4.10.1`。

### 4.4 FR-S5 / US-S04: 生活相談

**トリガー**: 「💬 生活相談」を選んだ後の任意のテキスト、またはメニューを通さず直接テキスト送信

**情報源**（T4.10 で `data/posts.json` が加わる）:

- `data/seed/areas.json` — 地域情報（**実在**：同志社今出川周辺の公共施設・行政窓口等）
- `data/seed/stores.json` — 店舗情報（**実在**：民間実名店舗。`data_freshness_note` を必ず併記）
- `data/seed/senior_posts.json` — 先輩投稿（**架空**：プライバシー保護のため）
- `data/posts.json` — **他の学生が実際に投稿した経験**（匿名化して渡す。`docs/06_ai_spec.md §4.2` 匿名化ポリシー参照）

**フロー**:

```
[user] 熱っぽいんですけど、近くの病院ってどこ？

（Gemini に地域データ + 先輩投稿 + 匿名化した学生投稿を渡す。この間はネイティブの Loading Indicator を表示）

[bot 吹き出し1・共感] 熱っぽいんですね、それはつらいですね💦
      近くで受診できるところ、一緒に見てみましょう。

[bot 吹き出し2・本文] 37 度台の発熱なら、まずは近くの内科クリニックの受診が安心です。

      ・今出川周辺には徒歩圏の内科が複数あります
      ・先輩の体験より: 土曜の午前も空いていて待ち時間が短かったそうです

[bot 吹き出し3・締め] 症状が続くときや高熱のときは、無理せず医療機関へ。
      🆘 緊急なら #7119（京都府救急安心センター）へ。
```

回答は Gemini から `empathy`（共感）/ `answer`（本文）/ `closing`（締め）の JSON で受け取り、**最大 3 つの吹き出し**に分割して **1 回の push（通知 1 回）** でまとめて送る。`empathy` は相談内容に感情（つらさ・不安・体調）が読み取れるときだけ入り、事務的な質問では省略されて実質 2 吹き出しになる（詳細は「回答書式」参照）。

**特殊トピック検出**:
- キーワード: `救急`, `119`, `動けない`, `倒れた`, `血が` 等
  → 応答の冒頭で「119 番通報を推奨」を強調

**Gemini 呼び出し**: `06_ai_spec.md` の生活相談用プロンプトを参照

**回答書式**（Issue #13 対応、`docs/06_ai_spec.md §4.2` の書式ルールと同期）:

LINE は Markdown をレンダリングしないため、装飾記号を使わず構造化プレーンテキストで整える。回答は**最大 3 つの吹き出し**（共感 / 本文 / 締め）に分け、`services/line_reply.push_texts` で **1 回の push（通知 1 回）** としてまとめて送る。

1. Gemini プロンプトで JSON 出力構造を規定: `empathy`（共感の 1 文、感情が読み取れるときだけ）/ `answer`（結論先出し → 行頭「・」の箇条書き）/ `closing`（気遣い + 誘導）。`-`/`*`/`#`/`**` 等の Markdown 記号は使わせない。
2. `services/gemini._parse_life_json` で JSON を分解し、各フィールドを整形ヘルパー `src/utils/text_format.py` で Markdown 痕跡除去（`- `/`* ` の行頭を「・」へ、`**`/`` ` `` マーカー除去）・改行正規化する。
3. 「共感 → 本文 → 締め」の順に吹き出しへ割り付ける。空フィールドの吹き出しは送らない（`empathy` が空なら実質 2 吹き出し）。Zero-context 時は先頭を `ZERO_CONTEXT_DISCLAIMER`、医療系は締め末尾に `MEDICAL_FOLLOWUP` を連結する（割り付けは `docs/06_ai_spec.md §5.3.6` の表）。Quick Reply は**最後の吹き出し**に付ける。
4. **複数バブル採用の判断**: 旧仕様は「単一テキストバブル（Flex・複数バブルは不採用）」で会話感を維持する方針だったが、共感の一言と本文を別バブルに分けるほうが「人が続けて打っている」自然な会話感と可読性・温かみが増すと判断し、テキスト複数バブルへ方針転換した（Flex は引き続き不採用。会話感を損なうため）。
5. 緊急定型応答（`_EMERGENCY_*`）は既に整形済みのため本整形の対象外（単一 reply のまま）。「詳しく聞く」等ほかの Gemini 回答への横展開は将来検討。

**Zero-context 分岐**（NFR-Truth-2 対応、`docs/06_ai_spec.md §5.3` の実装フェーズで対応）:

`context_search.find_relevant_context(user_message)` の戻り値 `total_hits == 0` の場合、Gemini が seed に無い固有情報（電話番号・営業時間・特定店舗名）を捏造するリスクを避けるため、以下の分岐を行う。

1. Gemini プロンプトに「total_hits = 0」と件数を明示、「地名・電話番号・営業時間・特定の店舗名を絶対に断定しない」制約を強制
2. **先頭の吹き出し**を `ZERO_CONTEXT_DISCLAIMER`（`docs/06_ai_spec.md §5.3.4`）にする（この場合 `empathy` は省略）
3. `context_search.detect_medical_intent(user_message)` が真なら**締めの吹き出し末尾**に `MEDICAL_FOLLOWUP` を連結（NFR-Truth-3）
4. Quick Reply には「🏠 メインメニュー」と「🚫 相談を終える」を維持（最後の吹き出しに付与）
5. `zero_context: true` を journald にログ（§3.3）

**実在情報鮮度注記**（NFR-Truth-4 対応）:

seed の store / area レコードを回答に含める場合は、Bot 応答に必ず情報鮮度注記を付ける。生活相談はテキスト吹き出し運用（本節上部・§4.4「回答書式」）なので、Flex 側の対応は同節ではなくやりたいこと相談（§4.3）側で扱う。

- **生活相談（本文中で強制）**: プロンプト側で `_summarise_stores` / `_summarise_areas` が各 seed レコード末尾に `[情報鮮度: ...]` を付加する。Gemini はその値を抜き出して回答本文（`answer` フィールド）の末尾に `※ (値)` の形で 1 文添える。実装は `src/services/prompts.py` の `build_life_consultation_prompt`（【回答時の注意】節）。
- **やりたいこと相談 Flex カルーセル（bubble 末尾に汎用注記 box）**: `reference_type in {store, event, volunteer}` の bubble に、seed の実値は引き当てず「※情報は変わっている可能性があります」を一律で body 末尾に表示する。実装は `src/templates/flex/activity_carousel.py` の `_build_bubble`。個別の `data_freshness_note` の引き当ては将来の課題。

**Zero-context の応答例**（ゴミ出しの相談で seed カバー外の想定）:

```
[user] ゴミの分別が本当にわからなくて困っている

[bot 吹き出し1・disclaimer] ごめんなさい、この話題については先輩の投稿や地域の情報がまだ届いていません🙏
      以下は一般的なご案内なので、正確な情報は公式窓口でご確認くださいね。

[bot 吹き出し2・本文] 京都市は地区ごとにゴミ出しの曜日と分別ルールが異なります。
      お住まいの区役所や京都市エコまちステーションに直接お問い合わせいただくのが確実です。
```

**Zero-context + 医療系キーワードの応答例**:

```
[user] 頭が痛くて眠れない

[bot 吹き出し1・disclaimer] ごめんなさい、この話題については先輩の投稿や地域の情報がまだ届いていません🙏
      以下は一般的なご案内なので、正確な情報は公式窓口でご確認くださいね。

[bot 吹き出し2・本文] 無理をせず、症状が続くようでしたら医療機関を受診してくださいね。
      市販薬に頼る前に、まずは十分な休息と水分補給を試してみるのも良いかもしれません。

[bot 吹き出し3・締め] 体調のご相談は #7119（京都府救急安心センター）でも相談できますよ。
      京都市の医療機関検索サイトも参考になります。
```

### 4.5 FR-S6 / US-S05: 経験投稿

**トリガー**: 「✏️ 経験を投稿」、または FR-S4 の「参加した」ボタン、または `投稿` 発話

**対話ステート**（T4.15 で `post.title` 手入力を廃止し、title は LLM 自動生成に。全項目収集後に LLM 統合呼び出しで title 生成 + period 正規化を行う）:

| ステート | Bot 発話 | ユーザー入力 |
| --- | --- | --- |
| post.category | どのカテゴリの投稿ですか？ | Quick Reply |
| post.period | いつ・どのくらいの期間の話ですか？（例: 先週末 / 去年の10月） | テキスト（最大 100 文字、スキップ可） |
| post.summary | 何をしましたか？（できごとの概要） | テキスト（最大 300 文字、**必須**） |
| post.learned | 学べたこと・良かったことは？ | テキスト（最大 200 文字、**必須**） |
| post.regret | 残念だったこと・注意点は？ | テキスト（最大 200 文字、スキップ可） |
| post.advice | 次にやる人へのアドバイスは？ | テキスト（最大 200 文字、スキップ可） |
| post.area | 場所（地名・店名など、なければ「なし」/「無し」/`skip`/空文字） | テキスト（自由入力、seed 照合なし） |
| post.share_parent | 保護者に「頑張ったこと」として共有しますか？ | Quick Reply（👨‍👩‍👧 共有する / 🙅 共有しない） |
| （LLM 統合呼び出し） | Loading Indicator 表示中に Gemini が title 生成 + period 正規化 | — |
| post.confirm | 内容確認（AI title・正規化 period を提示）→ 投稿する / タイトルを変更 / やり直す | Quick Reply（✅ 投稿する / ✏️ タイトルを変更 / 🔄 やり直す） |
| post.title_edit | （タイトルを変更を選んだ場合）新しいタイトルを入力 | テキスト（最大 40 文字）→ 確認へ戻る |

**構造化 5 問のねらい**: 旧 `post.body`（丸投げの自由記述）は情報量・粒度がユーザー任せで、蓄積される投稿の質がばらついていた。期間・概要・学び・残念・アドバイスに分解して質問することで、粒度を揃え、保護者月次レポートの読み応えと SECI モデル（他学生の生活相談 context）の継承精度を同時に底上げする。

**LLM 統合呼び出し（title 生成 + period 正規化、T4.15）**:

- `post.share_parent` の選択直後、全項目が揃った時点で **1 回だけ** Gemini を呼ぶ（`show_loading` で Loading Indicator を表示中に実行し、確認カードは push で後送）。この 1 回で title 生成・period 正規化・**妥当性判定**をまとめて行う。詳細は `docs/06_ai_spec.md §4.5`。
- **title 自動生成**: `summary` / `learned` 等の内容から 40 文字以内の見出しを生成する。ユーザーは確認カードで採用するか、`✏️ タイトルを変更` から編集できる。
- **period 正規化**: ユーザーの相対表現（生入力 `period_raw`、例「去年の10月」）を投稿時点（`created_at`）を基準に絶対表現（例「2025年10月」）へ変換して `period` に保存する。生の言葉は `period_raw` に残す。
- **妥当性判定（`valid`）**: 抽選・クーポン目的の無意味/虚偽の投稿が蓄積データ（保護者月次・他学生への SECI context）を汚染するのを防ぐ品質ゲート。判定は追加の LLM 呼び出しを増やさず上記の統合呼び出しに相乗りさせる。
  - `valid == false` の場合、**確認カードへ進めず投稿を保存しない**。固定警告文（事実と異なる/意味をなさない投稿が続くと機能の利用を制限する場合がある旨）を返してフローを終了する。
  - **ただし抽選（FR-S11）は引かせる**（デモ演出として体験を止めない。§4.9 参照）。保存しないため FR-S10 クーポンの投稿数カウントには加算されず、保護者共有・他学生 context にも載らない。
  - 判定は **false=明らかに無意味/虚偽/中身の伴わない抽選目的の投稿のみ、迷う場合は true（通す）** とし、誤検知（正当な投稿を弾く）を厳に避ける。警告は固定文言での牽制に留め、連続回数のカウントや自動利用停止は持たない（今後の展望、§4.9 参照）。
- **フォールバック（フローを止めない）**: LLM 失敗・空応答・JSON パース失敗・`GEMINI_MOCK_MODE` の場合、title は `summary` の冒頭 40 文字、period は `period_raw` をそのまま採用し、**`valid` は `true`（弾かず通す）** とする。
- プロフィール依存の表現（「大学1年の頃」等）は now 基準だけでは絶対化しきれないため、LLM のベストエフォートとし、曖昧なものは概ねの表現のまま残す（プロフィール投入は将来拡張）。

**スキップ規則**: `post.period` / `post.regret` / `post.advice` は任意。`スキップ` / `skip` / `なし` / `無し`（大小文字区別なし）または空文字を送るとそのフィールドは未入力（`null`）として扱う。これらのステップの Quick Reply には「⏭️ スキップ」ボタンを出す。`post.summary` / `post.learned` は必須で、空入力時は再入力を促す。スキップ判定は `src/services/posts.py::_normalize_skippable` に集約し、area 正規化（`_normalize_area`）も同ヘルパーに委譲する。

**body 合成規則**: 上記 5 フィールドは個別に保存すると同時に、非空フィールドのみを

```
【いつ】…
【やったこと】…
【学び】…
【残念・注意】…
【次の人へ】…
```

の形式で連結した `body`（合成派生フィールド）も生成・保存する。月次レポートのプレビューと SECI context（`list_all_for_context`）は従来どおり `body` を読むため、下流は無改修で動く。先輩投稿 seed（`senior_posts.json`、`body` 単一）とも共存できる。合成後の `body` 保存上限は 1200 文字。

**カテゴリ Quick Reply**（10 カテゴリ + キャンセル = 11 項目、LINE 上限 13 以内）:
- 🏛️ 地域イベント (`event`)
- 🧹 ボランティア (`volunteer`)
- 🍜 お店・カフェ (`store`)
- 🏥 病院・薬局 (`medical`)
- 📋 手続き・生活の知恵 (`tips`)
- 🎓 学び・勉強 (`study`)
- 💰 バイト・お金 (`money`)
- 🤝 サークル・交友 (`social`)
- 💪 がんばったこと (`effort`)
- ✨ その他 (`other`)
- 🚫 キャンセル

**area フィールドの正規化**:
- 空文字、`なし`、`無し`、`skip`（大小文字区別なし）は `area=null` として保存。
- それ以外の入力は seed `areas.json` との照合を行わず、そのまま文字列として保存する（デモ用途では手打ち入力を許容）。

**キャンセル・予約語割り込み**（§7 に準拠）:

対話中の `キャンセル` / `やめる` / `戻る` 発話は session を全リセットして idle に戻す。その他の予約語（`メインメニュー` / `ヘルプ` / `プロフィール` / `招待` / `連携` / `レポート` 等）が来た場合も同様に全リセットしてから対象アクションを実行する。

**永続化**:
- `data/posts.json` に追加
- `share_with_parent: bool` で共有フラグ管理
- `post_id` は `P` + 5 桁連番（`_next_post_id`）
- 実装: `src/services/posts.py::add_post`

**⚠️ `share_with_parent == True` フィルタの回帰リスク**:

月次サマリー（Pull・Push いずれも）は `share_with_parent=true` の投稿のみを保護者に見せる。`list_month_shared` の filter を外すと `false` 投稿が漏れる致命的なプライバシー事故になるため、実装・レビューで最重要不変条件として扱う。

**他学生の生活相談 context への継承**（T4.10、SECI モデル）:

経験投稿は `share_with_parent` フラグとは独立に **全件がデフォルトで他学生の生活相談 context** の対象となる（`docs/06_ai_spec.md §4.2` 参照）。ただし Gemini に渡すのは匿名化した `title` / `body` / `area` / `category` / `created_at` のみで、投稿者の LINE userId・プロフィール・`post_id` は伝播させない。学生には投稿完了時に「後輩の役に立ちます」を暗黙的に伝えられる文言を将来加える余地はあるが、MVP スコープでは投稿画面の UI 変更なし（黙示的な共有）。この方針は SECI モデルの「暗黙知の形式知化」を実装で体現する中核ルールとして扱う。

### 4.6 FR-S7 / US-S06: 招待コード発行

**トリガー**: 「👨‍👩‍👧 保護者連携」、または `招待` 発話

**フロー**:

```
[bot] 保護者の方向けの連携コードを発行します。
      👨‍👩‍👧 保護者を LINE で AI 寮母を友だち追加してもらい、
      以下のコードを入力してもらってください。

      ┌──────────────────┐
      │  🔑 コード: A3F7K9  │
      │  有効期限: 24 時間  │
      │  1 回限り有効       │
      └──────────────────┘

      共有用のメッセージをコピーできます:
      「AI寮母を追加してこのコード [A3F7K9] を入力してね」

      [Quick Reply]
        - 📋 メッセージをコピー
        - ↺ 新しいコードを発行
        - メインメニュー
```

**コード仕様**:
- 6 桁の英数字（大文字のみ、`I` `O` `0` `1` は除外して視認性確保）
- 使用文字集合: `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`（32 文字）
- 有効期限: 発行から 24 時間
- 1 回使うと無効化
- 衝突チェック: 発行時に `find_active(code)` で pre-check し、衝突時は最大 5 回リトライ

**再発行時の旧コード invalidate**:

同一学生が既に発行済みの未使用（`used_at IS NULL`）かつ未期限切れコードは、新規発行の直前に一括で `used_at=now`, `used_by_parent_id="__revoked__"` にマークして無効化する。**同時有効なコードは常に 1 個** という不変条件を守る。実装: `src/services/invitations.py::issue_code`。

**発行完了後の idle 状態の扱い**（M3 対応）:

招待コード Flex を受け取った直後の学生は session 状態を持たず（発行は単発トリガー）、次に自由テキストを送信すると `handlers/message.py` のフォールバックで生活相談ルートに落ちる。これは意図しない Gemini 呼び出しを引き起こすため、発行完了応答のテキストには「メニューから選択してください」の誘導文を含め、Quick Reply（再発行 / メインメニュー）で次のアクションを明示する。

**永続化**:
- `data/invitations.json` に保存
- フィールド: `code`, `student_user_id`, `created_at`, `expires_at`, `used_at`, `used_by_parent_id`

### 4.7 FR-S8: 頑張ったこと記録

FR-S6 の `share_with_parent: true` で投稿されたレコードのうち、当月分を月次サマリー生成の入力として使う。

### 4.8 FR-S10 / US-S06: クーポン配布（デモ）

経験投稿（FR-S6）が一定数たまるごとに、地域店舗クーポンを Flex Message で配布する。「知識共有 → インセンティブ獲得 → 地域消費 → 地域活性化」の循環（`00_product_context.md §10.5`）を、決勝プレゼンで実際に動く画面として見せるためのデモ機能。**引き換え・消込・ポイント台帳は持たず、見た目の配布のみ**を行う（本物のクーポン機能は `02_mvp_scope.md §4.1` で除外のまま）。

- **トリガー**: 経験投稿の確定処理（`src/handlers/student.py::_finalize_post`）で投稿を保存した**後**に判定する。母数はその学生の**全経験投稿数**（`share_with_parent` の ON/OFF を問わない。デモで確実に発火させるため）。
- **配布条件（決定論的）**: `N = posts.count_all(user_id)`（新設）とし、節目 `milestone = (N // 3) * 3` を求める。`milestone >= 3` かつ `milestone > last_awarded_milestone`（前回配布済みの節目）のときに 3 種を配布する。同一節目での二重配布は `last_awarded_milestone` の単調増加チェックで防止する。
- **配布内容のローテーション**: `data/seed/coupons.json` の `active: true` クーポンから、節目ごとに異なる 3 種を選ぶ。バッチ番号 `batch = (milestone // 3) - 1`（0 始まり）とし、`active_coupons[(batch * 3 + i) % len(active_coupons)]`（i=0,1,2）で循環スライスする。seed 件数が 3 の倍数でなくても常に 3 件取れ、使い切ったら先頭へ戻る。
- **表示枠**: 3 種を**クーポン専用カルーセル**（最大 3 バブル）で配布する。やりたいこと相談の活動カルーセルとは別テンプレート。
- **視覚表示**: 各バブルに店舗名・クーポン名・割引内容・有効期限（`valid_until`）を表示する。店舗は架空のため実在情報の鮮度注記は付けない（`05_data_model.md §4.15` の設計判断参照）。掲載テキストは seed の値をそのまま表示する。
- **ボタン**: 「お店で使う」（URI アクション → seed の `store_url`。架空 URL）。消込・状態変化を伴う postback は持たない。
- **配信方法**: 投稿完了応答（reply）の後に、`push_flex` でクーポンカルーセルを追加配信する（カルーセルは reply でなく push を使う既存慣行に合わせる。`src/handlers/student.py` の活動カルーセル送信と同様）。
- **トラッキング**: 配布実績を `data/coupon_distributions.json` に記録する（`05_data_model.md §4.16`）。学生ごとに `last_awarded_milestone` と配布履歴を持ち、重複防止と発表での配布回数提示に用いる。トップレベルキーは生の `line_user_id`（`usage_stats.json` 等と同一規約）。
- **実装場所**: 配布ロジックは `src/services/coupons.py`（新規）、seed ロードは `src/services/seed.py`、Flex は `src/templates/flex/coupon_carousel.py`（新規）、結線は `src/handlers/student.py::_finalize_post`。
- **状態遷移**: 新しい会話ステートは導入しない（投稿確定の副作用として push するのみ）。URI ボタンは外部遷移のため postback ルーターの変更も不要。

### 4.9 FR-S11 / US-S07: プレゼントくじ引き（デモ）

経験投稿を完了するたびにくじを 1 回引ける等級制の抽選。当落を Flex Message で演出し、投稿インセンティブ
（`00_product_context.md §14.6`）を決勝プレゼンで印象的に示すためのデモ機能。**リスクを負わない設計**を徹底する。

- **リスク回避（すべてスコープ外＝今後の展望）**: 実物賞品の配布・発送、当選者の個人情報（氏名・住所・連絡先）の
  収集/保存は**一切行わない**。景品表示法の懸賞規制は「実際に景品を提供する」ときに発動するため、実提供のない本デモ演出は
  非該当（`02_mvp_scope.md §4.1` に除外を明記）。当選者 PII 非収集は `.codex/rules/project_rules.md` の個人情報方針にも明記する。
- **くじを引くタイミング**: 経験投稿を完了するたびに**自動でくじを 1 回引く**（はずれを含む）。応募口数の概念は持たない。
  - **妥当性チェックで弾かれた投稿でも抽選は引く**（§4.5 の `valid == false`）。抽選体験を止めないためのデモ演出上の判断で、保存はしない一方で抽選だけは実行し、当落 Flex を push する。
  - この結果、抽選当選チャンス目的の連投自体は技術的には防がない（意図的な許容）。抑止は、弾かれた投稿が保存されない（クーポン加算・保護者共有・他学生 context に載らない）ことと、§4.5 の固定警告文による牽制に留める。連続回数カウント・自動利用停止は今後の展望。
- **等級構成**: 1 等（テーマパーク ペアチケット）／ 2 等（地元名店 ペアお食事券）／ 3 等（地域店舗クーポン）／はずれ。
  2 等・3 等は地域とのつながりを感じられる賞品に寄せる。上位等ほど当選確率を低くする
  （デモ演出用の既定値、`prizes.py` の確率テーブル）。デモ本番は手動トリガーで等級を指定して確実に発火する。
- **賞品**: `data/seed/prizes.json` の架空賞品に等級（`rank`）を持たせる。架空である旨は皆が理解している前提のため賞品名での
  「架空」明示は最小限にとどめ、誤認防止の注記は演出 Flex 側に小さく 1 行だけ添える。
- **抽選ロジック**: `prizes.draw(user_id, *, force_rank=None)`。乱数（`random`）で等級テーブルに従い当落・等級を決めるが、
  `force_rank` 指定時は等級を固定する（1〜3 で各等、`0` ではずれ）。抽選シードと結果を `prize_draws.json` に記録し、再現性・
  公正性の体裁を残す。**PII は保存しない**。
- **当落演出**: 専用 Flex（`src/templates/flex/prize_result.py`）。当選は等級バッジ＋賞品名の演出に加え、当選番号（抽選 seed 流用）・
  有効期限（ダミー、`valid_until`）・利用条件（`note`）を記した情報カードを添えて当選感・特別感を出す。はずれは「また投稿して挑戦」。
  単一バブルで表示し、`size:"mega"` は用いず折り返しの起きないコンパクトなレイアウトにする。小さく「デモ演出」注記を 1 行添える。
- **配信方法**: 当落演出は `push_flex` で送る（FR-S10 と同じ push 慣行）。投稿確定の副作用として自動で 1 回引き、結果を push する。
- **抽選トリガー（デモ）**: `scripts/trigger_prize_draw.py`（`--rank 1|2|3` / `--lose` / `--dry-run` / `--list`）で等級を指定して
  確実に演出できる。デモ本番はこれで 1 等を確実に出す（確率任せの事故を防ぐ）。
- **トラッキング**: 抽選結果を `data/prize_draws.json` に記録（`05_data_model.md §4.18`）。学生ごとに抽選履歴（等級・結果・seed）を
  持つが、**氏名・住所・連絡先は保存しない**。トップレベルキーは生の `line_user_id`（既存規約）。
- **実装場所**: 抽選ロジックは `src/services/prizes.py`、seed ロードは `src/services/seed.py`、Flex は
  `src/templates/flex/prize_result.py`、手動発火は `scripts/trigger_prize_draw.py`、結線は `src/handlers/student.py::_finalize_post`。
- **状態遷移**: 新しい会話ステートは導入しない（投稿確定の副作用として自動抽選・push）。

## 5. 保護者機能

### 5.1 FR-P1 / US-P01: 保護者役割選択

FR-S1 のフローで「👨‍👩‍👧 保護者です」を選択したケース。以降は保護者向けメニューを表示。

### 5.2 FR-P2 / US-P02: 招待コード入力

**トリガー**: 「🔑 コードを入力する」、または `連携` 発話

**対話ステート**（Day 3 の実装は `link.code` の 1 状態、学生名確認は省略）:

| ステート | Bot 発話 | ユーザー入力 |
| --- | --- | --- |
| link.code | お子さんから受け取った 6 桁のコードを入力してください（英数字） | テキスト（コード） |

MVP では学生プロフィールに `display_name` が無いため、`link.verify` の学生名提示ステップは省略し、consume 成功時にすぐ連携完了応答を返す。将来 `display_name` を追加した際に `link.verify` を再導入する（`docs/09_tasks.md` の Day 4 以降 TODO）。

**検証エラー分類**（consume 戻り値 `error_reason` と応答文言）:

| `error_reason` | 発生条件 | ユーザー向け応答 |
| --- | --- | --- |
| `not_found` | 形式は 6 桁英数だが該当レコードなし | 「そのコードは見つかりませんでした。学生さんに新しいコードを発行してもらってください。」 |
| `expired` | `expires_at` 過去 | 「そのコードは有効期限が切れています。学生さんに新しいコードを発行してもらってください。」 |
| `used` | `used_at` 既値（別保護者に使用済み or `__revoked__`） | 「そのコードは既に使われています。学生さんに新しいコードを発行してもらってください。」 |
| `self_link` | 発行学生と入力保護者が同一 LINE userId | 「ご自身が発行したコードは使用できません。別の LINE アカウントで保護者役として登録してください。」 |

上記いずれの場合も `session.increment_fail_count()` で失敗回数をインクリメントする。**5 回連続失敗（既存 `session.MAX_FAIL_COUNT = 5` に一致）で session を全リセットし、welcome + 役割選択 QR を返す**（B4 対応）。形式チェック（6 桁英数字大文字、`I`/`O`/`0`/`1` 以外）NG も同じフローで失敗カウントする。

**検証成功時の副作用**:
- `data/invitations.json` を更新（`used_at=now`, `used_by_parent_id=parent_line_user_id`）
- `data/parent_links.json` に `(parent, student, linked_at, active=true)` を保存（既存レコードがあれば冪等に上書き）
- 学生の LINE user へ連携完了 push
- 保護者側にも連携完了応答 + main menu QR を返す

**副作用**: 連携完了と同時に「今月のレポート」がメニューに追加される。

### 5.3 FR-P3 / US-P03: 月次サマリー閲覧

**配信方式**: Pull（保護者トリガー）と Push（毎月自動）の併用。

| 方式 | トリガー | 集計対象年月 |
| --- | --- | --- |
| Pull | 「📊 今月のレポート」、`レポート`、`頑張ったこと` 発話 | **当月**（送信時点の JST 当月 1 日 00:00 〜 送信時点） |
| Push | systemd timer（毎月 1 日 JST 09:00）+ 手動再実行 CLI | **前月**（`target_year_month` の 1 日 00:00 〜 末日 23:59 JST） |

**Pull フロー**（保護者側から `handle_monthly_report`）:

```
[bot] （data/posts.json から連携先学生の当月投稿を取得、share_with_parent=true のみ。
       前月件数と全期間通算件数、data/usage_stats.json の当月カウントも合わせて読む。
       Gemini で月次総括コメントを 1 本生成する。）

      [Flex Message]
      ┌──────────────────────────────┐
      │ 📊 あなたのお子さんの今月     │
      │ 2026-07                        │
      │ ─────────────────────────── │
      │ 🌸 頑張ったこと 2 件            │
      │    （先月 0 / 通算 5）         │
      │   🎓 期末レポートを提出        │
      │   🤝 サークルの新歓を手伝った  │
      │ ─────────────────────────── │
      │ 🏠 今月の利用                  │
      │   相談 12 回（生活 8 / 活動 4）│
      │   記録・更新 4 回              │
      │       （投稿 3 / プロフィール 1）│
      │ ─────────────────────────── │
      │ 💬 AI寮母より                  │
      │   「今月も前向きに過ごされて   │
      │    いる様子です」              │
      └──────────────────────────────┘
```

**表示内容（第1層＋第2層）**:

- **頑張ったこと**（第1層、原資 `posts.json`）: 最大 5 件、カテゴリ絵文字付き。件数見出しに **先月比**（前月の `share_with_parent=true` 件数）と **全期間通算**（`posts.count_all_shared`）を並べて表示する。
- **今月の利用**（第2層、原資 `usage_stats.json`）: 生活・活動相談の合計（内訳付き）と、記録・更新（経験投稿・プロフィール保存）の合計（内訳付き）を 2 行で表示。詳細な加算タイミングは `docs/05_data_model.md §4.14` を参照。
- **AI寮母より**（第1層、Gemini 総括）: 当月の共有投稿タイトルと利用回数のみを入力として、2〜3 文の温かい総括を生成する。医療診断・法律断定・事実捏造は禁止（`docs/06_ai_spec.md` の月次総括プロンプト規約）。

**少回数フォールバック**（第2層のみ）:

- 相談合計（生活＋活動）が **3 回未満**なら回数を出さず、「今月も自分から相談していました」等の定性表現に切り替える。
- 記録・更新合計が **0 回**なら「今月の利用」の 2 行目は非表示にする。
- 上記の判定は `services/monthly_report.py` 側で `report.usage` を見て決定し、Flex 側は与えられた文字列/フラグを描画するだけとする（表示ロジックを service に寄せる）。

**AI 総括のフォールバック**（第1層のみ）:

- 当月の共有投稿が 0 件、かつ相談合計が 3 回未満のときは Gemini を呼ばず、「今月もお子さんは元気に過ごされている様子です」等の定型文を `report.ai_summary` に格納する（`GEMINI_MOCK_MODE` および Gemini API 失敗時も同じ定型文にフォールバック）。

**Push フロー**（`scripts/push_monthly_reports.py` → `monthly_report.push_previous_month_to_all`）:

1. `parent_links.list_all_active_pairs()` で `(parent, student)` を列挙
2. 各ペアについて `posts.list_month_shared(student, year, month)` を取得（`share_with_parent=true` のみ）
3. 0 件なら **送信スキップ**（無音、`counters.empty++`）
4. 1 件以上なら Flex を組み立て `push_flex(parent, ...)` で送信、成功なら `counters.sent++`
5. LineBotApiError 等は per-parent 個別 catch → `counters.errors++`、次の宛先に継続
6. batch 結果を `data/monthly_report_state.json` に記録（同 `target_year_month` の記録があれば skip、`--force` で上書き可）

**該当データなしの場合の非対称ルール**（B5、FR-P3 拡張後も維持）:

- **Pull（当月 0 件）**: 頑張ったこと 0 件かつ利用回数も 0 回のときは、従来どおり「今月はまだ頑張ったことの記録がありません。少し様子を見てあげてくださいね😊」テキスト + main menu QR で返す。頑張ったこと 0 件でも利用回数が 1 回以上あれば **Flex を返す**（第2層と AI 総括が空を埋めるため）。
- **Push（前月 0 件）**: 頑張ったこと 0 件かつ利用回数も 0 回のときのみ送信スキップ（無音、`counters.empty++`）。利用回数がある場合は第2層＋AI 総括だけの Flex を送る（月初の「何もない体験」を回避）。

**連携時の同意透明性**（FR-P3 拡張の必須要件）:

第2層（相談回数）を共有するためには、学生本人が「利用状況も保護者に共有される」ことを知った上で招待コード発行〜連携完了に進めるようにする。個別トグル UI は作らず、連携＝一括同意で扱う。以下の文言に共有対象を明記すること:

- 学生側：招待コード発行時の案内（`handlers/student.py::start_invitation_flow` および招待 Flex）で「頑張ったことに加え、生活・活動相談の利用状況（回数）も保護者に共有されます」を明示。
- 保護者側：`handlers/parent.py::LINK_PROMPT` および `_LINK_COMPLETED_PARENT` に「学生さんが共有した頑張りと、生活・活動相談の利用状況（回数）が届きます」と明示。

**「メッセージを送る」ボタン**（Day 4 以降に持ち越し）:

保護者から学生への励まし送信機能は Day 4+ の T4.1a と併せて設計する。Day 3 の Flex には該当ボタンを **出さない**（Flex 内の footer は最大 5 件の投稿リストで完結）。

**当月境界の判定**（`services/monthly_report.py`）:

- Pull: `now = datetime.now(JST)` を取り、`start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)`、`end = now`。
- Push: `target_year_month = "YYYY-MM"` から `start = first day 00:00 JST`、`end = last day 23:59 JST`。
- 月末境界のズレ防止のため、systemd timer は `OnCalendar=*-*-01 09:00:00 Asia/Tokyo` で 09:00 JST に固定。ダウンタイムを跨いだ場合は `Persistent=true` で起動時に一度だけ追実行される。

## 6. 共通機能

### 6.1 FR-C1: ヘルプ

**トリガー**: `ヘルプ` `使い方` `help`

**役割別に案内文言を分岐**:

学生向け:
```
[bot] AI寮母の使い方 🏠
      🎯 やりたいこと相談 - あなたに合う活動を提案
      💬 生活相談 - 生活のお困りごとに答える
      ✏️ 経験を投稿 - 参加した活動や利用したお店を記録
      👤 プロフィール - 情報の確認・更新
      👨‍👩‍👧 保護者連携 - 招待コード発行

      その他: 「役割変更」で保護者役に切替可能
```

保護者向け:
```
[bot] AI寮母の使い方 🏠
      📊 今月のレポート - お子さんの頑張り確認
      🔗 学生と連携 - 招待コードで学生と紐付け
      ❓ ヘルプ - この案内
```

### 6.2 FR-C2: 役割再選択

**トリガー**: `役割変更` `切り替え` 発話

**フロー**:

```
[bot] 現在は [学生 / 保護者] として利用中です。
      切り替えますか？
      [Quick Reply]
        - はい、切り替える
        - キャンセル
```

**注意事項**:
- 切り替えても既存プロフィール・連携情報は削除しない
- MVP 期間内はテスト・デモ用の切り替え機能として実装

### 6.3 FR-C3: Quick Reply / Flex Message

- 全ての主要操作にボタン導線を用意
- テキスト入力必須の場面（プロフィール、投稿本文）以外はできるだけボタンで完結
- Flex Message は `templates/` にテンプレートとして分離

## 7. 会話ステートマシン概要

各機能の対話ステート（`profile.*`, `post.*`, `link.*`）はセッションに保存され、次のメッセージで遷移。

**主なステート**:
- `idle` — 通常状態、メインメニューの選択待ち
- `onboarding.role` — 役割選択待ち
- `profile.university` 〜 `profile.confirm`
- `post.category` → `post.title` → `post.body` → `post.area` → `post.share_parent` → `post.confirm`
- `link.code`（1 状態、`link.verify` は Day 3 時点では省略、§5.2 参照）
- `life.waiting`（生活相談）

**キャンセルコマンド**: 対話中でも `キャンセル` `やめる` `戻る` で `idle` に戻れる

**予約語ルーティングの優先順位**（`handlers/message.py` で実装）:

対話フロー中に以下の予約語が来た場合、**session を全リセットしてから対象アクションを実行**する。session state の途中でも予約語が優先される。

| カテゴリ | 発話例 | 挙動 |
| --- | --- | --- |
| キャンセル | `キャンセル` / `やめる` / `戻る` | session 全リセット → `_reply_placeholder`（役割別 main menu QR） |
| メニュー | `メインメニュー` / `menu` | session 全リセット → main menu 応答 |
| リスタート | `はじめる` / `始める` / `スタート` / `/start` | session 全リセット → welcome 応答 |
| ヘルプ | `ヘルプ` / `使い方` / `help` | session 全リセット → 役割別ヘルプ |
| プロフィール | `プロフィール` / `プロフ` | session 全リセット → プロフィール閲覧（登録済み） / 登録誘導（未登録）（学生） |
| やりたいこと | `やりたい` / `おすすめ` | session 全リセット → やりたいこと相談ハブ（切り口選択）を表示（学生、§4.3） |
| 生活相談 | `生活相談` / `相談` | session 全リセット → 生活相談開始（学生） |
| 経験投稿 | `投稿` / `経験` | session 全リセット → 経験投稿開始（学生） |
| 招待 | `招待` / `コード` | session 全リセット → 招待コード発行（学生） |
| 保護者連携 | `連携` | session 全リセット → 招待コード入力開始（保護者） |
| レポート | `レポート` / `頑張ったこと` | session 全リセット → 月次サマリー Pull（保護者） |

役割不一致の場合は `_require_role` で welcome/エラー応答に流す。

**タイムアウト**: 10 分無操作でセッション削除、次回発話時は `idle` から

## 8. Flex Message テンプレート方針

- `templates/flex/` 配下に各テンプレートを分離
- 主要テンプレート:
  - `welcome.py` — ウェルカム + 役割選択
  - `activity_carousel.py` — やりたいこと提案（2〜3 バブル）
  - `monthly_report.py` — 月次サマリー
  - `invitation_code.py` — 招待コード表示
  - `profile_view.py` — プロフィール閲覧（Day 4 追加）
  - `coupon_carousel.py` — クーポン配布（3 バブル、FR-S10。Day 4 追加）
  - `prize_result.py` — プレゼントくじ引きの当落演出（等級表示、FR-S11。Day 4 追加）
- テンプレートは build 関数として実装（既存 `kcb_linebot/flex_templates.py` と同様のパターン）
- **共通スタイルモジュール `templates/flex/style.py` 経由で白基調・アクセントバー基調に統一**（T4.13）。
  白ヘッダー＋navy 細アクセントバー、本文は余白＋hairline のエアリー意匠。カラートークン・アクセント
  バー生成などを単一情報源として集約し、5 builder が参照する。§4.3 の seed / AI 提案 / sponsored PR の
  視覚的区別（sponsored はゴールドのアクセントバー＋バッジ＋開示文）はデザイン刷新後も維持する。

## 9. 応答性能

- Gemini 呼び出しを伴う応答は 30 秒以内（LINE Webhook 制約）
- 目標: 平均 5 秒、最大 15 秒
- 30 秒に近づく場合は「もう少し考えます…」の中間応答（PushMessage）を送る

## 10. 変更履歴

| 日付 | 変更内容 | 記入者 |
| --- | --- | --- |
| 2026-07-05 | 初版作成 | kmch4n |
| 2026-07-06 | §4.3 に generated ラベル、§4.4 に Zero-context 分岐フローと応答例、§3.2 のエラー表に関連情報 0 件行、§3.3 に構造化ログフィールド 4 種を追記 | kmch4n |
| 2026-07-06 | §3.4 終端応答の Quick Reply 付与ルール新設、§3.5 送信者アイコン切替（Sender switch）仕様新設、§3.2 エラー表にキャンセル・placeholder 行と QR 付与補足列を追加 | kmch4n |
| 2026-07-06 | Day 3 家族ループ仕様を確定: §3.3 に月次 push ログ 7 項目、§3.5 に Day 3 期間 sender 未指定の暫定運用、§4.5 に 6 ステップ・area 正規化・share_with_parent 不変条件、§4.6 に再発行 invalidate と発行後 idle の誘導、§5.2 にエラー 4 種と 5 回失敗リセット、§5.3 に Pull/Push 併用・非対称ルール、§7 に予約語ルーティング優先順位表 | kmch4n |
| 2026-07-06 | Day 4 T4.1b Sender switch を実装完了: §3.5 の暫定 friendly 注記を撤回し、`line_reply` に `sender` 引数と `SENDER_PRESETS` の呼び出し実態、および friendly/system/notify それぞれの現行呼び出し場所を反映 | kmch4n |
| 2026-07-06 | §4.4 生活相談の情報源に `data/posts.json` を追加、§4.5 経験投稿に「他学生の生活相談 context へ全件匿名化継承」ポリシーを追記（T4.10 の docs-first 更新、SECI モデル体現） | kmch4n |
| 2026-07-06 | §4.2 プロフィール閲覧仕様を新設: 登録済みユーザーは Flex bubble で自分の情報を表示、未登録は登録誘導に振り分ける（Day 4 UX 改善、`👤 プロフィール` ボタンが即座に上書き入力を要求する挙動を撤廃） | kmch4n |
| 2026-07-06 | §3.4-b 非テキストメッセージのフォールバック仕様を新設: スタンプ・画像・動画・音声・ファイル・位置情報の 6 種を単一ハンドラで受け、session/role に応じて Quick Reply 付きの誘導を返す（Day 4 UX 改善、無応答による導線消失を撤廃） | kmch4n |
| 2026-07-06 | §3.4 終端応答 QR ルールに push_text / push_flex 経由の非同期通知を明示追加。連携完了時の学生側 push、追加学生の月次 push、想定 0 件フォールバックなど 5 箇所の QR 抜けを解消（Day 4 UX 改善） | kmch4n |
| 2026-07-06 | §3.6 Loading indicator による中間応答の可視化を新設（Day 4 T4.11 の docs-first）: SDK/API 仕様・20 秒既定・Sender switch との直交性・適用 3 handler の対応表 | kmch4n |
| 2026-07-06 | §2.2 メインメニューに「リッチメニュー本実装は決勝プレゼン後、当面 Quick Reply モックで運用」を追記 | kmch4n |
| 2026-07-07 | §4.4 生活相談に「回答書式」小節を新設し構造化プレーンテキスト（結論先出し・「・」箇条書き・空行区切り・Markdown 不使用・単一バブル維持）を規定、フロー例を差し替え（Issue #13 の docs-first。`docs/06_ai_spec.md §3`/§4.2 と同期） | anluck-m |
| 2026-07-07 | §4.5 経験投稿のカテゴリ Quick Reply に `study`/`money`/`social`/`effort` の 4 種を追加（6→10 カテゴリ、`tips` 後・`other` 前。Issue #14 の docs-first 更新） | anluck-m |
| 2026-07-08 | §4.4 実在情報鮮度注記を単一テキストバブル運用に整合させて書き直し（Phase 3）: 生活相談は `_summarise_stores` / `_summarise_areas` が付加する `[情報鮮度: ...]` をプロンプトで Gemini に強制引用させる方式に、Flex 側は §4.3 やりたいこと相談 bubble の汎用注記 box 方式に分離 | kmch4n |
| 2026-07-08 | §4.3 に「スポンサーPR枠の挿入（FR-S9）」を新設: 協賛イベントを決定論的にマッチング挿入、`reference_type: "sponsored"` のゴールド系＋「🏢 PR（協賛）」明示表示、URI「詳細・応募はこちら」＋「興味あり」計測、`sponsored_engagement.json` トラッキングを規定（企業スポンサードPR の docs-first） | kmch4n |
| 2026-07-09 | §5.3 FR-P3 を拡張: 頑張ったこと件数に先月比・全期間通算・カテゴリ絵文字、当月の利用回数（生活・活動相談 / 記録・更新）、AI 寮母の月次総括コメントを追加。少回数フォールバックと AI 総括フォールバックのルール、非対称ルールの再定義（0 件でも利用回数があれば Flex 送信）、連携時一括同意の透明性文言を新設 | kmch4n |
| 2026-07-09 | Sender switch 機能を撤去し LINE 公式アカウント名・アイコン一本化に統一: §3.5「送信者アイコン・名前の切替」節を削除、§3.4-b テーブルの Sender 列と §4.2 の sender 言及・§4.6 / §5.2 / §5.3 の Sender 未指定運用注記を削除、旧 §3.6 Loading indicator を §3.5 へ繰り上げ（Issue #34 の docs-first） | kmch4n |
| 2026-07-09 | §4.8「FR-S10 クーポン配布（デモ）」を新設: 全経験投稿 3 件ごとに架空クーポン 3 種を専用カルーセルで push 配布、節目ごとローテーション、`store_url` URI ボタン、`coupon_distributions.json` トラッキングと `last_awarded_milestone` 重複防止を規定。§8 テンプレート方針に `coupon_carousel.py` を追記（クーポン配布の docs-first） | kmch4n |
| 2026-07-10 | §4.9「FR-S11 プレゼントくじ引き（デモ）」を新設: 投稿ごとに 1 回引く等級制くじ（1〜3 等＋はずれ）、`prizes.draw` の乱数/`force_rank` 抽選、当落演出 Flex（等級表示・単一バブル・`size:mega` 不使用）、手動トリガー `--rank`、`prize_draws.json` の PII 非収集トラッキング、景表法非該当の判断根拠を規定。応募口数の概念は持たない。§8 テンプレート方針に `prize_result.py` を追記（プレゼントくじ引きの docs-first） | kmch4n |
| 2026-07-10 | §4.9 実装仕上げ: 2 等を「地元名店 ペアお食事券」（地域つながり系）に、当落 Flex に情報カード（当選番号=抽選 seed / 有効期限ダミー / 利用条件）を追加、抽選確率をはずれ 19% / 3 等 50% / 2 等 30% / 1 等 1% に調整、投稿完了時の自動抽選結線を明記 | kmch4n |
| 2026-07-10 | §4.5 に経験投稿の妥当性判定（`valid`）を新設: finalize 統合呼び出しに相乗りさせ、無意味/虚偽/中身の伴わない抽選目的の投稿を保存しない（確認カードへ進めず固定警告文で終了、迷う場合は通す誤検知回避方針）。§4.9 に「弾かれた投稿でも抽選は引く」デモ演出上の許容と抑止手段を追記（`docs/06_ai_spec.md §4.5` と同期） | kmch4n |
