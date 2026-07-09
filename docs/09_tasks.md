# 09. タスク分解

## 1. このドキュメントの目的

MVP の 3〜4 日分の実装タスクを、順序と完了基準込みで分解する。

- 各タスクの目的と成果物
- 依存関係
- 完了判定
- スコープ縮退時の落としどころ

## 2. マイルストーン

| Day | 目標 | 完了状態 |
| --- | --- | --- |
| Day 1 (2026-07-05) | 土台構築 | Webhook 受信 → エコー応答が返る |
| Day 2 (2026-07-06) | コア機能実装 | 学生役でやりたいこと相談・生活相談が動く |
| Day 3 (2026-07-07) | 家族ループ | 招待コード → 保護者連携 → 月次レポート |
| Day 4 (2026-07-08) | 磨き込み | Flex Message 整形、デモ通し、想定質問対応 |

（日付は今日 2026-07-05 を Day 1 とした場合の想定。実際の決勝日に合わせて調整）

## 3. Day 1: 土台構築

### T1.1 LINE 公式アカウント取得と Messaging API チャネル作成

**目的**: Webhook を受け取るための LINE 側設定を完了する

**手順**:
- LINE Developers Console で新規プロバイダー作成
- Messaging API チャネル作成
- Channel Access Token と Channel Secret を取得

**完了基準**: `.env.example` に対応する変数名が確定、`.env` に実値を投入

**担当**: 緑川
**推定**: 30 分

### T1.2 Gemini API キー取得

**目的**: Gemini 呼び出し用のキーを取得する

**手順**:
- Google AI Studio でプロジェクト作成
- API キー発行
- Flash-Lite が利用可能なリージョン確認

**完了基準**: `.env` に `GEMINI_API_KEY` 投入、`curl` で Gemini エンドポイント疎通確認

**推定**: 15 分

### T1.3 プロジェクト初期化

**目的**: FastAPI プロジェクトの骨格を作る

**手順**:
- `python3 -m venv .venv`
- `requirements.txt` 作成（`07_architecture.md` 7章参照）
- `.env.example` 作成
- `.gitignore` に `.venv`, `.env`, `data/logs/` 追加確認
- `src/` 配下の空ファイル群作成

**完了基準**: `pip install -r requirements.txt` が成功、`uvicorn src.main:app` が起動して `/health` に応答する

**推定**: 30 分

### T1.4 FastAPI アプリと Webhook 受信

**目的**: LINE 署名検証と Webhook 受信の最小実装

**成果物**: `src/main.py`, `src/router.py`, `src/config.py`

**完了基準**: LINE 側から Webhook を送ってエコー応答が返る

**推定**: 1 時間

### T1.5 Storage 層と Session 層の実装

**目的**: JSON ファイル I/O とインメモリセッション

**成果物**: `src/services/storage.py`, `src/services/session.py`

**完了基準**: `data/users.json` への読み書きが動作、単体テストは書かなくてもよい（手動確認）

**推定**: 1 時間

### T1.6 友だち追加時の役割選択実装

**目的**: FR-S1 / FR-P1 の実装

**成果物**: `src/handlers/follow.py`, `src/templates/flex/welcome.py`

**完了基準**: 友だち追加 → ウェルカム表示 → 「学生/保護者」を選ぶと `data/users.json` にレコードが保存される

**推定**: 1.5 時間

### T1.7 systemd 登録と Apache 設定

**目的**: デプロイパイプラインを完成させる

**手順**:
- `deploy/ai_house_mother.service` 作成
- `/etc/systemd/system/` にコピー
- Apache 設定に proxy パス追加
- Webhook URL を LINE Developers Console に登録

**完了基準**: `sudo systemctl status ai_house_mother.service` が active、`curl https://linebot.kmchan.jp/ai_house_mother/health` が 200 OK

**推定**: 1 時間

### T1.8 Day 1 締めのコミット・プッシュ

**完了基準**: `git log` に Day 1 の作業がコミットされている

## 4. Day 2: コア機能実装

### T2.1 Seed データ作成

**目的**: `data/seed/` 配下に seed データを投入する。地域・イベント・店舗は同志社今出川周辺の**実在情報**、先輩投稿・デモプロフィールは**架空**（詳細ポリシーは `.codex/rules/project_rules.md` の「データ運用」節参照）

**成果物**:
- `data/seed/areas.json`（30 件、実在: 公共施設・行政・大学施設。`last_verified_at` を全レコードに必須）
- `data/seed/stores.json`（15 件、実在: 民間実名店舗。`data_freshness_note` と `source_url` を全レコードに必須）
- `data/seed/events.json`（10 件、実在: 大学公式・行政主催。`last_verified_at` を全レコードに必須、`schedule` は「毎年◯月」等の再帰的表現優先）
- `data/seed/senior_posts.json`（20 件、架空: プライバシー保護のため）
- `data/seed/demo_profiles.json`（3〜5 件、架空: 実在人物の情報は使用しない）

**完了基準**: `05_data_model.md` の JSON スキーマに沿った内容、同志社今出川キャンパス周辺（京都市上京区・中京区・北区）に地理的に集中している

**推定**: 実在情報の verify を伴うため、初回は 4〜6 時間程度を想定

### T2.2 学生プロフィール登録実装

**目的**: FR-S2 の実装

**成果物**:
- `src/handlers/student.py` にプロフィール登録フロー
- セッションステート `profile.*`
- `data/profiles.json` への保存

**完了基準**: 学生役で対話形式にプロフィール登録できる、Bot が確認して保存を完了する

**推定**: 2 時間

### T2.3 Gemini クライアント実装

**目的**: `06_ai_spec.md` の呼び出しラッパー実装

**成果物**:
- `src/services/gemini.py`（`propose_activities`, `answer_life_question` 等）
- `src/services/prompts.py`（プロンプトテンプレート）

