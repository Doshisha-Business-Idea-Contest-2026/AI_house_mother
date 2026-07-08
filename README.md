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

## 実装ハイライト

単なる LINE + LLM 連携ではなく、コンテンツの信頼性・継承性・UX 上の役割設計まで踏み込んで
実装しています。

- **ハルシネーション抑制**: seed の実在情報（地域 30 / イベント 10 / 店舗 15）と `[情報鮮度: 2026-07]`
  注記の自動付与、Truth 制約群（NFR-Truth-1〜4）で医療・法律・緊急対応の断定を回避。
  詳細は [docs/06_ai_spec.md](docs/06_ai_spec.md)。
- **SECI モデル実装**: 学生の投稿を `context_search` で次の相談時に取り込み、暗黙知 → 形式知 →
  再暗黙知の継承サイクルをコードに落とし込み。
- **Sender switch**: `friendly` / `system` / `notify` の 3 プリセットで送信元アイコン・名称を切替、
  「寮母の会話」「システム通知」「保護者への通知」を UX 上明確に区別。
- **保護者連携の合意設計**: 6 桁招待コードで紐づけたうえで、学生本人が同意した情報のみを
  月次サマリー（Pull / 月次 Push）で保護者に届ける「監視ではなく合意ベースの見守り」。
- **オフラインデモ対応**: `GEMINI_MOCK_MODE` を有効化すると seed ベースの静的フォールバックで応答。
  発表当日のネットワーク障害・API 障害に対する保険。

## 技術スタック

| レイヤー | 採用技術 | 選定理由 |
| --- | --- | --- |
| 言語 | Python 3.12 | LINE SDK / Gemini SDK / FastAPI の第一言語で開発速度優先 |
| Web フレームワーク | FastAPI（uvicorn） | 型ヒント連携と非同期対応、LINE の低レイテンシ要件と相性 |
| LINE SDK | line-bot-sdk v3 | Messaging API v3 の Flex Message / Quick Reply / Loading indicator を活用 |
| LLM | Google Gemini（`gemini-flash-lite-latest`） | 低コスト・低レイテンシで日本語の生活相談に十分な品質 |
| データ永続化 | JSON ファイル（`fcntl` ロック付き） | MVP スコープに対する意図的な選定。RDB 導入は事業化フェーズで再検討 |
| プロセス管理 | systemd | 既存の自宅サーバー運用と揃え、月次 Push は timer で駆動 |
| リバースプロキシ | Apache | 既存の `linebot.kmchan.jp` 基盤を再利用 |
| ホスティング | 自宅 Ubuntu サーバー | デモまでのコスト最小化。事業化フェーズで PaaS 移行を想定 |

- ポート: `8084` / パス: `/ai_house_mother`
- Webhook: `POST /ai_house_mother/callback` / ヘルスチェック: `GET /ai_house_mother/health`

## チーム

- **提案チーム**: 宮崎総研（MRI）
- **文脈**: 同志社大学経済学部・経済学会「ビジネスアイデア大会 2026」決勝プレゼン向け MVP

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

開発規約は [.codex/AGENTS.md](.codex/AGENTS.md) と [.codex/rules/](.codex/rules/) を参照。

## ライセンス

Copyright (c) 2026 MRI. All rights reserved. 詳細は [LICENSE](LICENSE) を参照。
