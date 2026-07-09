# プロジェクト固有ルール

このファイルは AI 寮母（AI House Mother）プロジェクト固有の技術・運用ルールを定義する。

## プロジェクト概要

- **正式名称**: AI 寮母 〜つながりを生むAIチャット〜
- **文脈**: 同志社大学経済学部・経済学会主催「ビジネスアイデア大会 2026」決勝プレゼン向け MVP。
- **提案チーム**: MRI。
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
- 地域店舗の自己登録機能（実在店舗情報を手動 seed 投入で代替）
- RAG（ベクトル検索）
- 学生同士のマッチング

## データ運用

### 種別ごとのポリシー

seed データは種別ごとに扱いが異なる。人物系はプライバシー最優先で架空を維持、場所・イベント系は実在情報ベースで説得力を確保する。

| データ種別 | ファイル | 件数目安 | 扱い |
| --- | --- | --- | --- |
| 地域情報 | `data/seed/areas.json` | 30 | **実在化**（大学・図書館・保健センター・行政窓口等の公開情報） |
| イベント | `data/seed/events.json` | 10 | **実在化**（大学公式・行政主催イベント。日付は「毎年◯月開催」等で古風化回避） |
| 店舗 | `data/seed/stores.json` | 15 | **実在化**（民間実名店舗。全レコードに情報鮮度注記を必須付与） |
| 先輩投稿 | `data/seed/senior_posts.json` | 20 | **架空**（本人特定リスク回避） |
| デモプロフィール | `data/seed/demo_profiles.json` | 3〜5 | **架空**（チームメンバーをモデル可、フルネーム・個人特定情報は避ける） |

### 地理的カバー範囲

- **同志社大学今出川キャンパス周辺**（京都市上京区・中京区・北区）に集中させる。デモの「本当に使える感」を最大化するため、京都府全体や京都市全域には広げない。

### 実在情報の鮮度注記ルール

- 店舗 seed には `data_freshness_note`（例: `"2026-07 時点。営業状況は変更の可能性あり"`）と `source_url`（公式サイト URL、なければ null）フィールドを必須で持たせる。
- 地域・イベント seed には `last_verified_at`（例: `"2026-07"`）を必須で持たせる。
- Bot が実在の店舗・施設情報を返答に含めるときは Flex Message に情報鮮度注記を必ず併記する（`docs/06_ai_spec.md` の System Prompt ルール参照）。

### その他

- JSON ファイルは `data/` 配下に配置し、`fcntl` ロックで並行書き込みを制御する（既存 `kcb_linebot/storage.py` と同じパターン）。
- 会話ログを保存する場合は必ず本人同意フローを設計する（MVP では最小限に留める）。

## 個人情報・プライバシー

- LINE の user_id は個人識別子として扱い、ログには出さない（デバッグ時はハッシュ化）。
- 保護者に共有する情報は「学生本人が明示的に同意した範囲」に限定する。
- 医療判断、法律判断、緊急対応判断は AI が断定しない。公式窓口や 119 番などへの誘導に留める。
- **学生・保護者に関する情報（プロフィール・投稿・会話ログ・関係）は seed でも実運用でも架空またはユーザー本人由来のみ**。第三者の実在人物の情報を seed に含めない。
- 実在の店舗・病院名を回答する場合は「情報が古い可能性がある」旨を明記する（詳細は「データ運用」節の鮮度注記ルール参照）。
- **プレゼントくじ引き機能（FR-S11）でも当選者の氏名・住所・電話番号などの個人情報（PII）は収集・保存しない**。くじ引きはデモ演出として本人アカウント内で完結し、賞品は架空・実物配布は行わない。実物配布・当選者 PII 収集は今後の展望（`docs/02_mvp_scope.md §4.1` の除外、`docs/04_functional_spec.md §4.9`）。

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