**完了基準**: ローカルで Gemini を呼んで JSON 応答が返ることを手動確認

**推定**: 2 時間

### T2.4 やりたいこと相談実装

**目的**: FR-S4 の実装（主軸機能）

**成果物**:
- `src/handlers/student.py` に `handle_want_to_do`
- `src/templates/flex/activity_carousel.py`

**完了基準**: 「やりたいこと相談」でカルーセルが表示、各カードに 2〜3 件の活動が並ぶ

**推定**: 3 時間

### T2.5 生活相談実装

**目的**: FR-S5 の実装

**成果物**:
- `src/handlers/student.py` に `handle_life_question`
- 関連情報の検索ロジック（キーワードマッチ）

**完了基準**: 「熱っぽい、病院どこ？」等の質問に、先輩投稿を反映した回答が返る

**推定**: 2 時間

**注記（2026-07-06 追記）**: Zero-context 分岐（NFR-Truth-2/3、`docs/06_ai_spec.md §5.3`）は T2.5 の初期実装には含まれず、T2.hallu で追加する。

### T2.hallu ハルシネーション対策実装（Zero-context 分岐）

**目的**: `docs/06_ai_spec.md §5.3` の Zero-context 分岐と医療キーワード誘導を実装、NFR-Truth-1/2/3 を満たす。

**成果物**:
- `src/services/context_search.py`:
  - `ContextSearchResult` TypedDict 定義
  - `find_relevant_context()` の戻り値を `ContextSearchResult` に変更（`total_hits`, `matched_categories` を含める）
  - `should_add_disclaimer(result)` 追加
  - `detect_medical_intent(user_message)` 新設
- `src/services/prompts.py`:
  - `ZERO_CONTEXT_DISCLAIMER`, `MEDICAL_FOLLOWUP` 定数追加
  - `build_life_consultation_prompt()` に `total_hits` / `has_context` を引数追加、prompt に件数と制約を埋め込む
- `src/handlers/student.py::handle_life_consultation`:
  - `should_add_disclaimer(result)` で分岐、disclaimer / medical followup を組み立て
- `src/services/gemini.py::answer_life_question`:
  - `has_context` を受けて prompt 構築、Zero-context 時は応答冒頭に disclaimer を連結
- `src/templates/flex/activity_carousel.py`:
  - `reference_type: "generated"` のバブルに「AI 提案（要確認）」サブラベル追加（NFR-Truth-1 の視覚化）

**完了基準**:
- 「ゴミの分別が本当にわからなくて困っている」→ disclaimer + 一般案内 + 京都市エコまちステーション誘導
- 「熱っぽくて近くの病院を探しています」→ 通常応答（stores/areas から病院がヒットする）
- 「ミラノで美味しいレストランは？」→ disclaimer + 一般案内（Zero-context）
- 「頭が痛くて眠れない」→ disclaimer + `MEDICAL_FOLLOWUP`（#7119 誘導）
- journald に `zero_context: true, disclaimer_shown: true, medical_followup_shown: true/false, reference_types: [...]` が構造化ログとして残る

**推定**: 30〜40 分

**Day 割当**: Day 2 の延長として、T2.5 直後に実施。

### T2.6 Day 2 締めのコミット・プッシュ

## 5. Day 3: 家族ループ

### T3.0 docs 先行更新 & state ファイル初期化

**目的**: docs-first 原則に従い、Day 3 の仕様（招待コード再発行、月次 Push 併用、経験投稿 6 ステップ、予約語ルーティング、暫定 sender 運用）を実装前に docs へ落とし込む。`monthly_report_state.json` の空スケルトンも用意する。

**成果物**:
- `docs/04_functional_spec.md` §3.3 / §3.5 / §4.5 / §4.6 / §5.2 / §5.3 / §7 更新
- `docs/05_data_model.md` §2 / §4.3 / §4.4 / §4.11（新設） / §7 更新
- `docs/08_demo_scenario.md` に Pull 主軸のデモ手順、`--month` オーバーライドによる Push 手動再送手順、キャンセル・予約語割り込み確認
- `docs/09_tasks.md` の本ファイル自身
- `scripts/init_data.py` に `monthly_report_state.json` 初期化を追加
- `data/monthly_report_state.json` は `.gitignore` 済みだが手動で `{"last_batch": null}` を投入

**完了基準**: docs を読んだだけで Day 3 の全実装が着手できる粒度、`init_data.py` を空 `data/` で走らせて 7 ファイルが生成される

**推定**: 1 時間

### T3.1 招待コード実装

**目的**: FR-S7 の実装

**成果物**:
- `src/services/invitations.py`（`generate_code` / `issue_code` / `find_active` / `consume` / `is_expired`）
- `src/handlers/student.py` に招待コード発行フロー（`start_invitation_flow`）
- `src/handlers/postback.py` の `menu:invite` / `invite:regenerate` 配線
- `src/handlers/message.py` の `INVITE_COMMANDS` 予約語
- `src/templates/flex/invitation_code.py`
- `src/templates/quick_reply.py` に `invitation_menu_quick_reply`

**完了基準**:
- 学生役で 6 桁コードが発行され、`data/invitations.json` に保存される
- 再発行で前コードが即無効化される（`used_at`, `used_by_parent_id="__revoked__"`）
- 発行完了応答に main menu QR + 「メニューから選択してください」の誘導文が含まれ、続く自由テキストで Gemini が誤起動しない

**推定**: 1.5 時間

### T3.2 保護者連携実装

**目的**: FR-P2 の実装

