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

**iconUrl キャッシュ注意**:

LINE 側は iconUrl でキャッシュするため、同一 URL のまま画像だけ差し替えるとキャッシュヒットで古い画像が表示され続ける可能性がある。差し替え時はファイル名にバージョン suffix（例: `friendly_v2.png`）を付け、`src/config.py` の URL を更新して確実にキャッシュを無効化する。

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

**フロー**:

```
[user] 熱っぽいんですけど、近くの病院ってどこ？

[bot] （Gemini に地域データ + 先輩投稿を渡す）
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

**対話ステート**:

| ステート | Bot 発話 | ユーザー入力 |
| --- | --- | --- |
| post.category | どのカテゴリの投稿ですか？ | Quick Reply |
| post.title | 短いタイトルを教えてください（例: 下鴨神社の清掃活動に参加） | テキスト |
| post.body | 内容を詳しく教えてください | テキスト |
| post.area | 場所（地名・店名など、なければ「なし」） | テキスト |
| post.share_parent | 保護者に「頑張ったこと」として共有しますか？ | Quick Reply |
| post.confirm | 内容確認 → 投稿する / やり直す | Quick Reply |

**カテゴリ Quick Reply**:
- 🏛️ 地域イベント
- 🧹 ボランティア
- 🍜 お店・カフェ
- 🏥 病院・薬局
- 📋 手続き・生活の知恵
- ✨ その他

**永続化**:
- `data/posts.json` に追加
- `share_with_parent: bool` で共有フラグ管理

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
- 有効期限: 発行から 24 時間
- 1 回使うと無効化

**永続化**:
- `data/invitations.json` に保存
- フィールド: `code`, `student_user_id`, `created_at`, `expires_at`, `used_at`, `used_by_parent_id`

### 4.7 FR-S8: 頑張ったこと記録

FR-S6 の `share_with_parent: true` で投稿されたレコードのうち、当月分を月次サマリー生成の入力として使う。

## 5. 保護者機能

### 5.1 FR-P1 / US-P01: 保護者役割選択

FR-S1 のフローで「👨‍👩‍👧 保護者です」を選択したケース。以降は保護者向けメニューを表示。

### 5.2 FR-P2 / US-P02: 招待コード入力

**トリガー**: 「🔑 コードを入力する」、または `連携` 発話

**対話ステート**:

| ステート | Bot 発話 | ユーザー入力 |
| --- | --- | --- |
| link.code | お子さんから受け取った 6 桁のコードを入力してください | テキスト（コード） |
| link.verify | （検証） OK なら学生名を提示して確認 | Quick Reply（はい / 違う） |
| link.done | 連携完了メッセージ | - |

**検証結果**:
- 有効: `data/invitations.json` を更新（used_at, used_by_parent_id）、`data/parent_links.json` に紐付け保存、学生の LINE user へ通知
- 無効: 「そのコードは見つかりません、または期限切れです。」

**副作用**: 連携完了と同時に「今月のレポート」がメニューに追加される

### 5.3 FR-P3 / US-P03: 月次サマリー閲覧

**トリガー**: 「📊 今月のレポート」、または `レポート` `頑張ったこと` 発話

**フロー**:

```
[bot] （data/posts.json から連携先学生の当月投稿を取得、share_with_parent=true のみ）

      [Flex Message]
      ┌────────────────────────┐
      │ 📊 山田 春樹さんの今月    │
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
      │ [ボタン: メッセージを送る]│
      └────────────────────────┘
```

**該当データなしの場合**:

```
[bot] 今月はまだ頑張ったことの記録がありません。
      少し様子を見てあげてくださいね😊
```

**「メッセージを送る」**: シンプルに LINE トークルームを開くだけ（外部トークへの導線）
- MVP では非実装、代わりに「学生に励ましを送る」を保護者から学生 Bot 経由で送るテキスト定型文にする
- 時間なければこのボタン自体を省略

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
- `post.category` 〜 `post.confirm`
- `link.code` 〜 `link.done`

**キャンセルコマンド**: 対話中でも `キャンセル` `やめる` `戻る` で `idle` に戻れる

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
