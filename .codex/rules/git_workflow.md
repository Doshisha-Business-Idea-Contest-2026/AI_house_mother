# Git 運用ルール

このファイルは AI 寮母リポジトリの Git 運用ルールを定義する。

## 基本方針

- ユーザーの明示的な指示がない限り、`git add`、`git commit`、`git push`、GitHub Issue の書き込みアクションを実行してはならない。
- コミット依頼を受けた際は `.codex/rules/commit_message.md` と直近 10 件のコミット履歴を確認してからメッセージを起草する。
- コミットメッセージや Issue 本文、コメント、PR 説明に Claude、Codex、その他 AI エージェントへの言及を含めない。
- コミット・Issue 書き込み前に、`git config` の identity がユーザー本人（`kmchan@kmchan.jp` / `kmch4n`）のものであることを確認する。Bot や AI エージェントの identity になっていたら停止して報告する。
- push はユーザーが明示的に指示するまで実行しない。

## ブランチ運用

### MVP 期間（〜 2026-07-08 頃まで）

- **`main` ブランチで直接作業して良い**。
- MVP の完成を最速で達成することが最優先のため、フィーチャーブランチ運用は省略する。
- 代わりに **コミットをこまめに行う**（1 機能・1 修正 = 1 コミットが理想）。
- push もこまめに行う（ユーザーが指示したタイミングで）。

### MVP 完成以降

- **`main` への直接コミットは禁止**。以下のブランチ命名規約に従う。
- ブランチ命名規約:
  - `feature/xxx` — 新機能追加
  - `fix/xxx` — バグ修正
  - `refactor/xxx` — リファクタリング
  - `docs/xxx` — ドキュメントのみの変更
  - `chore/xxx` — ビルド設定・依存更新など
- 作業完了後は Pull Request を作成し、他メンバーがレビューしてから `main` にマージする。
- 1 人開発時でもブランチを切ってセルフレビューする文化を作る。
- マージ後はローカル・リモート両方のブランチを削除する。

### 命名例

```
feature/parent-invitation-code
fix/flex-message-android-rendering
refactor/extract-gemini-client
docs/add-mvp-scope
chore/upgrade-line-bot-sdk
```

## コミット粒度

- 1 コミット = 1 論理的変更。
- 「タイポ修正 + 新機能追加」のような無関係な変更を混ぜない。
- コミット前に `git diff --staged` で内容を確認する。
- `git add -A` や `git add .` は避け、対象ファイルを明示的に指定する（`.env` や大きなバイナリの誤コミット防止）。

## 破壊的操作の禁止

以下は AI エージェントが自発的に実行してはならない。ユーザーの明示的な指示がある場合のみ実行する。

- `git push --force` / `git push -f`
- `git reset --hard`
- `git checkout .` / `git restore .`
- `git clean -f`
- `git branch -D`
- `--amend`（既にプッシュ済みのコミットに対して）
- `--no-verify` などフックのスキップ
- `--no-gpg-sign` などの署名バイパス

### 特に重要

**`main` / `master` への force push は絶対に禁止**。仮に指示があってもユーザーに再確認する。

## PR / Issue の書き方

- PR タイトルはコミットメッセージと同じ規約（`[gitmoji] English title`）を使う。
- PR 本文には以下を含める:
  - Summary（変更概要、1〜3 の箇条書き）
  - Test plan（動作確認手順のチェックリスト）
  - 関連 Issue / チケット番号（あれば）
- AI 生成であっても "Generated with Claude Code" などの署名を追加しない。
- Issue は日本語で書いても良い（プロジェクト内向けタスク管理として使う場合）。ただし OSS 化する際は英語に統一する可能性がある。

## GitHub 操作

- GitHub 操作はすべて `gh` CLI を使う。
- Issue、PR、Release、チェック等の操作はまず `gh` で試みる。
- `gh` が失敗する場合のみ、Web UI での作業をユーザーに依頼する。

## 秘密情報の扱い

- `.env`、`credentials.json`、API キーを含むファイルは絶対にコミットしない。
- `.gitignore` に必ず登録する。
- 誤ってコミットしてしまった場合は速やかにユーザーに報告し、必要ならリポジトリ履歴からの削除（`git filter-repo` 等）と該当キーのローテーションを提案する。