**成果物**:
- `src/services/parent_links.py`（`link` / `list_students_for_parent` / `list_parents_for_student` / `list_all_active_pairs`）
- `src/handlers/parent.py`（`start_link_flow` / `handle_link_text` / `handle_link_postback` / `is_in_link_flow`）
- `src/handlers/__init__.py` に `parent` import 追加
- `src/handlers/postback.py` の `menu:link_student` / `link:*` 配線
- `src/handlers/message.py` の `LINK_COMMANDS` 予約語 + `is_in_link_flow` セッションルート
- `src/services/line_reply.push_text` で学生側へ連携完了通知（sender 未指定、§3.5 暫定運用）

**完了基準**:
- 保護者役でコード入力 → 連携完了、学生側に push 通知が届く
- 同一 (parent, student) の重複紐付けは冪等（`active=true` のまま）
- エラー 4 種（`not_found` / `expired` / `used` / `self_link`）で分岐、5 回連続失敗で session 全リセット + welcome QR

**推定**: 2 時間

### T3.3 経験投稿実装

**目的**: FR-S6 の実装

**成果物**:
- `src/services/posts.py`（`add_post` / `_next_post_id` / `list_current_month_shared` / `list_month_shared`）
- `src/handlers/student.py` に投稿フロー 6 ステップ（`start_post_flow` / `handle_post_text` / `handle_post_postback` / `is_in_post_flow`）
- `src/handlers/postback.py` の `menu:post` / `post:*` 配線
- `src/handlers/message.py` の `POST_COMMANDS` 予約語 + `is_in_post_flow` セッションルート
- `src/templates/quick_reply.py` に `post_category_quick_reply` / `post_share_parent_quick_reply` / `post_confirm_quick_reply`

**完了基準**:
- 6 ステップ対話フローが完走し `data/posts.json` に追加される
- キャンセル発話で全リセット + main menu QR
- `area` は自由入力（`なし`/`無し`/`skip`/空文字は null 正規化）
- `share_with_parent` フラグが Quick Reply の選択通り保存される

**推定**: 2 時間

### T3.4 月次サマリー Pull 実装

**目的**: FR-P3 の Pull パス（保護者トリガー）実装

**成果物**:
- `src/services/monthly_report.py`（`build_current_month_report` / `_first_of_this_month` / `_first_of_prev_month` / `CATEGORY_EMOJI` 定数）
- `src/handlers/parent.py` に `handle_monthly_report`
- `src/handlers/postback.py` の `menu:monthly_report` 配線
- `src/handlers/message.py` の `MONTHLY_COMMANDS` 予約語
- `src/templates/flex/monthly_report.py`（単一 bubble、最大 5 件、「メッセージを送る」ボタンなし）

**完了基準**:
- 保護者役で「今月のレポート」を選ぶと当月 `share_with_parent=true` 投稿が Flex Message で表示される
- 未連携の保護者は誘導テキスト + parent QR に流れる
- 連携複数学生の場合は先頭を reply + 残りを push
- 0 件時はテキスト定型 + parent QR

**推定**: 2 時間

### T3.4-b 月次サマリー Push スケジューラ実装

**目的**: FR-P3 の Push パス（毎月自動）実装。Pull と同じ Flex ロジックを流用し、systemd timer で駆動する。

**成果物**:
- `src/services/monthly_report.py` の拡張（`build_previous_month_report` / `push_previous_month_to_all(now_jst, target_year_month, force)`）
- `scripts/push_monthly_reports.py`（`argparse` で `--month YYYY-MM` / `--now ISO` / `--force`、journald 構造化ログ）
- `data/monthly_report_state.json` の read/write ロジック（二重実行防止）
- `deploy/ai_house_mother_monthly.service`（Type=oneshot）
- `deploy/ai_house_mother_monthly.timer`（`OnCalendar=*-*-01 09:00:00 Asia/Tokyo`, `Persistent=true`）

**完了基準**:
- `python scripts/push_monthly_reports.py --now "2026-08-01T00:01:00+09:00"` で前月分の Flex が連携保護者に届く
- 前月 0 件の (parent, student) は送信スキップ（無音、`counters.empty++`）
- LINE ブロック等の per-parent エラーは catch し `counters.errors++` して継続
- 同一 `target_year_month` の記録が既にあれば skip（`--force` で上書き）
- `deploy/*.timer` を systemd に登録すると `systemctl list-timers` に表示される

**推定**: 2 時間

### T3.5 Day 3 締めのコミット・プッシュ

## 6. Day 4: 磨き込み

### T4.1a Flex Message デザイン調整

**目的**: 見た目の質を上げる。プレゼンでオンボーディングを見せる際のインパクト向上のため、welcome を Flex bubble 化する副目標も含める。

**手順**:
- **welcome の Flex 化**: `src/templates/flex/welcome.py::build_welcome_message()` の返り値を `tuple[str, dict, QuickReply]`（alt_text / flex_contents / quick_reply）に変更。呼び出し側 10+ 箇所（`handlers/follow.py`, `handlers/message.py`, `handlers/postback.py`, `handlers/parent.py`）を `reply_flex` に置換。role=None での `_reply_placeholder` は Flex bubble の前置きテキストとして prefix を差し込める形にする。
- **既存 3 bubble（activity_carousel / invitation_code / monthly_report）のスタイル統一**:
  - Body spacing を `"md"` に統一（`monthly_report.py:110` の `"sm"` を修正）
  - Body title size を `"md"` weight `"bold"` に統一
  - Separator color を `"#e0e0e0"` に統一（`monthly_report.py:80` の `"#f0f0f0"` を修正）
  - Header sub-title size を `"sm"` に統一（`activity_carousel.py:89` の `"xs"` を修正）
- **絵文字調整**:
  - `↺`（U+21BA、Android 一部フォントで細字化）→ `🔄` に置換（`invitation_code.py` と `quick_reply.py::invitation_menu_quick_reply`）
  - `monthly_report.py` の `✨` 見出しを `🌸` に差し替え（category=other との衝突回避）
  - `invitation_code.py:78` の `size: "4xl"` → `"3xl"`（狭幅端末での折返し回避）

**推定**: 2 時間

