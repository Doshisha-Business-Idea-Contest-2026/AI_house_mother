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

### 3.5 送信者アイコン・名前の切替 (Sender switch)

**目的**: 応答のトーン（寮母口調 vs システムメッセージ vs 通知）を送信者名とアイコンで区別し、ユーザーに「今どのモードで話しているか」を視覚的に伝える。

**LINE 機能**: line-bot-sdk v3 の `linebot.v3.messaging.Sender(name, icon_url)` を Message オブジェクトの `sender` フィールドに設定することで、メッセージ単位で送信者名とアイコンを切替可能。iconUrl は公開 HTTPS URL 必須。

**プリセット（3 モード）**:

| モード名 | name | iconUrl | 主な利用箇所 |
| --- | --- | --- | --- |
| `friendly`（寮母モード、デフォルト） | `AI寮母` | `static/icons/friendly.png` | 生活相談・やりたいこと相談・活動詳細・緊急定型・Gemini 応答全般 |
| `system`（システムモード） | `AI寮母 System` | `static/icons/system.png` | プロフィール入力促し・キャンセル確認・エラー・placeholder |
| `notify`（通知モード） | `AI寮母 お知らせ` | `static/icons/notify.png` | 招待コード発行完了・保護者連携完了通知（Day 3 で使用） |

**iconUrl の組み立て**:

`https://{PUBLIC_BASE_URL}/static/icons/{friendly|system|notify}.png` の形式で、`PUBLIC_BASE_URL` は `.env` の `PUBLIC_BASE_URL=https://linebot.kmchan.jp/ai_house_mother` から読む（`src/config.py` に追加予定）。

**呼び出し場所ごとの sender 分類（Day 4 実装時の指針）**:

| 呼び出し場所 | sender |
| --- | --- |
| `handlers/student.py::handle_life_consultation` の Gemini 応答 push | `friendly` |
| `handlers/student.py` の緊急定型 reply（life/medical/crime） | `friendly` |
| `handlers/student.py::handle_want_to_do` の push_flex カルーセル | `friendly` |
| `handlers/student.py::handle_activity_detail` の push_text | `friendly` |
| `handlers/student.py::handle_activity_participated` の reply | `friendly` |
| `handlers/message.py::handle_text` のキャンセル / placeholder / エラー | `system` |
| `handlers/postback.py::_handle_menu` の placeholder | `system` |
| `handlers/student.py` プロフィール入力ステップの reply | `system` |
| Day 3 の招待コード発行完了 push（学生側） | `notify` |
| Day 3 の保護者連携完了 push（学生側への通知） | `notify` |
| `follow.py::handle_follow` のウェルカムメッセージ | `friendly` |

**実装方針（Day 4 の T4.1b）**:

- `src/services/line_reply.py` の `reply_text` / `reply_flex` / `push_text` / `push_flex` に `sender: SenderPreset | None = None` 引数を追加
- `SenderPreset = Literal["friendly", "system", "notify"]`
- 内部で `Sender(name=..., icon_url=...)` を組み立てて Message オブジェクトの `sender` フィールドに設定
- 未指定時（`None`）は `friendly`（寮母モード）にフォールバック → 既存呼び出しは無変更
- `src/main.py` に FastAPI の `StaticFiles(directory="static")` を `/ai_house_mother/static` にマウント
- Apache は既に `/ai_house_mother` を FastAPI にプロキシしているので追加設定不要

**アイコン画像 placeholder**:

MVP 期間は暫定の 512×512 PNG を `static/icons/` にコミット済み。デモ前にチームで正式版に差し替える。

**Day 4 T4.1b 完了時点の実装状況**:

T4.1b 実装により、上表の分類はコードに反映済み。`src/services/line_reply.py` の `reply_text` / `reply_flex` / `push_text` / `push_flex` はいずれも `sender: SenderPreset | None = None` を受け取り、未指定時は `friendly` プリセットにフォールバックする。呼び出し側の分類は次のとおり:

- **friendly**: `handlers/follow.py::handle_follow`（welcome）、`handlers/student.py` の `handle_want_to_do` / `handle_activity_detail` / `handle_activity_participated` / `start_life_consultation` / `handle_life_consultation`（緊急定型・「少し考えます」・Gemini 応答）、`handlers/parent.py::_reply_report_for`。
- **system**: `handlers/message.py` と `handlers/postback.py` のキャンセル・placeholder・エラー・welcome fallback、`handlers/student.py` のプロフィール登録・経験投稿の全ステップ・招待発行エラー、`handlers/parent.py::start_link_flow` / `_handle_link_failure` / `handle_monthly_report`（未連携誘導）/ `_reply_placeholder`。
- **notify**: `handlers/student.py::start_invitation_flow`（招待コード Flex）、`handlers/parent.py::handle_link_text`（学生への `_LINK_COMPLETED_STUDENT` push + 保護者への `_LINK_COMPLETED_PARENT` reply）、`handlers/parent.py::_push_report_for`、`services/monthly_report.py::push_previous_month_to_all` の月次 Push。

`PUBLIC_BASE_URL` は `.env` 経由で切替可能（デフォルト `https://linebot.kmchan.jp/ai_house_mother`）で、FastAPI の `StaticFiles` マウントが `/ai_house_mother/static/icons/*.png` を配信する。

**iconUrl キャッシュ注意**:

LINE 側は iconUrl でキャッシュするため、同一 URL のまま画像だけ差し替えるとキャッシュヒットで古い画像が表示され続ける可能性がある。差し替え時はファイル名にバージョン suffix（例: `friendly_v2.png`）を付け、`src/config.py` の URL を更新して確実にキャッシュを無効化する。

### 3.6 Loading indicator による中間応答の可視化

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
- Loading Indicator は §3.5 の Sender switch（`friendly` / `system` / `notify`）と **直交** する概念で、アイコン切替はしない。後続の `push_text` / `push_flex` の `sender` 引数は独立に効く。
- API 呼び出しが失敗（LINE 側障害・レート制限）しても Gemini 応答の push は必ず継続する（`raise_on_error=False` 既定）。中間表示が出ない実害は本応答が届くことで十分に緩和される。

**適用箇所**（Day 4 T4.11 で置き換え済み）:

| Handler | 削除する中間 reply | 追加する呼び出し |
| --- | --- | --- |
| `handlers/student.py::handle_life_consultation` | 「💭 少し考えます…」 | `show_loading(user_id)` |
| `handlers/student.py::handle_want_to_do` | 「🤔 あなたに合いそうな活動を考えています…」 | `show_loading(user_id)` |
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

### 4.2 FR-S2 / US-S02: 学生プロフィール登録

**トリガー**: 「✍️ プロフィールを登録する」、または `プロフィール` `プロフ` 発話

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

**前提チェック**: プロフィール未登録なら FR-S2 に誘導

**フロー**:

```
[bot] （プロフィール確認 + 地域データを Gemini に渡す）
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
        - 🔄 他の案も見る
        - メインメニュー
```

**Gemini 呼び出しへの入力**: `06_ai_spec.md` を参照

**「詳しく聞く」選択後**: 該当活動について追加情報を AI が回答

**「参加した」選択後**: 経験投稿フロー（FR-S6）に遷移、対象活動情報を pre-fill

**`reference_type: "generated"` の視覚ラベル**（NFR-Truth-1 対応）:

- Gemini が seed に完全一致するレコードなしで発想した提案は Flex Message の Header 上部に「🧭 AI 提案（要確認）」のサブラベルを付ける
- seed 由来（`event` / `volunteer` / `store` / `senior_post`）の提案とは背景色または見出しで区別
- ユーザーが「AI が組み立てた提案」なのか「先輩投稿由来」なのかを一目で判別できるようにする
- 実装場所: `src/templates/flex/activity_carousel.py`

### 4.4 FR-S5 / US-S04: 生活相談

**トリガー**: 「💬 生活相談」を選んだ後の任意のテキスト、またはメニューを通さず直接テキスト送信

**情報源**（T4.10 で `data/posts.json` が加わる）:

- `data/seed/areas.json` — 地域情報
- `data/seed/stores.json` — 店舗情報
- `data/seed/senior_posts.json` — 先輩投稿（架空データ）
- `data/posts.json` — **他の学生が実際に投稿した経験**（匿名化して渡す。`docs/06_ai_spec.md §4.2` 匿名化ポリシー参照）

**フロー**:

```
[user] 熱っぽいんですけど、近くの病院ってどこ？

[bot] （Gemini に地域データ + 先輩投稿 + 匿名化した学生投稿を渡す）
      考え中です…💭

      37 度台の発熱なら、まずは今出川の「同志社前クリニック」が便利です。
      先輩の投稿より: 「土曜午前も空いていて、待ち時間が短かった」
      症状が続く場合や高熱の場合は迷わず医療機関を受診してください。

      🆘 緊急の場合は #7119（京都府救急安心センター）へ。
```

**特殊トピック検出**:
- キーワード: `救急`, `119`, `動けない`, `倒れた`, `血が` 等
  → 応答の冒頭で「119 番通報を推奨」を強調

**Gemini 呼び出し**: `06_ai_spec.md` の生活相談用プロンプトを参照

**Zero-context 分岐**（NFR-Truth-2 対応、`docs/06_ai_spec.md §5.3` の実装フェーズで対応）:

`context_search.find_relevant_context(user_message)` の戻り値 `total_hits == 0` の場合、Gemini が seed に無い固有情報（電話番号・営業時間・特定店舗名）を捏造するリスクを避けるため、以下の分岐を行う。

1. Gemini プロンプトに「total_hits = 0」と件数を明示、「地名・電話番号・営業時間・特定の店舗名を絶対に断定しない」制約を強制
2. Gemini 応答テキストの先頭に `ZERO_CONTEXT_DISCLAIMER`（`docs/06_ai_spec.md §5.3.4`）を連結
3. `context_search.detect_medical_intent(user_message)` が真なら末尾に `MEDICAL_FOLLOWUP` を追加（NFR-Truth-3）
4. Quick Reply には「🏠 メインメニュー」と「🚫 相談を終える」を維持
5. `zero_context: true` を journald にログ（§3.3）

**Zero-context の応答例**（ゴミ出しの相談で seed カバー外の想定）:

```
[user] ゴミの分別が本当にわからなくて困っている

[bot] ごめんなさい、この話題については先輩の投稿や地域の情報がまだ届いていません🙏
      以下は一般的なご案内なので、正確な情報は公式窓口でご確認くださいね。

      京都市は地区ごとにゴミ出しの曜日と分別ルールが異なります。
      お住まいの区役所や京都市エコまちステーションに直接お問い合わせいただくのが確実です。
```

**Zero-context + 医療系キーワードの応答例**:

```
[user] 頭が痛くて眠れない

[bot] ごめんなさい、この話題については先輩の投稿や地域の情報がまだ届いていません🙏
      以下は一般的なご案内なので、正確な情報は公式窓口でご確認くださいね。

      無理をせず、症状が続くようでしたら医療機関を受診してくださいね。
      市販薬に頼る前に、まずは十分な休息と水分補給を試してみるのも良いかもしれません。

      体調のご相談は #7119（京都府救急安心センター）でも相談できますよ。
      京都市の医療機関検索サイトも参考になります。
```

### 4.5 FR-S6 / US-S05: 経験投稿

**トリガー**: 「✏️ 経験を投稿」、または FR-S4 の「参加した」ボタン、または `投稿` 発話

**対話ステート**（6 ステップ、Day 3 で確定）:

| ステート | Bot 発話 | ユーザー入力 |
| --- | --- | --- |
| post.category | どのカテゴリの投稿ですか？ | Quick Reply |
| post.title | 短いタイトルを教えてください（例: 下鴨神社の清掃活動に参加） | テキスト（最大 40 文字） |
| post.body | 内容を詳しく教えてください | テキスト（最大 500 文字） |
| post.area | 場所（地名・店名など、なければ「なし」/「無し」/`skip`/空文字） | テキスト（自由入力、seed 照合なし） |
| post.share_parent | 保護者に「頑張ったこと」として共有しますか？ | Quick Reply（👨‍👩‍👧 共有する / 🙅 共有しない） |
| post.confirm | 内容確認 → 投稿する / やり直す | Quick Reply（✅ 投稿する / 🔄 やり直す） |

