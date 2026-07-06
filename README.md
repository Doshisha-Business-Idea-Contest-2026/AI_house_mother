# AI 寮母 〜つながりを生む AI チャット〜

学生マンションに眠る先輩の経験・地域情報・学生の興味関心を AI に蓄積し、初めての一人暮らしの
不安解消と、「学び・成長・つながり」のきっかけづくりを実現する **LINE Bot** です。

> 同志社大学経済学部・経済学会「ビジネスアイデア大会 2026」決勝プレゼン向け MVP。
> 提案チーム: 宮崎総研（MRI）。

---

## プロダクト概要

AI 寮母は、汎用 AI チャットとは異なり **「その地域・そのマンションに特化した暗黙知」** を扱います。

- **課題**: 初めての一人暮らしの生活不安に加え、「何かやりたいけど何をすればよいかわからない」
  学生が、地域や他者とつながるきっかけを持てていない。
- **解決**: 学生自身が情報提供者となって経験を投稿し、AI がそれを次の学生の相談回答に活用する
  （暗黙知 → 形式知の継承 = **SECI モデル**）。生活相談だけでなく、学生の興味に合わせた地域活動を
  AI 側から提案し、行動のきっかけを生み出す。
- **保護者**: 学生本人が同意した範囲だけを届ける「監視ではなく合意ベースの見守り」を提供。

背景・課題・ビジネスモデルの詳細は [docs/00_product_context.md](docs/00_product_context.md) を参照。

## 提供価値

- **学生**: 24/365 の生活相談、地域特化のローカル情報、興味に合う活動提案、つながりのきっかけ。
- **保護者**: 過干渉にならない適度な見守りと、子どもの頑張りの可視化による安心感。
- **JSB（学生マンション事業者）**: 物件の差別化、入居率・満足度向上、管理業務の効率化、
  他社が模倣しにくい知識資産の蓄積。
- **地域社会**: 学生の送客、地域イベント・課題解決への参加、コミュニティの活性化。

## MVP 機能

| 機能 | 概要 |
| --- | --- |
| 役割選択 | 友だち追加時に Quick Reply で学生 / 保護者を選択 |
| プロフィール登録 | 対話形式で大学・学部・興味・目標などを登録 |
| やりたいこと相談 | プロフィール × 地域データから AI が活動を提案（Flex Message カルーセル） |
| 生活相談 | 先輩投稿・地域情報を反映した回答（ハルシネーション抑制付き） |
| 経験投稿 | 対話形式でカテゴリ選択し投稿。匿名化して次の学生の回答に活用 |
| 保護者連携 | 6 桁の招待コード方式で学生と保護者を連携 |
| 月次サマリー | 学生本人が共有を選んだ「頑張ったこと」を保護者へ（Pull / 月次 Push） |
| ヘルプ | 使い方案内 |

MVP 対象外の機能（クーポン・ポイント、サブスク課金、学生同士のマッチング、緊急通知、
モデレーション等）は「今後の展望」として発表資料に残します。詳細は
[docs/02_mvp_scope.md](docs/02_mvp_scope.md) を参照。

## 技術スタック

| レイヤー | 採用技術 |
| --- | --- |
| 言語 | Python 3.12 |
| Web フレームワーク | FastAPI（uvicorn） |
| LINE SDK | line-bot-sdk v3 |
| LLM | Google Gemini（`gemini-flash-lite-latest`） |
| データ永続化 | JSON ファイル（`fcntl` ロック付き） |
| プロセス管理 | systemd |
| リバースプロキシ | Apache |
| ホスティング | 自宅 Ubuntu サーバー |

- ポート: `8084` / パス: `/ai_house_mother`
- Webhook: `POST /ai_house_mother/callback` / ヘルスチェック: `GET /ai_house_mother/health`

## ディレクトリ構成