### T4.1b Sender switch 実装（送信者アイコン・名前の切替）

**目的**: `docs/04_functional_spec.md §3.5` の仕様に基づき、応答のトーンに応じて送信者名とアイコンを切替、機械的応答と人間的応答の区別を UX で明示する。

**依存アセット**:
- `static/icons/friendly.png` / `system.png` / `notify.png`（Day 2 で placeholder コミット済み。デモ前に正式版に差し替え）

**成果物**:
- `src/services/line_reply.py`:
  - `reply_text` / `reply_flex` / `push_text` / `push_flex` に `sender: SenderPreset | None = None` 引数を追加
  - `SenderPreset = Literal["friendly", "system", "notify"]` を定義
  - 内部で `linebot.v3.messaging.Sender(name=..., icon_url=...)` を組み立てて Message の `sender` フィールドに設定
  - 未指定時は `friendly`（デフォルト）
- `src/main.py` に `StaticFiles(directory="static")` を `/ai_house_mother/static` にマウント
- `src/config.py` に `PUBLIC_BASE_URL` を追加（`.env` から読む、デフォルトは `https://linebot.kmchan.jp/ai_house_mother`）
- `.env.example` に `PUBLIC_BASE_URL` を追記
- 呼び出し側の分類（`docs/04_functional_spec.md §3.5` の表参照）:
  - `handlers/student.py::handle_life_consultation` の Gemini 応答 push → `friendly`
  - `handlers/student.py` の緊急定型 → `friendly`
  - `handlers/student.py::handle_want_to_do` のカルーセル push → `friendly`
  - `handlers/student.py::handle_activity_detail` の push → `friendly`
  - `handlers/message.py::handle_text` のキャンセル・placeholder・エラー → `system`
  - `handlers/postback.py::_handle_menu` の placeholder → `system`
  - `handlers/student.py` プロフィール入力ステップ → `system`
  - `handlers/follow.py::handle_follow` のウェルカム → `friendly`
  - Day 3 の招待コード発行完了・保護者連携完了通知 → `notify`

**完了基準**:
- LINE 実機で「生活相談」と「キャンセル」の応答が異なる送信者名・アイコンで表示される
- `curl https://linebot.kmchan.jp/ai_house_mother/static/icons/friendly.png` で 200 が返る（他 2 種も同様）
- 既存の呼び出し箇所は無変更で動作する（`sender` 未指定は `friendly` にフォールバック）

**推定**: 2 時間

### T4.2 リッチメニュー実装（P1、決勝プレゼン後に持ち越し）

**目的**: 主要機能への導線を固定表示する

**手順**:
- リッチメニュー画像作成（Canva か Figma で 2500x1686）
- LINE Messaging API でメニュー登録
- 学生用・保護者用の 2 パターンを user 属性で切り替え

**推定**: 2 時間

**Day 4 の暫定運用**: 決勝プレゼン 2026-07-08 までは Quick Reply モックで導線を確保する。`main_menu_quick_reply(role)` が 6 項目（学生）/ 3 項目（保護者）を常に提示するため、機能到達性は担保されている。リッチメニュー本実装はプレゼン後の Day 5+ 課題に持ち越し。

### T4.3 ヘルプ・エラーメッセージ整備

**目的**: FR-C1 / エラー系の文言磨き込み。3 サブスコープに分割:

- **T4.3-a 残置文言除去**: `HELP_STUDENT` / `HELP_PARENT` の "(Day 3)" 表記、`PARENT_CONFIRM` の "Day 3 で実装予定"、プロフィール完了メッセージの「順次追加中」、`handle_activity_participated` の「Day 3 で追加予定」、docstring 内の "Day 2+ / Later days will add ..." を実装済み事実に更新。
- **T4.3-b 語尾統一**: 「アクション」「機能」→「操作」に統一、セッション切れメッセージを 1 種類に統一、リトライ文言（「お試しください」）、`_ERROR_MESSAGES` の末尾句点統一、メニュー文言（「下のボタン」→「下のメニュー」）。
- **T4.3-c 権限違い応答一貫性**: `_reply_wrong_role(event, actual_role, required_role)` ヘルパーを追加し、`postback.py::_handle_menu` の全 role 不一致分岐と `postback.py` の prefix 判定を統一。

**推定**: 1 時間

### T4.4 デモシナリオ通し実行

**目的**: `08_demo_scenario.md` の全 7 シーンを手元で実演できることを確認

**手順**:
- 学生役・保護者役のスマホでシナリオを最初から最後まで実行
- 各シーンで想定通りに動くか確認
- 動かない箇所を即修正

**完了基準**: 中断なく全シーンが完走する

**推定**: 1.5 時間

### T4.5 想定質問対応 & 発表資料整合

**目的**: `08_demo_scenario.md` 第 6 章の質問候補に対する回答を発表資料に反映

**推定**: 1 時間

### T4.6 データリセットスクリプト

**目的**: デモ前に user データを消して初期状態に戻すツール

**成果物**: `scripts/reset_demo.py`

**完了基準**: 実行後に `data/users.json`, `profiles.json`, `posts.json`, `invitations.json`, `parent_links.json` が空になる（seed は残る）

**推定**: 30 分

### T4.7 発表当日チェックリスト

`08_demo_scenario.md` 第 9 章のチェックリストを実行

### T4.8 Day 4 締めのコミット・プッシュ

### T4.11 Loading Indicator 実装（中間応答の UX 磨き込み）

**目的**: LINE Messaging API の Loading Indicator（`docs/04_functional_spec.md §3.6`）を活用し、Gemini 応答待ちの体感待機時間を短縮する。テキストの中間応答（「少し考えます…」等）を削除し、「Bot が入力中…」のアニメーションに置き換える。

**成果物**:

