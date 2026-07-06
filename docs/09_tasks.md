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

**目的**: `data/seed/` 配下の架空データを 30 + 15 + 10 + 20 件投入

**成果物**:
- `data/seed/areas.json`（30 件）
- `data/seed/stores.json`（15 件）
- `data/seed/events.json`（10 件）
- `data/seed/senior_posts.json`（20 件）
- `data/seed/demo_profiles.json`（3 件）

**完了基準**: `05_data_model.md` の JSON スキーマに沿った内容、京都・同志社周辺の内容として妥当

**推定**: 2 時間（一気に書く）

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

**目的**: 見た目の質を上げる

**手順**:
- ウェルカム、活動カード、月次レポートの余白・色を調整
- 絵文字の統一
- iOS / Android 両方で表示崩れがないか確認

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

### T4.2 リッチメニュー実装（P1）

**目的**: 主要機能への導線を固定表示する

**手順**:
- リッチメニュー画像作成（Canva か Figma で 2500x1686）
- LINE Messaging API でメニュー登録
- 学生用・保護者用の 2 パターンを user 属性で切り替え

**推定**: 2 時間（時間ないなら省略）

### T4.3 ヘルプ・エラーメッセージ整備

**目的**: FR-C1, エラー系の充実

**手順**:
- 役割別ヘルプの文言確定
- 全エラーメッセージの語尾統一
- 想定外入力への挙動確認

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

### T4.9 Post-hoc 正規表現ハルシネーション検出

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
