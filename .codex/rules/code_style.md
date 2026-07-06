# コードスタイル規約

このファイルは AI 寮母リポジトリのコーディング規約を定義する。Python + FastAPI + LINE Bot が主なスタックである。

## 言語ポリシー

- ユーザーとの対話は日本語。
- コード、コメント、コミットメッセージ、リリースノートは英語。
- Issue と PR の本文は日本語（日本人チームでの運用のため）。ただし PR タイトルは `[gitmoji] English`、Issue タイトルの種別接頭辞（`feat` / `bug` など）とラベルは英語のまま使う。詳細は `git_workflow.md` を参照。
- README、`docs/` 配下のプロジェクト向けドキュメントは日本語で統一する（このリポジトリの慣習）。
- 触るファイルはすべて UTF-8 でエンコードする。

## 全般

- インデントは半角スペース 4（タブ禁止）。
- 文字列リテラルはダブルクォート優先。
- 1 ファイルは 500 〜 700 行を目安に、超えそうならモジュール分割する。
- すべての関数・メソッドに型ヒント（type hints）を付ける。

## Python

- フォーマッタ: **Black** + **Ruff**。
- スタイル: **PEP 8** に準拠。
- ドックストリング: **Google スタイル**。
- 型チェック: **mypy**。
- 依存管理: `pip` + `requirements.txt`。
- 仮想環境: `.venv/` に作成。既存の LINE Bot と同じ運用。
- ロガー: `logging.getLogger(__name__)` パターンを使う。

### Google スタイル docstring 例

```python
def build_flex_carousel(activities: list[Activity]) -> FlexMessage:
    """Build a Flex carousel message from activity suggestions.

    Args:
        activities: List of activity candidates to render as bubbles.

    Returns:
        A FlexMessage ready to be sent via LINE Messaging API.

    Raises:
        ValueError: If ``activities`` is empty or exceeds 10 items.
    """
```

## 命名規則

- API クライアントのインスタンス名は `cl` を使う（`client` は使わない）。
  - 例: `cl = genai.Client(api_key=...)`
- 定数は `UPPER_SNAKE_CASE`。
- クラスは `PascalCase`、関数・変数は `snake_case`。
- プライベート属性は `_leading_underscore`。

## 出力ルール

- JSON 出力は `indent=4`、`ensure_ascii=False` を必須とする。
  - 例: `json.dump(data, f, indent=4, ensure_ascii=False)`
- ログ・print 出力は本番環境で余分な情報が出ないよう精査する。
- ファイル全体を再出力せず、外科的な最小差分で編集する。
- コード引用時はファイルパスと行番号を併記する（例: `handlers/student.py:42`）。

## ファイル操作・エンコーディング・改行

このプロジェクトは Ubuntu サーバー上で動作するため、以下の運用に統一する。

| ファイル種別 | エンコーディング | 改行 |
| --- | --- | --- |
| Python (`.py`) | UTF-8 (BOM なし) | LF |
| Markdown (`.md`) | UTF-8 (BOM なし) | LF |
| JSON (`.json`) | UTF-8 (BOM なし) | LF |
| YAML / TOML | UTF-8 (BOM なし) | LF |
| shell スクリプト (`.sh`) | UTF-8 (BOM なし) | LF |

## Web / フロントエンド（本 MVP では対象外だが将来のために）

- アクセシビリティ: ARIA ラベル付与、キーボードナビゲーション確保。
- レスポンシブ: モバイルファースト設計。

## 禁止事項

- タブインデント。
- シングルクォート優先の統一（Black のデフォルトはダブル）。
- 型ヒントの省略。
- 例外を握り潰す `except Exception: pass`。
- `print` デバッグの残置（`logging` に置き換える）。
- ハードコードされた秘密情報。必ず `.env` 経由で読み込む。