- `src/services/line_reply.py::show_loading(line_user_id, loading_seconds=20, raise_on_error=False)` を新設
  - `DEFAULT_LOADING_SECONDS = 20` を定数として持つ
  - 5 の倍数・5〜60 秒の範囲を `ValueError` でバリデーション
  - 内部で `MessagingApi.show_loading_animation(ShowLoadingAnimationRequest(...))` を呼ぶ
  - 既存の push ヘルパーと同じ fire-and-forget パターン（`raise_on_error` オプション付き）
- `src/handlers/student.py` の 3 handler で中間 `reply_text` を削除し `show_loading(user_id)` に置換:
  - `handle_life_consultation`（緊急定型の後、Gemini 呼び出しの直前）
  - `handle_want_to_do`（プロフィール未登録の error の後、Gemini 呼び出しの直前）
  - `handle_activity_detail`（activity_store.resolve error の後、Gemini 呼び出しの直前）

**完了基準**:

- LINE 実機で「やりたい」「生活相談」「活動詳細」を送信 → テキストの中間応答は表示されず、Loading Indicator が出たあと Gemini 応答が push で届く
- 20 秒より短い応答時は Gemini 応答 push が届いた瞬間に Loading Indicator が自動的に消える
- `.venv/bin/python -c "from src.services.line_reply import show_loading; show_loading('U...')"` で例外が出ない
- 引数バリデーション: `show_loading(..., loading_seconds=7)` で ValueError

**推定**: 30〜45 分

**Day 割当**: Day 4 に組み込む。T4.10 の後、T4.4（デモ通し）の前に実施することで、デモシナリオを Loading Indicator つきで通す。

### T4.10 学生投稿を生活相談 context に組み込む（SECI モデル継承）

**目的**: `docs/06_ai_spec.md §4.2` および `docs/05_data_model.md §8` の docs-first で確定した「学生の経験投稿を後の学生の生活相談 Gemini プロンプトに匿名化して継承する」ポリシーを実装する。SECI モデルの「形式知化 → 継承」サイクルをコードで体現。

**成果物**:

- `src/services/posts.py::list_all_for_context() -> list[dict]`（匿名化アクセサ、5-field allow-list を実装）
- `src/services/context_search.py`:
  - `ContextSearchResult` に `student_posts: list[dict]` を追加、`total_hits` を 4 コレクションの合計に更新
  - `find_relevant_context` で `posts.list_all_for_context()` を対象に rank
- `src/services/prompts.py`:
  - `build_life_consultation_prompt` に `student_posts` / `student_posts_hits` を渡すブロック追加
  - System prompt の情報源記述を更新（06_ai_spec §3.1 と同期）
  - 匿名引用ルール「同じマンションの先輩の投稿」を明記
- `src/services/gemini.py::answer_life_question`:
  - 呼び出しに `student_posts` を渡す
- `src/handlers/student.py::handle_life_consultation`:
  - journald に `student_posts_hits` を追記

**完了基準**:

- 学生 A が `tips` カテゴリで投稿 → 別セッションから学生 A（or 別学生）が関連キーワードで生活相談 → Gemini 応答に投稿内容が反映される
- Zero-context 判定が学生投稿を含めた `total_hits == 0` で決定される
- 匿名化ポリシー: `line_user_id` / `post_id` / `share_with_parent` / プロフィール情報が Gemini プロンプトの本文中に登場しない
- 既存の `share_with_parent` 月次サマリー用途は無変更（回帰なし）

**推定**: 1〜1.5 時間

**Day 割当**: Day 4 に組み込む。

### T4.9 Post-hoc 正規表現ハルシネーション検出（Day 5+ に持ち越し）

**Day 4 での判断**: Zero-context disclaimer（T2.hallu、`docs/06_ai_spec.md §5.3`）とプロンプト側の「情報源にない固有情報を断定しない」制約、T4.10 SECI 継承（学生投稿を反映）で MVP 期間の Truth 対策は十分。デモ後の Day 5+ に持ち越す。以下は将来仕様として残す。

**目的**: `docs/06_ai_spec.md §5.2` の post-hoc チェックを実装、Gemini 応答に含まれる捏造固有情報を検出・除去する。

**成果物**:
- `src/services/hallucination_filter.py` 新設
- 正規表現で以下を検出:
  - 電話番号パターン（`\d{2,4}-\d{2,4}-\d{4}`）
  - 「毎週◯曜日」「毎月◯日」等の断定的日程表現
  - 「〜時から〜時まで」等の断定的営業時間
- `answer_life_question` の応答に対してフィルタを適用:
  - seed に存在しない値なら該当箇所を削除、または「（要確認）」注記に置換
  - 電話番号は `#7119` などの一般窓口に自動置換

**完了基準**:
- テストケース「電話は 075-123-4567 です」→ 「電話は公式サイトでご確認ください」に置換
- テストケース「毎週水曜が燃えるゴミです」→ 「詳しくは京都市エコまちステーションにご確認ください」に置換
- seed 由来の #7119 などは残る

**優先度**: P2（Day 4 の余裕枠に配置、必須ではない）

**推定**: 45 分

### T4.12 企業スポンサードPR 実装（FR-S9、第3の収益源）

**目的**: `docs/04_functional_spec.md §4.3`・`docs/05_data_model.md §4.12/§4.13` で確定した「やりたいこと相談に協賛イベントを PR 枠として決定論的に挿入する」機能を実装する。保護者サブスク・店舗掲載料に次ぐ第3の収益源（`docs/00_product_context.md §10.7`）を実演で示す。

**成果物**:

