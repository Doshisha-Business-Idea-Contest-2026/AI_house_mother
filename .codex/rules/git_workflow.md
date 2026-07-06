# Git 運用ルール

このファイルは AI 寮母リポジトリの Git 運用ルールを定義する。

## 基本方針

- ユーザーの明示的な指示がない限り、`git add`、`git commit`、GitHub Issue の書き込みアクションを実行してはならない。
- コミット依頼を受けた際は `.codex/rules/commit_message.md` と直近 10 件のコミット履歴を確認してからメッセージを起草する。
- コミットメッセージや Issue 本文、コメント、PR 説明に Claude、Codex、その他 AI エージェントへの言及を含めない。
- コミット・Issue 書き込み前に、`git config` の identity がユーザー本人（`kmchan@kmchan.jp` / `kmch4n`）のものであることを確認する。Bot や AI エージェントの identity になっていたら停止して報告する。
- `git commit` 済みの変更は、ユーザーの追加指示なしに `git push` してよい（このリポジトリ固有の運用。`git add` / `git commit` 自体は従来どおり明示指示が必要）。force push（`--force` / `-f`）は「破壊的操作の禁止」に従い実行しない。

## ブランチ運用

### MVP 期間（〜 2026-07-08 頃まで）

- **`main` ブランチで直接作業して良い**。
- MVP の完成を最速で達成することが最優先のため、フィーチャーブランチ運用は省略する。
- 代わりに **コミットをこまめに行う**（1 機能・1 修正 = 1 コミットが理想）。
- push もこまめに行う（コミット後に随時 push してよい。force push を除く）。

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

## PR の書き方

- PR タイトルはコミットメッセージと同じ規約（`[gitmoji] English title`）を使う。
- PR 本文には以下を含める:
  - Summary（変更概要、1〜3 の箇条書き）
  - Test plan（動作確認手順のチェックリスト）
  - 関連 Issue / チケット番号（あれば）
- AI 生成であっても "Generated with Claude Code" などの署名を追加しない。

## Issue の書き方

Issue 本文は **日本語**で書く（日本人チームでの運用のため）。ただし種別接頭辞（`feat` / `bug` など）とラベルは英語のまま使う。

### タイトル

`[種別] 簡潔な日本語タイトル` の形式にする。

- 種別接頭辞はブランチ命名と揃えた 5 種類: `feat` / `bug` / `refactor` / `docs` / `chore`。
- 例:
  - `[feat] 保護者の招待コード入力フローを追加`
  - `[bug] Android で Flex Message が崩れる`
  - `[docs] MVP スコープに月次サマリーを追記`

### ラベル

作成した Issue には必ず **種別ラベルと優先度ラベルを 1 つずつ**付ける。

- **種別ラベル**（タイトル接頭辞と一致させる）: `type: feat` / `type: bug` / `type: refactor` / `type: docs` / `type: chore`
- **優先度ラベル**: `priority: high` / `priority: medium` / `priority: low`

| priority | 目安 |
| --- | --- |
| `priority: high` | デモ・MVP を止める。最優先で着手。 |
| `priority: medium` | 通常。MVP スコープ内で対応する。 |
| `priority: low` | あると良い。余裕があれば対応。 |

ラベルの初期セットは `.github/setup-labels.sh` で一括作成できる（`gh auth login` 済みが前提）。

### 本文フォーマット

種別ごとに以下のテンプレートに従う。GitHub 上では `.github/ISSUE_TEMPLATE/` のフォームが対応する。

#### feat（機能追加）

```markdown
## 概要
（何を追加するか 1〜2 文）

## 背景・目的
（なぜ必要か。関連する `docs/` のファイル名やユーザーストーリー番号を明記）

## 受け入れ条件
- [ ] （満たすべき条件を列挙）
- [ ]

## 補足
（設計メモ・参考リンクなど。任意）
```

> **ドキュメントファースト規約**に従い、機能追加はまず `docs/` を更新してから Issue 化・実装する。背景欄に対応する `docs/` を必ず紐づける。

#### bug（バグ修正）

```markdown
## 概要
（何が問題か 1〜2 文）

## 再現手順
1.
2.

## 期待する挙動

## 実際の挙動

## 環境
- 端末 / OS:
- LINE アプリ版:
- 役割: 学生 / 保護者

## 補足
（ログ・スクリーンショットなど。任意）
```

#### refactor / docs / chore

```markdown
## 概要
（何をするか 1〜2 文）

## 目的・背景
（なぜ必要か）

## done の定義
- [ ]
```

### 運用メモ

- Issue はすべて `gh` CLI で作成する（`gh issue create`）。
- `gh` 操作前に認証状態を確認する。未認証なら `gh auth login` をユーザーに依頼する。
- 種別・優先度ラベルの付け忘れがないか、作成後に `gh issue view <番号>` で確認する。
- Issue の新規作成は他人に見える書き込み操作のため、ユーザーの明示的な指示があってから行う。

## GitHub 操作

- GitHub 操作はすべて `gh` CLI を使う。
- Issue、PR、Release、チェック等の操作はまず `gh` で試みる。
- `gh` が失敗する場合のみ、Web UI での作業をユーザーに依頼する。

## 秘密情報の扱い

- `.env`、`credentials.json`、API キーを含むファイルは絶対にコミットしない。
- `.gitignore` に必ず登録する。
- 誤ってコミットしてしまった場合は速やかにユーザーに報告し、必要ならリポジトリ履歴からの削除（`git filter-repo` 等）と該当キーのローテーションを提案する。
