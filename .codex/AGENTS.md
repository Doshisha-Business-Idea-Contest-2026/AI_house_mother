# AI 寮母 - AI エージェント・開発者向け規約

このファイルは AI 寮母リポジトリで作業するすべての AI エージェント（Claude Code, Codex, Gemini CLI 等）および人間の開発者が守るべき規約のエントリポイントである。

## プロジェクト概要

- **プロジェクト**: AI 寮母 〜つながりを生むAIチャット〜
- **文脈**: 同志社大学ビジネスアイデア大会 2026 決勝プレゼン向け MVP
- **提案チーム**: MRI
- **プロダクト詳細**: `docs/00_product_context.md`
- **仕様書**: `docs/` 配下（`00_product_context` 〜 `09_tasks` の連番構成）

## 規約マップ

作業内容に応じて必ず該当ファイルを参照すること。以下はすべて `@import` で本ファイルに読み込まれる。

| 規約ファイル | 何を見るか |
| --- | --- |
| `rules/commit_message.md` | gitmoji コミットメッセージ形式・Git 安全ポリシー |
| `rules/git_workflow.md` | ブランチ運用・PR・Issue・push・破壊的操作の禁止 |
| `rules/code_style.md` | コーディング規約・言語ポリシー・エンコーディング |
| `rules/project_rules.md` | 技術スタック・サーバー配置・MVP スコープ・プライバシー |
| `rules/development_policy.md` | 開発姿勢・秘密情報管理・意思決定の記録 |

@rules/commit_message.md
@rules/code_style.md
@rules/git_workflow.md
@rules/project_rules.md
@rules/development_policy.md

## 絶対に外さない要点

詳細は上記の各規約ファイルに従うこと。特に違反しやすい要点のみ抜粋する。

- **ドキュメントファースト**: 機能追加・仕様変更は着手前に必ず `docs/` を先に編集する。
- **ブランチ + PR 経由**: `main` 直接コミット禁止。ブランチを切り、PR 経由で merge する（1 人開発中はセルフレビュー可）。
- **明示指示なしに書き込まない**: 実装・ファイル編集・Git 書き込みは開発者の明示的な指示があってから行う。議論・レビュー・仕様確認はデフォルト read-only。
- **コミット形式**: `[gitmoji] English subject`（例: `[✨] Add feature`）。

## 優先順位

規約が競合する場合、以下の優先順位で判断する。

1. **作業を依頼している開発者の明示的な指示** — 最優先
2. **このリポジトリのローカル規約**（`.codex/rules/*`）
3. **各開発者のグローバル設定**（`~/.claude/CLAUDE.md` 等、AI エージェント個人の環境）
4. **AI エージェントのデフォルト挙動** — 最低優先

## チーム / 開発者コンテキスト

- オーナー: kmchan（メール: `kmchan@kmchan.jp`、GitHub: `kmch4n`）。
- 提案チーム MRI のメンバーが複数在籍し、各自の GitHub アカウントで貢献する。
- 開発者との対話は日本語で行う。
- 言語ポリシー（対話は日本語 / コード・コミット・PR タイトルは英語 / Issue・PR 本文は日本語）は `@rules/code_style.md` を参照。