- **seed**: `data/seed/sponsored.json`（架空の協賛企業イベント 2〜3 件。就活・選考直結ハッカソン・ビジネスアイデア大会等。`§4.12` スキーマ準拠、鮮度注記必須）。デモ用に学年が合致するプロフィールを 1 つ用意
- **マッチング挿入**: `src/services/sponsored.py` を新設。`active: true` の案件を学生プロフィール（`faculty` / `grade` / `interests`）で突き合わせ、合致スコア最上位 1 件を返す（合致なしは None）
- **Flex 表示**: `src/templates/flex/activity_carousel.py` に `reference_type: "sponsored"` を追加（ゴールド系ヘッダー色 ＋「🏢 PR（協賛）」バッジ ＋ 開示文「この案内は協賛企業からの提供です」＋ 鮮度注記）。ボタンは URI「詳細・応募はこちら」（`apply_url`）＋ postback「興味あり」（`sponsored:interest:{sponsor_id}`）
- **カルーセル組み立て**: `src/handlers/student.py` のやりたいこと相談（ブランチ A / B 両方）で、Gemini 応答後にマッチPR を先頭へ別枠挿入（通常提案は最大 3 件維持、合計最大 4 バブル）
- **トラッキング**: `src/handlers/postback.py` で `sponsored:interest:*` を処理し、`data/sponsored_engagement.json` に追記（user_id はハッシュ化、`§4.13` スキーマ）。`scripts/init_data.py` に空スケルトン生成を追加

**完了基準**:

- [ ] プロフィール合致学生でやりたいこと相談 → カルーセル先頭に「🏢 PR（協賛）」枠が表示される
- [ ] 合致案件が無い学生では PR 枠が表示されない
- [ ] PR カードの掲載テキストが seed の値と一致する（AI による言い換えが無い）
- [ ] 「詳細・応募はこちら」で `apply_url` が開く／「興味あり」で `sponsored_engagement.json` に記録される
- [ ] `sponsored_engagement.json` に生の LINE user_id が保存されていない（ハッシュのみ）
- [ ] iOS / Android 両方で PR 枠が崩れず表示される

**優先度**: P1（`docs/02_mvp_scope.md §3.2`。逼迫時は落とせるが、収益モデル実演のため実装を目指す）

**推定**: 2〜3 時間

**Day 割当**: Day 4。T4.4（デモ通し）の前に実施し、シーン 2 の PR 実演を含めて通す。

### T4.13 Flex Message デザイン刷新（カード構造化・共通スタイル基盤）

**目的**: 全 Flex Message（5 種）のビジュアルを、現状の「色付きヘッダー＋セパレータ区切りの
フラットな本文」から、`../kcb_linebot/flex_templates.py` 準拠の「背景トーンで塗り分けた
カードインカード構造＋左アクセントバー＋サイズ階層」へ刷新する。決勝プレゼンの実機デモで
Flex の見栄えが訴求力に直結するため、情報のグルーピングを視覚的に強化する。

T4.1a（spacing/色/絵文字の軽微な統一、概ね完了済み）とは別の、一段深いビジュアル刷新である。

**成果物**:

- **共通スタイルモジュール新設**: `src/templates/flex/style.py`（仮）。カラートークン
  （同志社ネイビー `#00579C` 基調、既存 `activity_carousel._CATEGORY_COLORS` と整合）・
  角丸・パディング・背景トーン・左アクセントバー生成などのヘルパーを提供
- **5 builder の刷新**: `activity_carousel` / `welcome` / `monthly_report` /
  `invitation_code` / `profile_view` が共通モジュールを利用し、カードインカード構造へ移行
- 既存の機能・postback data・alt text・情報鮮度注記（NFR-Truth-4）・PR 開示文（FR-S9）は
  すべて維持（デザイン変更のみで挙動は不変）

**完了基準**:

- [ ] `src/templates/flex/style.py` が新設され、5 builder が共通トークン／ヘルパーを利用している
- [ ] 5 種の Flex がカードインカード構造（角丸背景ボックス・アクセントバー・サイズ階層）で表示される
- [ ] postback data・alt text・鮮度注記・PR 開示文が刷新前と機能的に同一である
- [ ] iOS / Android 両方（または LINE Flex Simulator）で表示崩れがないことを確認
- [ ] 既存テスト（`tests/test_activity_carousel.py` 等）が通る／構造変更に追随して更新済み

**参考**: `../kcb_linebot/flex_templates.py` の `create_stop_info_box`（左アクセントバー）、
`create_single_route_bubble`（`styles` によるヘッダー/ボディ/フッター背景制御）。

**実施方針（確定・改定）**:

初回実装（グレー角丸カード＋見出しバー）は実機で変化が弱く「垢抜けない」と評価されたため、
**白基調・エアリー路線**へ改定した。

- **ヘッダーは白地＋navy アクセント**: navy ベタ塗りブロックを廃し、白ヘッダーにタイトルを navy
  太字、左に navy 細アクセントバー、下に navy の hairline を敷く。ブランド色はアクセントで残す。
- **本文は白基調・余白＋hairline**: グレーの塗りカードを廃止し、余白（spacing）と細い区切り線、
  サイズ階層（ラベル小／値大）で情報を分ける。透明感・垢抜けを優先。
- **配色は同志社ネイビー基調**: `_CATEGORY_COLORS` は彩度を落とした落ち着いたトーンとし、提案の
  カテゴリ色・`sponsored` のゴールド `#C9A227`（FR-S9 の識別要件）は**ヘッダー左のアクセントバー**で
  表現する（白ヘッダーでも区別が付く）。

**優先度**: P2（デモのインパクトに効くが MVP を止めない。逼迫時は T4.1a の水準で妥協）

**推定**: 3〜4 時間

**Day 割当**: Day 4 以降。T4.4（デモ通し）前に実施できれば実演効果が高い。

### T4.14 経験投稿の構造化（body 丸投げ → 5 問フロー）