```
AI_house_mother/
├── src/
│   ├── main.py               # FastAPI エントリポイント
│   ├── config.py             # 環境変数・LINE/Gemini クライアント初期化
│   ├── router.py             # Webhook / health エンドポイント、署名検証
│   ├── handlers/             # follow / student / parent / postback
│   ├── services/             # gemini, line_reply, session, storage, prompts,
│   │                         # invitations, monthly_report, profiles, posts,
│   │                         # users, parent_links, activity_store,
│   │                         # context_search, seed
│   ├── templates/
│   │   ├── flex/             # welcome, activity_carousel, monthly_report,
│   │   │                     # invitation_code, profile_view
│   │   └── quick_reply.py
│   └── utils/
├── data/
│   └── seed/                 # areas, stores, events, senior_posts, demo_profiles
├── scripts/                  # init_data, push_monthly_reports, reset_demo, run_local.sh
├── deploy/                   # systemd unit / timer, Apache 設定, デプロイ手順
├── docs/                     # MVP 仕様書（00〜09）
├── static/icons/             # Sender switch 用アイコン
├── tests/
├── .env.example
└── requirements.txt
```

## セットアップ / ローカル実行

```bash
# 1. 仮想環境と依存
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 環境変数（.env.example をコピーして値を設定）
cp .env.example .env

# 3. 初期データ生成（seed は手動投入、ユーザーレコードは空で開始）
python scripts/init_data.py

# 4. 起動（auto-reload）
scripts/run_local.sh
# もしくは
uvicorn src.main:app --reload --host 0.0.0.0 --port 8084
```

必須の環境変数:

- `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_CHANNEL_SECRET`（[LINE Developers Console](https://developers.line.biz/console/)）
- `GEMINI_API_KEY`（[Google AI Studio](https://aistudio.google.com/)）

LINE / Gemini の資格情報がなくても動作確認したい場合は、`.env` で `GEMINI_MOCK_MODE=true` に
設定すると seed ベースの静的フォールバックで応答します（オフライン開発・デモ時の Gemini 障害
リハーサル用）。

疎通確認:

```bash
curl http://localhost:8084/ai_house_mother/health
```

## デプロイ

本番（自宅 Ubuntu サーバー）へは **systemd** でアプリを常駐させ、**Apache** のリバースプロキシで
`https://linebot.kmchan.jp/ai_house_mother` に公開します。月次レポートの Push は systemd timer で
毎月 1 日に実行します。

手順の詳細は [deploy/README.md](deploy/README.md) と [docs/07_architecture.md](docs/07_architecture.md)
を参照。

## デモ

学生役・保護者役の 2 台のスマートフォンで、友だち追加 → プロフィール登録 → やりたいこと相談 →
招待コード連携 → 生活相談 → 経験投稿 → 月次レポートまでを一連で実演します。

当日の操作手順・想定質問・保険は [docs/08_demo_scenario.md](docs/08_demo_scenario.md) を参照。

## ドキュメント

| ファイル | 内容 |
| --- | --- |
| [docs/00_product_context.md](docs/00_product_context.md) | プロダクト背景・課題・価値・ビジネスモデル（完全版コンテキスト） |
| [docs/01_requirements.md](docs/01_requirements.md) | 要件定義 |
| [docs/02_mvp_scope.md](docs/02_mvp_scope.md) | MVP スコープ（含む / 除外 / 成功基準） |
| [docs/03_user_stories.md](docs/03_user_stories.md) | ユーザーストーリー |
| [docs/04_functional_spec.md](docs/04_functional_spec.md) | 機能仕様 |
| [docs/05_data_model.md](docs/05_data_model.md) | データモデル |
| [docs/06_ai_spec.md](docs/06_ai_spec.md) | AI 仕様（System Prompt、ハルシネーション対策） |
| [docs/07_architecture.md](docs/07_architecture.md) | アーキテクチャ・デプロイ |
| [docs/08_demo_scenario.md](docs/08_demo_scenario.md) | デモシナリオ |
| [docs/09_tasks.md](docs/09_tasks.md) | 開発タスク |

## 開発ルール

- **ブランチ運用**: `main` への直接コミットは禁止。`feature/` `fix/` `refactor/` `docs/` `chore/`
  でブランチを切り、PR 経由でマージする（1 人開発中はセルフレビュー可）。
- **コミットメッセージ**: `[gitmoji] English subject` 形式（例: `[✨] Add student profile flow`）。
- **ドキュメントファースト**: 機能追加・仕様変更は着手前に必ず `docs/` を先に更新する。
- **言語**: 対話は日本語、コード・コミット・Issue・PR は英語、`docs/`・README は日本語。

規約の全文は [.codex/AGENTS.md](.codex/AGENTS.md) と [.codex/rules/](.codex/rules/) を参照。
