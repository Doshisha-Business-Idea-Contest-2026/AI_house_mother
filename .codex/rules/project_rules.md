# プロジェクト固有ルール

このファイルは AI 寮母（AI House Mother）プロジェクト固有の技術・運用ルールを定義する。

## プロジェクト概要

- **正式名称**: AI 寮母 〜つながりを生むAIチャット〜
- **文脈**: 同志社大学経済学部・経済学会主催「ビジネスアイデア大会 2026」決勝プレゼン向け MVP。
- **提案チーム**: 宮崎総研（MRI）。
- **プロダクトの詳細**: `docs/00_product_context.md` を参照。
- **MVP スペック**: `docs/` 配下のドキュメントを参照。

## 技術スタック（確定）

| レイヤー | 採用技術 |
| --- | --- |
| 言語 | Python 3.12 |
| Web フレームワーク | FastAPI |
| LINE SDK | line-bot-sdk v3.x |
| LLM | Google Gemini 2.0 Flash-Lite |
| データ永続化 | JSON ファイル（`fcntl` ロック付き） |
| プロセス管理 | systemd |
| リバースプロキシ | Apache（既存）|
| ホスティング | 自宅 Ubuntu サーバー |
| 依存管理 | `pip` + `requirements.txt` |
| 仮想環境 | `.venv/` |
| フォーマッタ | Black + Ruff |
| 型チェック | mypy |

## サーバー配置

- **ポート**: 8084
- **パス**: `/ai_house_mother`
- **Webhook URL**: `https://linebot.kmchan.jp/ai_house_mother/callback`
- **ヘルスチェック**: `https://linebot.kmchan.jp/ai_house_mother/health`
- **systemd service 名**: `ai_house_mother.service`
- **リポジトリパス**: `/home/kmch4n/dev/AI_house_mother/`

## MVP スコープ（含む）

- 学生・保護者の役割分岐（初回友だち追加時に Quick Reply で選択）
- 学生プロフィール登録（対話形式）
- 「やりたいこと相談」機能（Gemini による活動提案 + Flex Message）
- 生活相談機能（先輩投稿・地域情報を活用した回答）
- 経験投稿機能（対話形式、カテゴリ選択）
- 保護者連携（6 桁招待コード方式）
- 保護者向け月次サマリー（「今月のレポート」ボタン）

## MVP スコープ（除外）

以下の機能は MVP に含めない。「今後の展望」として発表資料には残す可能性があるが、実装しない。

- 緊急通知
- AI 利用統計
- クーポン・ポイント機能
- モデレーション機能（投稿承認フロー）
- LIFF（LINE Front-end Framework）
- 地域店舗の自己登録機能（架空データを手動投入）
- RAG（ベクトル検索）
- 学生同士のマッチング

## データ運用

- **架空データのみを使う**。実在の学生・保護者・店舗情報は使用しない。
- 架空学生プロフィールは 3 〜 5 名分、チームメンバーをモデルにできるがフルネームや個人特定できる情報は避ける。
- 地域情報 30 件、店舗 15 件、イベント 10 件、先輩投稿 20 件を目安に手動投入。
- JSON ファイルは `data/` 配下に配置し、`fcntl` ロックで並行書き込みを制御する（既存 `kcb_linebot/storage.py` と同じパターン）。
- 会話ログを保存する場合は必ず本人同意フローを設計する（MVP では最小限に留める）。

## 個人情報・プライバシー

- LINE の user_id は個人識別子として扱い、ログには出さない（デバッグ時はハッシュ化）。
- 保護者に共有する情報は「学生本人が明示的に同意した範囲」に限定する。
- 医療判断、法律判断、緊急対応判断は AI が断定しない。公式窓口や 119 番などへの誘導に留める。
- 実在の店舗・病院名を回答する場合は「情報が古い可能性がある」旨を明記する。

## AI 回答の制約

Gemini への system prompt には以下を必ず含める。

- 医療的診断をしない。「症状が続く場合は医療機関を受診してください」に誘導。
- 法律相談に断定的に答えない。専門家相談を推奨。
- 緊急時は 110/119 と教える。
- 実在の店舗・施設について古い情報の可能性を注記。
- ユーザーが登録した学生プロフィール以外の個人情報を漏らさない。

## LINE Bot の UX 方針

- Quick Reply、Flex Message を積極活用する。
- リッチメニューは MVP 期間内で余裕があれば実装（優先度: 中）。
- テキスト応答は簡潔に。長文になる場合は Flex Message や複数バブルで分割。
- 絵文字は日本語ユーザーが自然に受け取れる範囲で使う（過剰使用は避ける）。

## デモ運用

- **発表当日**: 学生役アカウント + 保護者役アカウントの 2 台構成で実演。
- **審査員体験**: QR コードで友だち追加してもらい、実際に触ってもらう選択肢も用意。
- **デモシナリオ**: `docs/08_demo_scenario.md` を参照。

## systemd サービス設定

サービスユニットファイルは以下に配置する想定（実装時に作成）。

```
/etc/systemd/system/ai_house_mother.service
```

管理コマンド:

```bash
# ステータス確認
systemctl status ai_house_mother.service

# 再起動
sudo systemctl restart ai_house_mother.service

# ログ確認
journalctl -u ai_house_mother.service -f
```

## Apache リバースプロキシ設定

既存の `/etc/apache2/sites-enabled/linebot.kmchan.jp*.conf` に以下エントリを追加する。

```apache
ProxyPass /ai_house_mother http://localhost:8084/ai_house_mother
ProxyPassReverse /ai_house_mother http://localhost:8084/ai_house_mother

<Location /ai_house_mother>
    Require all granted
</Location>
```

追加後は `sudo systemctl reload apache2` で反映。

## 環境変数（.env）

必須:

```
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
GEMINI_API_KEY
```

任意:

```
FASTAPI_PORT=8084
FASTAPI_DEBUG=False
LOG_LEVEL=INFO
```

`.env` は絶対に Git にコミットしない。`.env.example` はコミットする。
