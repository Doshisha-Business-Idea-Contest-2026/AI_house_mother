# 07. アーキテクチャ

## 1. このドキュメントの目的

AI 寮母 MVP のシステム構成、ディレクトリ構造、モジュール分割、デプロイ手順を定義する。

## 2. システム構成図

```
┌─────────────┐              ┌─────────────────────┐
│ LINE User   │              │ Google AI Studio    │
│ (学生/保護者) │              │ (Gemini 2.0 Flash-  │
└──────┬──────┘              │  Lite)              │
       │                     └──────────▲──────────┘
       │ LINE Messenger                 │ HTTPS
       │                                │
       ▼                                │
┌──────────────────┐                    │
│ LINE Platform    │                    │
│ (Messaging API)  │                    │
└──────┬───────────┘                    │
       │ Webhook (HTTPS POST)           │
       │                                │
       ▼                                │
┌────────────────────────────────────────┴───────┐
│         Ubuntu Server (自宅)                    │
│                                                 │
│  ┌───────────────────────────────────────┐     │
│  │  Apache HTTP Server                   │     │
│  │  linebot.kmchan.jp (SSL)              │     │
│  │  /ai_house_mother → localhost:8084    │     │
│  └──────────┬────────────────────────────┘     │
│             │                                   │
│             ▼                                   │
│  ┌───────────────────────────────────────┐     │
│  │  FastAPI App (uvicorn)                │     │
│  │  ai_house_mother.service (systemd)    │     │
│  │  Port 8084                            │     │
│  │                                       │     │
│  │  ┌─────────────┐   ┌───────────────┐  │     │
│  │  │ Router      │──▶│ Handlers      │  │     │
│  │  │ /callback   │   │ (message/     │  │     │
│  │  │ /health     │   │  postback/    │  │     │
│  │  └─────────────┘   │  follow)      │  │     │
│  │                    └───────┬───────┘  │     │
│  │                            ▼          │     │
│  │                    ┌───────────────┐  │     │
│  │                    │ Services      │  │     │
│  │                    │ - Gemini      │──┼─────┘
│  │                    │ - LINE reply  │  │
│  │                    │ - Session     │  │
│  │                    │ - Storage     │  │
│  │                    └───────┬───────┘  │
│  │                            ▼          │
│  │                    ┌───────────────┐  │
│  │                    │ Data (JSON +  │  │
│  │                    │ fcntl lock)   │  │
│  │                    └───────────────┘  │
│  └───────────────────────────────────────┘     │
│                                                 │
└─────────────────────────────────────────────────┘
```

## 3. ディレクトリ構造