**カテゴリ Quick Reply**（6 カテゴリ + キャンセル）:
- 🏛️ 地域イベント (`event`)
- 🧹 ボランティア (`volunteer`)
- 🍜 お店・カフェ (`store`)
- 🏥 病院・薬局 (`medical`)
- 📋 手続き・生活の知恵 (`tips`)
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

**Sender 未指定（Day 3 期間中）**:

発行完了 push は §3.5 の暫定運用に従い `sender` 未指定で送出。Day 4 T4.1b で `notify` に差し替え予定。

### 4.7 FR-S8: 頑張ったこと記録

FR-S6 の `share_with_parent: true` で投稿されたレコードのうち、当月分を月次サマリー生成の入力として使う。

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
- 学生の LINE user へ連携完了 push（sender 未指定、§3.5 の Day 3 暫定運用に従う）
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
[bot] （data/posts.json から連携先学生の当月投稿を取得、share_with_parent=true のみ）

      [Flex Message]
      ┌────────────────────────┐
      │ 📊 あなたのお子さんの今月 │
      │ 2026-07                  │
      │ ─────────────────────── │
      │ ✨ 頑張ったこと 3 件      │
      │                          │
      │ 🏛️ 下鴨神社の清掃活動    │
      │    参加してきました。   │
      │                          │
      │ 🧹 子ども食堂サポート    │
      │    ...                  │
      │                          │
      └────────────────────────┘
```

**Push フロー**（`scripts/push_monthly_reports.py` → `monthly_report.push_previous_month_to_all`）:

1. `parent_links.list_all_active_pairs()` で `(parent, student)` を列挙
2. 各ペアについて `posts.list_month_shared(student, year, month)` を取得（`share_with_parent=true` のみ）
3. 0 件なら **送信スキップ**（無音、`counters.empty++`）
4. 1 件以上なら Flex を組み立て `push_flex(parent, ...)` で送信、成功なら `counters.sent++`
5. LineBotApiError 等は per-parent 個別 catch → `counters.errors++`、次の宛先に継続
6. batch 結果を `data/monthly_report_state.json` に記録（同 `target_year_month` の記録があれば skip、`--force` で上書き可）

**該当データなしの場合の非対称ルール**（B5）:

- **Pull（当月 0 件）**: 「今月はまだ頑張ったことの記録がありません。少し様子を見てあげてくださいね😊」テキスト + main menu QR で返す。
- **Push（前月 0 件）**: 送信を丸ごとスキップし、保護者に対して一切のメッセージを送らない（無音）。理由: 月初に「頑張ったこと 0 件」の空 push を受け取ると、初回連携直後の保護者体験が悪化するため。

**「メッセージを送る」ボタン**（Day 4 以降に持ち越し）:

保護者から学生への励まし送信機能は Day 4+ の T4.1a/T4.1b と併せて設計する。Day 3 の Flex には該当ボタンを **出さない**（Flex 内の footer は最大 5 件の投稿リストで完結）。

**Sender 未指定（Day 3 期間中）**:

Push は §3.5 の暫定運用に従い `sender` 未指定で送出。Day 4 T4.1b で `notify` に差し替え予定。

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
| プロフィール | `プロフィール` / `プロフ` | session 全リセット → プロフィール登録開始（学生） |
| やりたいこと | `やりたい` / `おすすめ` | session 全リセット → やりたいこと相談（学生） |
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
- テンプレートは build 関数として実装（既存 `kcb_linebot/flex_templates.py` と同様のパターン）

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
| 2026-07-06 | §3.6 Loading indicator による中間応答の可視化を新設（Day 4 T4.11 の docs-first）: SDK/API 仕様・20 秒既定・Sender switch との直交性・適用 3 handler の対応表 | kmch4n |