**目的**: 経験投稿（FR-S6）の中核 `post.body`（丸投げの自由記述、最大 500 字）を、粒度が揃う
5 問（期間 / 概要 / 学び / 残念・注意 / 次の人へのアドバイス）に構造化する。蓄積される投稿の質を
底上げし、保護者月次レポートの読み応えと SECI モデル（他学生の生活相談 context）の継承精度を
同時に高める。仕様は `docs/04_functional_spec.md §4.5`・`docs/05_data_model.md §4.3`・
`docs/06_ai_spec.md §4.2` に定義済み。

**成果物**:

- `src/services/posts.py`:
  - フィールド上限定数を追加（`MAX_PERIOD_LEN=100` / `MAX_SUMMARY_LEN=300` / `MAX_LEARNED_LEN=200`
    / `MAX_REGRET_LEN=200` / `MAX_ADVICE_LEN=200`）、`MAX_BODY_LEN` を 500→1200 に引き上げ
  - スキップ正規化ヘルパー `_normalize_skippable`（`skip`/`なし`/`無し`/`スキップ`/空 → `None`）を新設し、
    `_normalize_area` をこれに委譲
  - `compose_body(period, summary, learned, regret, advice)`（非空のみ `【…】` 連結）を新設
  - `add_post` シグネチャを 5 フィールドに変更し、内部で `compose_body` を呼んで `body` も格納
- `src/handlers/student.py`:
  - `_POST_STEP_ORDER` を新 10 ステップに更新（`is_in_post_flow` の単一 source of truth）
  - `handle_post_text` に `post.period`/`summary`/`learned`/`regret`/`advice` 分岐を追加
    （必須ステップは空入力で再入力、スキップ可ステップはスキップトークンで `None` 記録）
  - `_send_post_confirmation` の確認カードを 5 フィールド表示に、`_finalize_post` を新シグネチャに更新
- `src/templates/quick_reply.py`: `post_skip_quick_reply()`（「⏭️ スキップ」＋「🚫 キャンセル」）を新設
- `tests/test_posts.py`（新規、pytest 非依存の既存流儀）: `compose_body` / `_normalize_skippable` /
  `add_post` のレコード形状（5 フィールド + 合成 body + 上限 truncate）を検証

**完了基準**:

- [ ] 経験投稿が category → title → 5 問 → area → 共有 → 確認の 10 ステップで動く
- [ ] `post.period`/`regret`/`advice` はスキップ可、`summary`/`learned` は必須（空入力で再入力を促す）
- [ ] `data/posts.json` に 5 フィールド + 合成 `body` が保存される
- [ ] 保護者月次レポート・生活相談 context が合成 `body` 経由で無改修のまま動く（後方互換）
- [ ] 旧スキーマの既存レコード（`body` のみ）も月次・context で従来どおり読める
- [ ] `black --check` / `ruff check` / `mypy` / `pytest` が通る

**優先度**: P2（投稿の質向上。MVP を止めないが SECI モデルの説得力に効く）

**推定**: 3〜4 時間

**Day 割当**: Day 4 以降。

### T4.15 経験投稿への LLM アシスト（title 自動生成 + period 時間正規化）

**目的**: T4.14 で構造化した経験投稿を LLM で仕上げる。(1) title のユーザー手入力を廃止し、内容から
自動生成、(2) 相対的な period 表現（「去年の10月」）を投稿時点（`created_at`）基準で絶対表現へ正規化。
入力品質のばらつきと相対時間の意味喪失を解消する。仕様は `docs/06_ai_spec.md §4.5`・
`docs/04 §4.5`・`docs/05 §4.3` に定義済み。

**方針**: 固定フローは維持し、全項目収集後・confirm 直前に **1 回の Gemini 統合呼び出し**で title 生成 +
period 正規化を実施。LLM 失敗時は必ずフォールバック（title←summary 冒頭、period←raw）しフローを
止めない。動的設問は今回スコープ外。

**成果物**:

- `src/services/prompts.py`: `build_post_finalize_prompt(...)` を新設
- `src/services/gemini.py`: `finalize_post(...) -> {"title", "period"}` を新設（JSON モード・
  `GEMINI_MOCK_MODE`/失敗時フォールバック）
- `src/services/posts.py`: `add_post` に `period_raw` を追加、`period` は正規化値を格納
- `src/handlers/student.py`: `post.title` 手入力を削除、`post.title_edit` を追加、share 選択直後に
  `show_loading` → `finalize_post` → 確認カードを push、確認カードに `✏️ タイトルを変更` を追加
- `src/templates/quick_reply.py`: `post_confirm_quick_reply()` に「タイトルを変更」を追加
- `tests/test_posts.py` 拡張・`tests/test_gemini_finalize.py`（mock フォールバック検証）新設

**完了基準**:

- [ ] title 手入力ステップが無く、確認カードに AI 生成 title が出る（`✏️ タイトルを変更`で編集可）
- [ ] 相対 period が `created_at` 基準で正規化され、`period_raw`（生）と `period`（正規化）が両方保存される
- [ ] LLM 失敗・`GEMINI_MOCK_MODE` 時は title←summary 冒頭・period←raw にフォールバックしフローが完走する
- [ ] `period_raw` を持たない旧レコードが月次・context で従来どおり読める（後方互換）
- [ ] `black --check` / `ruff check` / `mypy` / `pytest` が通る

**優先度**: P2（LLM 活用のショーケース。デモ映えするが MVP を止めない）

**推定**: 3〜4 時間

**Day 割当**: Day 4 以降。

## 7. タスク依存グラフ

```
T1.1 ─┐
T1.2 ─┼─▶ T1.3 ─▶ T1.4 ─▶ T1.5 ─▶ T1.6 ─▶ T1.7 ─▶ T1.8
      │                             │
      │                             ▼
      └─▶ T2.3                    T2.1 (並行)

T2.1 ┐
T1.6 ┼──▶ T2.2 ─▶ (T2.4 と T2.5 は並行可) ─▶ T2.6
T2.3 ┘

T2.6 ─▶ T3.0 ─▶ T3.1 ─▶ T3.2 ┐
                              ├─▶ T3.4 ─▶ T3.4-b ─▶ T3.5
              T2.5 ─▶ T3.3 ───┘

T3.5 ─▶ T4.1a ─▶ T4.1b ─▶ T4.2 (opt) ─▶ T4.3 ─▶ T4.4 ─▶ T4.5 ─▶ T4.6 ─▶ T4.7 ─▶ T4.8
```