```
AI_house_mother/
├── .claude/
│   └── CLAUDE.md
├── .codex/
│   ├── AGENTS.md
│   └── rules/
│       ├── commit_message.md
│       ├── code_style.md
│       ├── git_workflow.md
│       ├── project_rules.md
│       └── development_policy.md
├── docs/
│   ├── 00_product_context.md
│   ├── 01_requirements.md
│   ├── ... (このファイル群)
├── src/
│   ├── main.py               # FastAPI エントリポイント
│   ├── config.py             # 環境変数・設定
│   ├── router.py             # Webhook/health エンドポイント
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── follow.py         # 友だち追加時
│   │   ├── message.py        # テキストメッセージ
│   │   ├── postback.py       # Quick Reply / Flex Message ボタン
│   │   ├── student.py        # 学生向けフロー
│   │   └── parent.py         # 保護者向けフロー
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini.py         # Gemini API クライアント
│   │   ├── line_reply.py     # LINE 応答送信
│   │   ├── session.py        # インメモリセッション管理
│   │   ├── storage.py        # JSON ファイル I/O + fcntl lock
│   │   ├── prompts.py        # プロンプトテンプレート
│   │   ├── invitations.py    # 招待コード発行・検証
│   │   └── monthly_report.py # 月次サマリー生成
│   ├── templates/
│   │   └── flex/
│   │       ├── __init__.py
│   │       ├── welcome.py
│   │       ├── activity_carousel.py
│   │       ├── monthly_report.py
│   │       └── invitation_code.py
│   └── utils/
│       ├── __init__.py
│       ├── hash.py           # user_id ハッシュ化
│       └── datetime.py       # 日時ヘルパー
├── data/
│   ├── users.json
│   ├── profiles.json
│   ├── posts.json
│   ├── invitations.json
│   ├── parent_links.json
│   ├── seed/
│   │   ├── areas.json
│   │   ├── stores.json
│   │   ├── events.json
│   │   ├── senior_posts.json
│   │   └── demo_profiles.json
│   └── logs/                 # .gitignore で除外
├── tests/
│   ├── __init__.py
│   └── test_placeholder.py   # MVP 期間は最小限
├── scripts/
│   ├── init_data.py          # data/*.json の初期化
│   └── run_local.sh          # ローカル起動スクリプト
├── deploy/
│   ├── ai_house_mother.service   # systemd unit ファイル
│   └── apache.conf.snippet       # Apache リバースプロキシ設定
├── .env
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## 4. モジュール責務

### 4.1 `src/main.py`

- FastAPI アプリ初期化
- ログ設定
- ライフサイクル管理（`startup` で seed データ読み込み）
- `uvicorn.run(port=8084)`

### 4.2 `src/config.py`

- `.env` 読み込み
- 環境変数の型付き公開:
  - `LINE_CHANNEL_ACCESS_TOKEN`
  - `LINE_CHANNEL_SECRET`
  - `GEMINI_API_KEY`
  - `FASTAPI_PORT`
  - `LOG_LEVEL`
- LINE SDK 設定オブジェクト
- Gemini クライアント初期化

### 4.3 `src/router.py`

- `POST /ai_house_mother/callback`: Webhook 受信
- `GET /ai_house_mother/health`: ヘルスチェック
- LINE 署名検証を router 層で実施
- 各イベントを `handlers/` にディスパッチ

### 4.4 `src/handlers/`

| モジュール | 責務 |
| --- | --- |
| `follow.py` | 友だち追加時のウェルカム + 役割選択 |
| `message.py` | テキストメッセージのルーティング（コマンド判定・自由発話） |
| `postback.py` | Quick Reply / Flex Message ボタン処理 |
| `student.py` | 学生向けフロー: プロフィール、やりたいこと、生活相談、投稿、招待コード |
| `parent.py` | 保護者向けフロー: 連携、月次レポート |

### 4.5 `src/services/`

| モジュール | 責務 |
| --- | --- |
| `gemini.py` | Gemini API 呼び出しラッパー、リトライ、エラーハンドリング |
| `line_reply.py` | LINE Messaging API への応答送信（reply / push） |
| `session.py` | インメモリセッション管理（10 分 TTL） |
| `storage.py` | `data/*.json` の読み書き（fcntl ロック、atomic write） |
| `prompts.py` | System Prompt、機能別プロンプトテンプレート |
| `invitations.py` | 招待コード発行・検証・使用ロジック |
| `monthly_report.py` | 月次サマリー生成（対象月の投稿抽出） |

### 4.6 `src/templates/flex/`

Flex Message ビルダー関数。それぞれ引数を受け取って FlexMessage オブジェクトを返す。

### 4.7 `src/utils/`

汎用ユーティリティ。ハッシュ化、日時整形など。

## 5. 処理フロー例

### 5.1 学生の「やりたいこと相談」フロー

```
1. LINE User → LINE Platform → Webhook POST
2. Apache → localhost:8084/ai_house_mother/callback
3. FastAPI router.py: 署名検証、event 抽出
4. handlers/postback.py: data="menu:want_to_do" を検知
5. handlers/student.py::handle_want_to_do():
   5.1 session.get(user_id) でステート取得
   5.2 storage.load_profile(user_id) でプロフィール取得
   5.3 プロフィール未登録なら FR-S2 に誘導
   5.4 storage.load_seed_areas/stores/events/senior_posts でコンテキスト取得
   5.5 services/gemini.py::propose_activities(profile, context) 呼び出し
       - services/prompts.py::build_activity_prompt() でプロンプト生成
       - Gemini SDK 呼び出し
       - JSON パース
   5.6 templates/flex/activity_carousel.py で Flex Message 構築
   5.7 services/line_reply.py::reply(reply_token, flex_message)
6. LINE Platform → LINE User に配信
```

### 5.2 保護者の連携フロー

```
1. handlers/parent.py: postback data="menu:link_code" 受信
2. session.set_state(user_id, "link.code")
3. 「6 桁のコードを入力してください」応答
4. 次のメッセージ受信 → handlers/message.py がステート判定
5. services/invitations.py::use_invitation(code, parent_user_id):
   5.1 storage.load(invitations.json)
   5.2 code 検索・期限・使用状態チェック
   5.3 有効なら used_at/used_by_parent_id 更新
   5.4 storage.save(invitations.json)
   5.5 storage.load(parent_links.json) → 追加
   5.6 storage.save(parent_links.json)
6. 学生プロフィールから学生名を取得して確認応答
7. 学生の LINE user へ「保護者と連携しました」を push
```

## 6. デプロイ

### 6.1 事前準備

1. LINE 公式アカウント取得、Messaging API チャネル作成
2. Google AI Studio で Gemini API キー取得
3. `.env` に上記シークレットを設定

### 6.2 セットアップ手順

```bash
cd /home/kmch4n/dev/AI_house_mother
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 初期データ生成（seed データは手動で書く。ユーザーレコードは空で開始）
python scripts/init_data.py

# 動作確認
python -m uvicorn src.main:app --host 0.0.0.0 --port 8084
```

### 6.3 systemd 登録

`deploy/ai_house_mother.service` を `/etc/systemd/system/` へコピー:

```ini
[Unit]
Description=AI House Mother LINE Bot
After=network.target

[Service]
Type=simple
User=kmch4n
WorkingDirectory=/home/kmch4n/dev/AI_house_mother
EnvironmentFile=/home/kmch4n/dev/AI_house_mother/.env
ExecStart=/home/kmch4n/dev/AI_house_mother/.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8084
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo cp deploy/ai_house_mother.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai_house_mother.service
sudo systemctl start ai_house_mother.service
sudo systemctl status ai_house_mother.service
```

### 6.4 Apache リバースプロキシ

`/etc/apache2/sites-enabled/linebot.kmchan.jp.conf` と `linebot.kmchan.jp-le-ssl.conf` の両方に以下を追加:

```apache
ProxyPass /ai_house_mother http://localhost:8084/ai_house_mother
ProxyPassReverse /ai_house_mother http://localhost:8084/ai_house_mother

<Location /ai_house_mother>
    Require all granted
</Location>
```

```bash
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### 6.5 LINE Webhook 登録

LINE Developers Console で:

- Webhook URL: `https://linebot.kmchan.jp/ai_house_mother/callback`
- Webhook を有効化
- 応答メッセージ: 無効化（Bot が応答するため）
- あいさつメッセージ: 好みで設定

### 6.6 動作確認

```bash
# ヘルスチェック
curl https://linebot.kmchan.jp/ai_house_mother/health

# 期待レスポンス
{"status":"ok","service":"ai_house_mother","timestamp":"..."}

# ログ確認
journalctl -u ai_house_mother.service -f
```

## 7. 依存パッケージ

`requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
line-bot-sdk==3.21.0
google-generativeai==0.8.3
python-dotenv==1.0.0
pydantic==2.9.2
```

（バージョンは実装開始時点で最新安定版に更新する）

## 8. 開発時ローカル実行

Webhook を LINE Platform から受けるには公開 URL が必要。開発中は自宅サーバー上で直接 uvicorn を動かして本番ドメインで受ける。

```bash
# フォアグラウンド実行（デバッグ）
source .venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8084

# systemd を止めて手動起動
sudo systemctl stop ai_house_mother.service
uvicorn src.main:app --reload --host 0.0.0.0 --port 8084

# 開発が終わったら再起動
sudo systemctl start ai_house_mother.service
```

## 9. ログ・監視

- 全ログは journald 経由
- `journalctl -u ai_house_mother.service -f` で追跡
- MVP 期間は監視ツールなし、目視確認のみ

## 10. スケーラビリティ

**MVP 対象外**。単一プロセスで動作、水平スケール不可（インメモリセッション、ファイル I/O）。本番運用時は Redis + PostgreSQL への移行を検討。

## 11. セキュリティ

- LINE Webhook 署名検証を必須
- HTTPS 通信のみ（Apache + Let's Encrypt SSL）
- `.env` は Git 管理外
- fail2ban 等の追加防御は既存サーバー設定に依存

## 12. 変更履歴

| 日付 | 変更内容 | 記入者 |
| --- | --- | --- |
| 2026-07-05 | 初版作成 | kmch4n |
