# AI 寮母 - AI エージェント・開発者向け規約

このファイルは AI 寮母リポジトリで作業するすべての AI エージェント（Claude Code, Codex, Gemini CLI 等）および人間の開発者が守るべき規約のエントリポイントである。

## リポジトリ概要

- **プロジェクト**: AI 寮母 〜つながりを生むAIチャット〜
- **文脈**: 同志社大学ビジネスアイデア大会 2026 決勝プレゼン向け MVP
- **提案チーム**: 宮崎総研（MRI）
- **プロダクト詳細**: `About.md`
- **MVP スペック**: `docs/` 配下（整備中）

## 規約ファイル一覧

以下のファイルにルールを分割している。作業内容に応じて必ず該当ファイルを参照すること。

@rules/commit_message.md
@rules/code_style.md
@rules/git_workflow.md
@rules/project_rules.md
@rules/development_policy.md

## 優先順位

規約が競合する場合、以下の優先順位で判断する。

1. **ユーザーの明示的な指示**（直接の依頼、`About.md` の記述）— 最優先
2. **このリポジトリのローカル規約**（`.codex/rules/*`）
3. **ユーザーのグローバル設定**（`~/.claude/CLAUDE.md` 等、AI エージェント個人の環境）
4. **AI エージェントのデフォルト挙動** — 最低優先

## ユーザーコンテキスト

- ユーザー: kmchan（メール: `kmchan@kmchan.jp`、GitHub: `kmch4n`）
- ユーザーとの対話は日本語で行う。
- コード、コミットメッセージ、Issue、PR は英語で書く（プロジェクト内ドキュメントは日本語）。

## クイックリファレンス

### コミットメッセージ

```
[✨] English commit message
```

詳細は `@rules/commit_message.md`。

### ブランチ運用

- MVP 期間（〜 2026-07-08 頃）: `main` 直接コミット OK
- MVP 完了後: `feature/xxx`, `fix/xxx` などのブランチを切る

詳細は `@rules/git_workflow.md`。

### 技術スタック

- Python 3.12 + FastAPI + line-bot-sdk v3
- LLM: Gemini 2.0 Flash-Lite
- データ: JSON ファイル（`fcntl` ロック付き）
- ポート 8084、パス `/ai_house_mother`

詳細は `@rules/project_rules.md`。

### 実装前の確認

- ユーザーの明示的な指示なしに実装・書き込み操作をしない。
- 議論・レビュー・仕様確認はデフォルト read-only。

詳細は `@rules/development_policy.md`。