## 8. スコープ縮退

期間が逼迫した場合、以下の順で機能を削る（`02_mvp_scope.md` 6.5 節と対応）。

1. **T4.2 リッチメニュー** — Quick Reply のみで代替
2. **T2.5 生活相談の高度化** — キーワードマッチをスキップして Gemini に全部渡す
3. **T3.3 経験投稿** — デモでは事前投入データのみで動かす、投稿 UI モックのみ
4. **T3.4 月次サマリー** — 静的テンプレート化（"春樹さんの今月：〜" を固定文言）
5. **T4.1a Flex Message デザイン調整** — テキスト応答に置き換え
6. **T4.1b Sender switch 実装** — 全応答を単一送信者に戻す（アイコン切替なし）
7. **T4.13 Flex デザイン刷新** — T4.1a の水準（フラット構造）のまま据え置き
8. **T4.14 経験投稿の構造化** — 単一 `body` 自由記述に戻す（5 問化を見送る）
9. **T4.15 経験投稿の LLM アシスト** — 手入力 title・raw period に戻す（LLM 呼び出しを外す）

## 9. 完了状況トラッキング

以下のフォーマットで各タスクの完了を記録する。`docs/` に別ファイル `progress.md` を作るか、GitHub Issues で管理するかは判断次第。

```
Day 1
- [x] T1.1 LINE 公式アカウント取得
- [ ] T1.2 Gemini API キー取得
- [ ] T1.3 プロジェクト初期化
...
```

## 10. 変更履歴

| 日付 | 変更内容 | 記入者 |
| --- | --- | --- |
| 2026-07-05 | 初版作成 | kmch4n |
| 2026-07-06 | T2.5 に Zero-context 未実装の注記、T2.hallu と T4.9 を新設（ハルシネーション対策のため） | kmch4n |
| 2026-07-06 | T4.1 を T4.1a（Flex デザイン調整）と T4.1b（Sender switch 実装）に分割、タスク依存グラフと縮退順序を同期 | kmch4n |
| 2026-07-06 | Day 3 タスク詳細化: T3.0 docs 先行更新 & init_data 拡張を新設、T3.1〜T3.4 の成果物・完了基準を家族ループ仕様（招待コード再発行 invalidate / 5 回失敗リセット / 6 ステップ経験投稿 / Pull 主軸月次レポート）に合わせて拡張、T3.4-b を月次 Push スケジューラとして分離、依存グラフを同期 | kmch4n |
| 2026-07-06 | T4.10 を新設: 学生投稿を生活相談 Gemini context に匿名化継承する SECI モデル体現タスク（成果物 posts.list_all_for_context / context_search 拡張 / prompts 更新 / gemini 呼び出し） | kmch4n |
| 2026-07-06 | T4.11 を新設: LINE Loading Indicator API による中間応答 UX 磨き込み。line_reply.show_loading を追加し、student.py の 3 handler で「考えています…」等のテキスト reply を Loading Indicator に置き換える | kmch4n |
| 2026-07-06 | Day 4 残タスクの範囲確定: T4.2 リッチメニュー本実装を Day 5+ に持ち越し（Quick Reply モックで暫定運用）、T4.9 Post-hoc 正規表現ハルシネーション検出も Day 5+ に持ち越し、T4.1a に welcome Flex 化を追加、T4.3 を 3 サブスコープ (a 残置除去 / b 語尾統一 / c 権限違い応答一貫性) に分割 | kmch4n |
| 2026-07-08 | T4.12 企業スポンサードPR 実装（FR-S9、第3の収益源）を新設: sponsored.json seed・マッチング挿入・Flex PR 表示・興味ありトラッキングの成果物と完了基準を定義 | kmch4n |
| 2026-07-09 | T4.13 を新設: 全 Flex（5 種）を kcb_linebot 準拠のカードインカード構造へ刷新し、共通スタイルモジュール src/templates/flex/style.py を新設するデザイン刷新タスク（T4.1a より一段深いビジュアル改善） | kmch4n |
| 2026-07-09 | T4.14 を新設: 経験投稿の丸投げ body を 5 問（期間/概要/学び/残念/アドバイス）に構造化。個別保存＋合成 body で下流無改修・後方互換を維持し、蓄積情報の質と SECI context 精度を底上げ（docs/04 §4.5・docs/05 §4.3・docs/06 §4.2 を更新） | kmch4n |
| 2026-07-09 | T4.15 を新設: 経験投稿に LLM アシスト（title 自動生成 + period 時間正規化）を追加。confirm 直前の 1 回統合呼び出し、raw+正規化 period の両保存、失敗時フォールバックでフロー継続（docs/04 §4.5・docs/05 §4.3・docs/06 §4.5 を更新） | kmch4n |
| 2026-07-09 | T4.13 実施方針を確定: カード密度=バランス（セクション見出しに左アクセントバー＋本文を角丸カードで軽くグルーピング）、配色=同志社ネイビー基調に調整（sponsored ゴールドは維持）。docs/07 §4.6 に style.py 方針を追記 | kmch4n |
| 2026-07-09 | T4.13 実施方針を白基調エアリーへ改定: 初回のグレー角丸カードは変化が弱く、白ヘッダー＋navy アクセントバー／余白＋hairline へ作り替え。グレー塗りカード廃止、カテゴリ色・sponsored ゴールドはヘッダー左アクセントバーで表現（docs/07 §4.6・docs/04 §8 を更新） | kmch4n |
