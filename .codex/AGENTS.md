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

1. **作業を依頼している開発者の明示的な指示**（直接の依頼、`About.md` の記述）— 最優先
2. **このリポジトリのローカル規約**（`.codex/rules/*`）
3. **各開発者のグローバル設定**（`~/.claude/CLAUDE.md` 等、AI エージェント個人の環境）
4. **AI エージェントのデフォルト挙動** — 最低優先

## チーム / 開発者コンテキスト

- オーナー: kmchan（メール: `kmchan@kmchan.jp`、GitHub: `kmch4n`）。
- 提案チーム 宮崎総研（MRI）のメンバーが複数在籍し、各自の GitHub アカウントで貢献する。
- 開発者との対話は日本語で行う。
- 言語ポリシー（対話は日本語 / コード・コミット・PR タイトルは英語 / Issue・PR 本文は日本語）は `@rules/code_style.md` を参照。

## クイックリファレンス

### コミットメッセージ

```
[✨] English commit message
```

詳細は `@rules/commit_message.md`。

### ブランチ運用

- `main` 直接コミットは禁止。必ずブランチを切って作業し、PR 経由で merge する。
- ブランチ命名: `feature/xxx` / `fix/xxx` / `refactor/xxx` / `docs/xxx` / `chore/xxx`。
- 1 人開発中はセルフレビューで自分で merge してよい（PR は必ず経由）。

詳細は `@rules/git_workflow.md`。

### 技術スタック

- Python 3.12 + FastAPI + line-bot-sdk v3
- LLM: Gemini 2.0 Flash-Lite
- データ: JSON ファイル（`fcntl` ロック付き）
- ポート 8084、パス `/ai_house_mother`

詳細は `@rules/project_rules.md`。

### 実装前の確認

- 機能追加・仕様変更はドキュメントファースト（着手前に必ず `docs/` を先に編集）。
- 開発者の明示的な指示なしに実装・書き込み操作をしない。
- 議論・レビュー・仕様確認はデフォルト read-only。

詳細は `@rules/development_policy.md`。
