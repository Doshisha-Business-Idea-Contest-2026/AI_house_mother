# 05. データモデル

## 1. このドキュメントの目的

AI 寮母 MVP のデータ構造を定義する。全てのデータは **JSON ファイル** に永続化する（DB は使わない）。

- ファイル配置
- 各エンティティの JSON スキーマ
- 並行アクセスの取り扱い（`fcntl` ロック）
- seed データのサンプル（人物系は架空、場所・イベント系は実在情報ベース。詳細は `.codex/rules/project_rules.md` の「データ運用」節参照）
- キー戦略

## 2. ファイル配置

```
data/
├── users.json                 # LINE user 単位の基本情報（役割、作成日時）
├── profiles.json              # 学生プロフィール
├── posts.json                 # 学生の経験投稿
├── invitations.json           # 招待コード
├── parent_links.json          # 保護者-学生の紐付け
├── session_activities.json    # やりたいこと相談の 30 分短期永続化キャッシュ
├── monthly_report_state.json  # 月次サマリー Push の実行状態（二重実行防止用）
├── sponsored_engagement.json  # スポンサーPR「興味あり」クリックの計測ログ（FR-S9）
├── usage_stats.json           # 学生の月次利用回数（生活/活動相談・投稿・プロフィール、FR-P3 拡張）
├── coupon_distributions.json  # クーポン配布実績と last_awarded_milestone（FR-S10）
├── prize_draws.json           # プレゼント抽選履歴（FR-S11、PII 非収集）
├── seed/                      # 手動投入する seed データ（同志社今出川周辺）
│   ├── areas.json             # 地域情報（実在: 公共施設・行政窓口等）
│   ├── stores.json            # 学生向け店舗（実在: 民間実名店舗、鮮度注記必須）
│   ├── events.json            # 地域イベント・ボランティア（実在: 大学公式・行政主催）
│   ├── senior_posts.json      # 先輩投稿（架空: プライバシー保護）
│   ├── sponsored.json         # 協賛企業イベント PR（架空: 実在企業の課金体裁誤認を回避）
│   ├── coupons.json           # 地域店舗クーポン（架空: 実在店舗のクーポン誤認を回避、FR-S10）
│   ├── prizes.json            # プレゼント賞品（架空: 実在ブランド・実物配布の誤認を回避、FR-S11）
│   └── demo_profiles.json     # デモ用学生プロフィール（架空: プライバシー保護）
└── logs/
    └── conversations/         # 任意: 会話ログ（デバッグ用、本番運用時は要検討）
```

- **コミット対象**: `data/seed/*`（デモの再現性を確保）と `data/.gitkeep`/`data/seed/.gitkeep` のみ。
- **`.gitignore` 除外**: `data/logs/` および実行時に更新される JSON 11 種（`users.json`、`profiles.json`、`posts.json`、`invitations.json`、`parent_links.json`、`session_activities.json`、`monthly_report_state.json`、`sponsored_engagement.json`、`usage_stats.json`、`coupon_distributions.json`、`prize_draws.json`）。`data/seed/sponsored.json`・`data/seed/coupons.json`・`data/seed/prizes.json` は seed のためコミット対象。
- **理由**: デモ直前のリセット容易性を優先する。ランタイム JSON をコミット対象にすると、審査員体験時に生成された LINE user_id が Git 履歴に残る懸念もある。
- **初期化**: `python scripts/init_data.py` を実行すると、ランタイム JSON 11 種が空スキーマで作成される（既存ファイルは上書きしない）。

## 3. 並行アクセス

- 書き込みは **exclusive lock (`LOCK_EX`)**、読み込みは **shared lock (`LOCK_SH`)**（`fcntl.flock`）。
- 書き込みは **atomic write** で行う。手順:
  1. 保存先と同じディレクトリに `tempfile.mkstemp()` で一時ファイルを作る。
  2. 一時ファイルに `LOCK_EX` を掛けた状態で `json.dump()` + `flush()` + `os.fsync()`。
  3. `os.replace(tmp_path, final_path)` で原子的に差し替える。
  4. 失敗した場合は一時ファイルを削除する。
- 実装は `src/services/storage.py` の `load_json()` / `save_json()` を参照。
- MVP 期間は uvicorn を `--workers 1` で起動するため、単一プロセス内での競合は起きない。将来スケールする際も `fcntl` はプロセス間で機能するので、ワーカー数を増やしても壊れない。

**参考コード** (`src/services/storage.py` より抜粋):

```python
def save_json(relative_path: str, data: Any) -> None:
    path = DATA_DIR / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
```

## 4. スキーマ定義

### 4.1 users.json

役割等の LINE user 単位の最小限情報。

```json
{
    "users": {
        "U1234abcd...": {
            "line_user_id": "U1234abcd...",
            "role": "student",
            "created_at": "2026-07-05T14:00:00+09:00",
            "updated_at": "2026-07-05T14:00:00+09:00"
        }
    }
}
```

**フィールド**:
| フィールド | 型 | 説明 |
| --- | --- | --- |
| `line_user_id` | string | LINE の userId |
| `role` | `"student"` \| `"parent"` | 役割 |
| `created_at` | string (ISO 8601 + tz) | 初回作成日時 |
| `updated_at` | string (ISO 8601 + tz) | 最終更新日時 |

### 4.2 profiles.json

学生プロフィール。

```json
{
    "profiles": {
        "U1234abcd...": {
            "line_user_id": "U1234abcd...",
            "university": "同志社大学",
            "faculty": "経済学部",
            "grade": "1",
            "interests": ["地域活動", "ものづくり", "食・カフェ巡り"],
            "recent_effort": "英語のスコアを上げるためにTOEICを毎日勉強しています",
            "want_to_do": "京都の伝統文化に触れる体験がしたい、地域の人と関わってみたい",
            "created_at": "2026-07-05T14:10:00+09:00",
            "updated_at": "2026-07-05T14:10:00+09:00"
        }
    }
}
```

**フィールド**:
| フィールド | 型 | 説明 |
| --- | --- | --- |
| `line_user_id` | string | 学生の LINE userId |
| `university` | string | 大学名 |
| `faculty` | string | 学部名 |
| `grade` | string | 学年（"1"〜"4", "M1", "M2"） |
| `interests` | string[] | 興味関心タグ（複数） |
| `recent_effort` | string | 最近頑張っていること（自由記述、最大 200 文字） |
| `want_to_do` | string | やってみたいこと（自由記述、最大 200 文字） |
| `created_at` | string | 作成日時 |
| `updated_at` | string | 最終更新日時 |

### 4.3 posts.json

学生の経験投稿。

```json
{
    "posts": [
        {
            "post_id": "P00001",
            "line_user_id": "U1234abcd...",
            "category": "volunteer",
            "title": "下鴨神社の清掃活動に参加",
            "period_raw": "去年の10月",
            "period": "2025年10月",
            "summary": "下鴨神社の月例清掃に参加した",
            "learned": "地域の方と話すきっかけになった",
            "regret": "朝が早くて起きるのが大変だった",
            "advice": "動きやすい服装で行くのがおすすめ",
            "body": "【いつ】2025年10月\n【やったこと】下鴨神社の月例清掃に参加した\n【学び】地域の方と話すきっかけになった\n【残念・注意】朝が早くて起きるのが大変だった\n【次の人へ】動きやすい服装で行くのがおすすめ",
            "area": "下鴨神社",
            "share_with_parent": true,
            "created_at": "2026-07-05T18:30:00+09:00"
        }
    ]
}
```

**フィールド**:
| フィールド | 型 | 説明 |
| --- | --- | --- |
| `post_id` | string | `P` + 5 桁連番 |
| `line_user_id` | string | 投稿者（学生） |
| `category` | string | `event` \| `volunteer` \| `store` \| `medical` \| `tips` \| `study` \| `money` \| `social` \| `effort` \| `other` |
| `title` | string | タイトル（最大 40 文字）。**LLM 自動生成**、確認画面でユーザーが編集可（T4.15、`docs/06 §4.5`） |
| `period_raw` | string \| null | ユーザーの生入力（例「去年の10月」、最大 100 文字、スキップ可）。LLM 正規化の入力かつ意図の担保 |
| `period` | string \| null | `period_raw` を `created_at` 基準で LLM 正規化した絶対表現（例「2025年10月」）。正規化失敗時は `period_raw` と同値 |
| `summary` | string | できごとの概要（最大 300 文字、必須） |
| `learned` | string | 学べたこと・良かったこと（最大 200 文字、必須） |
| `regret` | string \| null | 残念だったこと・注意点（最大 200 文字、スキップ可） |
| `advice` | string \| null | 次にやる人へのアドバイス（最大 200 文字、スキップ可） |
| `body` | string | 上記 5 フィールドからの**合成派生**（最大 1200 文字）。下流（月次レポート・SECI context）はこの `body` を読む |
| `area` | string \| null | 地名・店名等（自由入力、`なし`/`無し`/`skip`/空文字は null に正規化） |
| `share_with_parent` | boolean | 保護者への共有可否（月次サマリーの最重要フィルタ） |
| `created_at` | string | 投稿日時 |

**`body` の合成と後方互換**:

`period`（正規化値）/ `summary` / `learned` / `regret` / `advice` は個別保存に加えて、非空フィールドのみを `【いつ】…／【やったこと】…／【学び】…／【残念・注意】…／【次の人へ】…` 形式で連結した `body` を `src/services/posts.py::compose_body` で生成・保存する（`docs/04_functional_spec.md §4.5`）。`body` の `【いつ】` には正規化済み `period` を使う（`period` が無ければ `period_raw` にフォールバック）。月次レポート（`body` 冒頭プレビュー）と SECI context（`list_all_for_context`）は `body` のみを参照するため、構造化・LLM 正規化しても下流は無改修。T4.14 以前の旧レコード（5 フィールドや `period_raw` を持たず `body` のみ）も同じ読み取り経路で扱えるため後方互換が保たれる。

**`post_id` の採番方式**:

`src/services/posts.py::_next_post_id` は「`data/posts.json` を毎回 load → `posts[].post_id` の数値部（`int(post_id[1:])`）を全走査 → max + 1」パターンで採番する。O(n) だが MVP スコープ（投稿件数 100 件未満想定）では問題ない。

**並行採番の安全性**:

MVP 期間は uvicorn を `--workers 1` で起動しているため、リクエストは in-process でシリアライズされる。加えて `save_json` は `LOCK_EX` で書き込みロックを取るので、最悪でも `load → append → save` サイクルが原子的に完了する。ワーカー数を増やす場合はプロセス間 race が発生し得るので、Redis などの外部採番機構への切替が必要（`08_demo_scenario.md` 想定範囲外）。

**他学生の生活相談への継承**（T4.10、SECI モデル）:

`data/posts.json` は月次サマリー用途に加えて、**他の学生が生活相談を送った際の Gemini context** の一次情報源にもなる。この用途で外部（Gemini）に渡すのは以下の 5 フィールドのみに限定する:

- `title`
- `body`
- `area`
- `category`
- `created_at`

`line_user_id` / `post_id` / `share_with_parent` は Gemini に **一切渡さない**。専用の匿名化アクセサ `src/services/posts.py::list_all_for_context()` を経由することで、生の posts.json レコードが誤って上流に流れないよう構造的に防ぐ。詳細な引用ルールと Zero-context への影響は `docs/06_ai_spec.md §4.2` および §5.3 を参照。

T4.14 で投稿は構造化されたが、Gemini に渡す本文は引き続き合成済み `body` に集約する。構造化フィールド（`period` / `summary` / `learned` / `regret` / `advice`）を個別に Gemini へ渡すことはせず、アローリスト（`list_all_for_context` の 5 フィールド `title` / `body` / `area` / `category` / `created_at`）は**変更しない**。これにより匿名化契約を維持したまま context 品質だけを底上げする。

### 4.4 invitations.json

招待コード。

```json
{
    "invitations": [
        {
            "code": "A3F7K9",
            "student_user_id": "U1234abcd...",
            "created_at": "2026-07-05T15:00:00+09:00",
            "expires_at": "2026-07-06T15:00:00+09:00",
            "used_at": null,
            "used_by_parent_id": null
        }
    ]
}
```

**フィールド**:
| フィールド | 型 | 説明 |
| --- | --- | --- |
| `code` | string | 6 桁英数字（`I`, `O`, `0`, `1` 除外、`ABCDEFGHJKLMNPQRSTUVWXYZ23456789` 32 文字集合） |
| `student_user_id` | string | 発行した学生 |
| `created_at` | string | 発行日時 |
| `expires_at` | string | 有効期限（発行から 24 時間） |
| `used_at` | string \| null | 使用日時（未使用なら null） |
| `used_by_parent_id` | string \| null | 使用した保護者 userId、または `"__revoked__"`（再発行で invalidate されたもの） |

**衝突チェック**:

`_generate_code()` は `secrets.choice` で 6 文字を生成した後、`find_active(code)` で既存 pending レコードと衝突しないかを pre-check する。衝突時は最大 5 回リトライし、5 回とも衝突なら `RuntimeError` を上げる（32^6 ≈ 10 億通りあるため実務上ほぼ発生しない）。

**再発行時の invalidate（Day 3 で確定）**:

同一学生が既に発行済みの pending コード（`used_at IS NULL` かつ未期限切れ）は、`issue_code` の先頭で一括で `used_at=now`, `used_by_parent_id="__revoked__"` にマークして無効化する。同時有効なコードは常に 1 個という不変条件を守る。

```python
# services/invitations.py::issue_code の pseudo コード
def issue_code(student_user_id: str) -> dict[str, Any]:
    data = load_json(_FILE, default=_EMPTY)
    now = _now_iso()
    # 1) prior pending を revoke
    for inv in data["invitations"]:
        if (inv["student_user_id"] == student_user_id
                and inv["used_at"] is None
                and not is_expired(inv["expires_at"])):
            inv["used_at"] = now
            inv["used_by_parent_id"] = REVOKED_SENTINEL
    # 2) 新規発行（衝突チェック 5 回リトライ）
    code = _generate_unique_code(data["invitations"])
    record = {
        "code": code,
        "student_user_id": student_user_id,
        "created_at": now,
        "expires_at": _hours_later_iso(24),
        "used_at": None,
        "used_by_parent_id": None,
    }
    data["invitations"].append(record)
    save_json(_FILE, data)
    return record
```

### 4.5 parent_links.json

保護者-学生の紐付け。

```json
{
    "links": [
        {
            "parent_user_id": "U9876wxyz...",
            "student_user_id": "U1234abcd...",
            "linked_at": "2026-07-05T20:00:00+09:00",
            "active": true
        }
    ]
}
```

**フィールド**:
| フィールド | 型 | 説明 |
| --- | --- | --- |
| `parent_user_id` | string | 保護者の LINE userId |
| `student_user_id` | string | 連携した学生の LINE userId |
| `linked_at` | string | 連携完了日時 |
| `active` | boolean | 有効フラグ（解除時 false） |

**関係性**: 1 学生 : N 保護者、1 保護者 : N 学生（家族構成の柔軟性を確保）

### 4.6 areas.json（seed、実在情報）

**同志社大学今出川キャンパス周辺**の公共施設・行政窓口・大学施設等の実在情報を 30 件手動投入。

- 情報鮮度: `last_verified_at`（例: `"2026-07"`）を全レコードに必須付与。Bot が回答に含める際は「◯年◯月時点の情報」として鮮度注記する。
- 対象範囲: 京都市上京区・中京区・北区に集中。京都府全域・京田辺キャンパス周辺は含めない。

```json
{
    "areas": [
        {
            "area_id": "AR001",
            "name": "今出川エリア",
            "category": "district",
            "description": "同志社大学今出川キャンパス周辺。学生向け飲食店、書店、コンビニが多い。",
            "tags": ["同志社", "学生街", "今出川"],
            "last_verified_at": "2026-07"
        },
        {
            "area_id": "AR002",
            "name": "京都市上京区役所",
            "category": "government",
            "description": "住民票や国民健康保険の手続き窓口。平日 8:45-17:15、混雑時間は 10-12 時。",
            "tags": ["行政", "手続き", "上京区"],
            "last_verified_at": "2026-07"
        }
    ]
}
```

**カテゴリ候補**: `district`, `government`, `medical`, `cultural`, `transport`, `park`, `library`

### 4.7 stores.json（seed、実在情報）

**同志社大学今出川キャンパス周辺**の学生向け実在店舗 15 件を手動投入。

- 情報鮮度: `data_freshness_note`（例: `"2026-07 時点。営業状況は変更の可能性あり"`）を全レコードに必須付与。Bot は Flex Message の末尾にこの文言を必ず表示する（NFR-Truth-4）。
- 参照元: `source_url`（公式サイト URL、なければ null）。verify 作業の再現性のため保持。

```json
{
    "stores": [
        {
            "store_id": "ST001",
            "name": "喫茶 進々堂 京大北門前",
            "category": "cafe",
            "area": "百万遍",
            "description": "老舗の喫茶店。長い机で他の学生と相席になることも。読書・勉強に最適。",
            "student_friendly": true,
            "price_range": "コーヒー 500 円台",
            "tags": ["喫茶", "勉強", "老舗"],
            "data_freshness_note": "2026-07 時点。営業状況は変更の可能性あり",
            "source_url": "https://example.com/shinshindo"
        }
    ]
}
```

**カテゴリ候補**: `cafe`, `restaurant`, `bookstore`, `bath`, `medical`, `pharmacy`, `convenience`

### 4.8 events.json（seed、実在情報）

大学公式・行政主催の実在イベント / ボランティアを 10 件手動投入。

- 情報鮮度: `last_verified_at`（例: `"2026-07"`）を全レコードに必須付与。
- 古風化回避: `schedule` フィールドは「毎年◯月開催」「毎月第◯土曜」等の**再帰的表現**を優先し、単発日付は避ける。単発日付が避けられない場合は `last_verified_at` と併せて Bot 応答で鮮度注記する。

```json
{
    "events": [
        {
            "event_id": "EV001",
            "name": "下鴨神社 月例清掃ボランティア",
            "category": "volunteer",
            "area": "下鴨神社",
            "schedule": "毎月第2土曜 8:30-10:00",
            "description": "地域の方と一緒に境内を清掃。参加無料、初参加歓迎。",
            "target_audience": ["学生", "地域住民"],
            "tags": ["ボランティア", "地域", "神社"],
            "last_verified_at": "2026-07"
        }
    ]
}
```

**カテゴリ候補**: `event`, `volunteer`, `workshop`, `festival`, `study_group`

### 4.9 senior_posts.json（seed、架空）

先輩入居者の投稿（**架空**、20 件）。本人特定リスクを避けるため、実在の先輩の実名・実体験は使用しない。ただし記述内の地名・施設名は実在化した areas / stores と整合させる（例: 「今出川近くの◯◯カフェ」を stores.json の実在店舗名で参照する）。

```json
{
    "senior_posts": [
        {
            "post_id": "SP001",
            "author_pseudonym": "先輩A（経済学部3年）",
            "category": "medical",
            "title": "夜間の発熱で焦った話",
            "body": "深夜に 38 度出て焦ったけど、京都市の #7119 に電話したら病院を教えてくれた。#7119 は覚えておくと安心。",
            "area": "京都市",
            "created_at": "2026-04-10T00:00:00+09:00"
        }
    ]
}
```

**カテゴリ**: `posts.json` と同じ。

### 4.10 session_activities.json（ランタイム、活動提案の短期永続化）

やりたいこと相談（FR-S4）で Gemini が返した提案 2〜3 件を、後続の「詳しく聞く」「参加した」postback が拾えるように 30 分だけ保持する。セッション（10 分 TTL）よりも長い TTL を持つ理由と実装方針は `docs/04_functional_spec.md §4.3` 参照。

```json
{
    "activities": {
        "a1b2c3d4": {
            "user_id": "U1234abcd...",
            "activity": {
                "title": "下鴨神社 月例清掃ボランティア",
                "summary": "地域の方と一緒に境内を清掃。参加無料、初参加歓迎。",
                "location": "下鴨神社",
                "when": "毎月第2土曜 8:30-10:00",
                "why_recommend": "地域活動に興味がある学生にぴったり",
                "reference_type": "volunteer"
            },
            "_written_at": 1751713200.0
        }
    }
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `activities` | dict | key = title の SHA-1 先頭 8 桁 |
| `<key>.user_id` | string | 提案を送った学生の LINE userId |
| `<key>.activity` | object | 提案本体（下記スキーマ） |
| `<key>._written_at` | float | UNIX epoch 秒。TTL 30 分の判定に使う |

**`activity` サブオブジェクトのスキーマ**（`06_ai_spec.md §4.1` の Gemini 出力形式と一致）:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `title` | string | 40 文字以内 |
| `summary` | string | 概要 2 文程度、120 文字以内 |
| `location` | string | 場所（空文字許容） |
| `when` | string | 時期・頻度（空文字許容） |
| `why_recommend` | string | なぜこの学生に合うか（80 文字以内） |
| `reference_type` | string enum | 下記 §4.10.1 参照 |

#### 4.10.1 `reference_type` の enum 値

やりたいこと相談の Gemini プロンプト（`docs/06_ai_spec.md §4.1`）と実装が共有する enum。値は以下 6 種に限定:

| 値 | 意味 | 由来 |
| --- | --- | --- |
| `event` | 地域イベント | `data/seed/events.json`（category=event/festival/study_group 等） |
| `volunteer` | ボランティア | `data/seed/events.json`（category=volunteer） |
| `store` | 店舗訪問系 | `data/seed/stores.json` |
| `senior_post` | 先輩投稿由来の提案 | `data/seed/senior_posts.json` |
| `generated` | AI が seed を組み合わせて発想した提案 | seed に完全一致するレコードなし、Flex Message で「AI 提案（要確認）」ラベルを付与 |
| `static_fallback` | Gemini 障害時のフォールバック | seed からランダム抽出（`docs/06_ai_spec.md §5.3.7`） |
| `sponsored` | 協賛企業イベントの PR 枠（FR-S9） | `data/seed/sponsored.json`。コード側で決定論的に挿入。Flex Message で「🏢 PR（協賛）」を付与（`docs/04_functional_spec.md §4.3`） |

`static_fallback` / `sponsored` はコード側が付与する注入型で、Gemini の JSON 出力には現れない。したがって `sponsored` は `src/templates/flex/activity_carousel.py` の色・ラベルにのみ追加し、`src/services/gemini.py::_ACTIVITY_JSON_SCHEMA` の enum には**追加しない**。Gemini が直接返す値（`event` / `volunteer` / `store` / `senior_post` / `generated`）を増減する場合のみ、`docs/06_ai_spec.md §4.1` のスキーマと `_ACTIVITY_JSON_SCHEMA` を同時に更新すること。

### 4.11 monthly_report_state.json（ランタイム、月次 Push の実行状態）

月次サマリー Push（`scripts/push_monthly_reports.py` → `monthly_report.push_previous_month_to_all`）の二重実行防止と実行履歴の保持のために用いる。

```json
{
    "last_batch": {
        "batch_id": "MRB-2026-08-01T09:00:00+09:00",
        "target_year_month": "2026-07",
        "executed_at": "2026-08-01T09:00:12+09:00",
        "counters": {"sent": 3, "empty": 1, "errors": 0}
    }
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `last_batch` | object \| null | 最後に実行された batch の記録（初期化直後は null） |
| `last_batch.batch_id` | string | `"MRB-" + executed_at ISO`。ログの相関 ID にも使う |
| `last_batch.target_year_month` | string | 集計対象年月（`"YYYY-MM"`） |
| `last_batch.executed_at` | string | 実際の実行完了時刻（ISO 8601 + tz） |
| `last_batch.counters` | object | `{"sent": int, "empty": int, "errors": int}` |

**二重実行防止**:

`push_previous_month_to_all(target_year_month=T)` は実行前に `last_batch.target_year_month == T` かをチェックし、一致すれば skip（戻り値の `skipped_batch=True`）。`--force` フラグで上書き実行可能（デモ・再送用）。

**初期化**:

`scripts/init_data.py` が `{"last_batch": null}` の空スケルトンを作成する。既存ファイルは上書きしない。

### 4.12 sponsored.json（seed、架空）

やりたいこと相談に PR 枠として掲載する協賛企業イベント（FR-S9、`04_functional_spec.md §4.3`）を 2〜3 件手動投入。実在企業が課金して掲載しているという体裁を実在企業名で出すと誤認を招くため、**デモ用と分かる架空企業名**を用いる（`.codex/rules/project_rules.md` のプライバシー方針）。掲載テキストは Bot がそのまま表示するため、日付・応募条件は正確に記述する。

- `data_freshness_note`: 募集状況の変化を前提とした鮮度注記を全レコードに必須付与（store seed と同方針）。Bot は bubble 末尾に鮮度注記を表示する。

```json
{
    "sponsored": [
        {
            "sponsor_id": "SPN001",
            "company_name": "株式会社サンプルテック（架空）",
            "title": "選考直結ハッカソン 2026 秋",
            "summary": "2 日間でプロダクトを開発。上位入賞者は本選考の一次選考が免除。",
            "apply_url": "https://example.com/hackathon-2026",
            "event_date": "2026-11-15",
            "deadline": "2026-10-31",
            "target": {
                "faculties": ["経済", "商"],
                "grades": ["3", "4"],
                "interest_tags": ["学問・研究", "ものづくり"]
            },
            "data_freshness_note": "2026-07 時点。募集状況は変更の可能性あり",
            "active": true
        }
    ]
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `sponsor_id` | string | 一意 ID（`"SPN" + 連番`）。トラッキングの相関キー |
| `company_name` | string | 協賛企業名（架空。「（架空）」を明記） |
| `title` | string | イベント名（40 文字以内目安） |
| `summary` | string | 概要（2 文程度、120 文字以内目安） |
| `apply_url` | string | 応募・詳細ページ URL（URI ボタンの遷移先） |
| `event_date` | string | 開催日（`"YYYY-MM-DD"` または再帰表現。空文字許容） |
| `deadline` | string | 応募締切（`"YYYY-MM-DD"`。空文字許容） |
| `target` | object | マッチング条件。下記参照 |
| `target.faculties` | list[str] | 対象学部（部分一致。seed `"経済"` ⊂ profile `"経済学部"`）。空リストは全学部対象 |
| `target.grades` | list[str] | 対象学年（プロフィール `grade` と同じ文字列。`"1"`〜`"4"` / `"M1"` / `"M2"`）。空リストは全学年対象 |
| `target.interest_tags` | list[str] | 対象の興味タグ。プロフィール `interests` の語彙（`src/templates/quick_reply.py` の `INTEREST_TAGS`）と**完全一致**で突き合わせるため、その語彙値をそのまま用いる |
| `data_freshness_note` | string | 鮮度注記（必須） |
| `active` | bool | `true` のみ掲載候補。掲載停止は `false` に切り替える |

**マッチング**（`04_functional_spec.md §4.3`）: `active: true` の案件を学生プロフィールの `faculty` / `grade` / `interests` と突き合わせ、合致スコア最上位 1 件を選ぶ。スコアは `faculty` 部分一致で +1、`grade` 一致で +1、`interest_tags` の重なり件数分を加点する。`target` の各フィールドが空リストなら「全対象」とみなし、その軸では加点しない。スコアが 0（どの軸も一致しない）の案件は掲載しない（的外れな広告を強制しない）。同点は seed の並び順で先頭を採る。

### 4.13 sponsored_engagement.json（ランタイム、PR クリック計測）

スポンサーPR の「興味あり」クリックを記録し、企業への効果指標・発表での反応数提示に用いる（FR-S9）。個人特定を避けるため LINE user_id はハッシュ化して保存する（`.codex/rules/project_rules.md` のプライバシー方針）。

```json
{
    "events": [
        {
            "sponsor_id": "SPN001",
            "user_hash": "9f2c...",
            "clicked_at": "2026-07-08T14:32:10+09:00"
        }
    ]
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `events` | list[object] | クリックイベントの追記ログ |
| `events[].sponsor_id` | string | クリックされた案件の `sponsor_id` |
| `events[].user_hash` | string | LINE user_id のハッシュ（生値は保存しない） |
| `events[].clicked_at` | string | クリック時刻（ISO 8601 + tz） |

**初期化**: `scripts/init_data.py` が `{"events": []}` の空スケルトンを作成する。既存ファイルは上書きしない。集計は `sponsor_id` ごとの件数を数えるだけの単純な read で足りる（月次サマリーへの反映は MVP 対象外）。

### 4.14 usage_stats.json（ランタイム、学生の月次利用回数）

FR-P3 拡張の第2層（利用状況の可視化）の計測ストア。学生が生活相談・やりたいこと相談を送るごと、経験投稿を保存するごと、プロフィールを更新するごとに 1 加算する。**保護者への共有は招待コード連携時の一括同意範囲**として扱い、レポートには当月分のみを要約表示する（`docs/04_functional_spec.md §5.3`）。ダッシュボードとしての時系列可視化は MVP スコープ外（`docs/02_mvp_scope.md §4.1`）。

```json
{
    "U1234567890abcdef1234567890abcdef": {
        "2026-07": {
            "life": 8,
            "activity": 4,
            "post": 3,
            "profile": 1
        }
    }
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `<line_user_id>` | object | 学生の LINE user_id（キー）。既存 `posts.json` / `profiles.json` と同じくキーとして使用。 |
| `<line_user_id>.<YYYY-MM>` | object | 月次バケット。当月の各イベントカウント。 |
| `<...>.life` | int | 生活相談ハンドラの呼出回数（非緊急・実回答分岐に到達した発話 1 件で +1）。マルチターンでも 1 発話 = 1 カウント。 |
| `<...>.activity` | int | やりたいこと相談（`handle_want_events` / `handle_want_students`）の呼出回数。 |
| `<...>.post` | int | 経験投稿の保存成功回数（`share_with_parent` の値によらず加算）。 |
| `<...>.profile` | int | プロフィール保存成功回数（新規登録も編集も両方カウント）。 |

**加算タイミング**（`src/handlers/student.py` 内、実装で参照する docs）:

- `handle_life_consultation` の非緊急分岐、Gemini 呼出直後 → `life`
- `handle_want_events` / `handle_want_students` 冒頭 → `activity`
- 経験投稿保存 (`posts.add_post`) 直後 → `post`
- `profiles.save_profile` 直後 → `profile`

**加算 API**（`src/services/usage_stats.py`）:

- `record(user_id: str, event_type: str, now_jst: datetime | None = None) -> None`
- `get_month(user_id: str, year_month: str) -> dict[str, int]`（欠損は 0 埋め）

**初期化**: `scripts/init_data.py` が `{}` の空スケルトンを作成する。既存ファイルは上書きしない。生 user_id をキーに持つため `.gitignore` 除外必須（他のランタイム JSON と同じ扱い）。ログには `user_id[:8]` のみ出す。

### 4.15 coupons.json（seed、架空）

経験投稿の節目ごとに配布する地域店舗クーポン（FR-S10、`04_functional_spec.md §4.8`）を 6〜9 件手動投入。節目ごとに 3 種ずつローテーション配布するため、6 件以上を用意する（`02_mvp_scope.md §3.3`）。実在店舗が実際にクーポンを発行しているという誤認を避けるため、**デモ用と分かる架空店舗名**を用いる（`.codex/rules/project_rules.md` のプライバシー方針）。

- **鮮度注記の扱い**: store seed（`stores.json`）と異なり、クーポンは架空店舗のため実在情報の鮮度注記（`data_freshness_note`）は**付与しない**。代わりに `valid_until`（有効期限）を持たせ、クーポンとしての様式を揃える。Bot は bubble に `valid_until` を表示する。
- 実店舗との連携・引き換え・消込は行わない（`02_mvp_scope.md §4.1` の除外範囲。本 seed は見た目の配布のみに用いる）。

```json
{
    "coupons": [
        {
            "coupon_id": "CPN001",
            "store_name": "サンプル珈琲店（架空）",
            "title": "ドリンク 1 杯無料",
            "summary": "対象ドリンクいずれか 1 杯を無料でご提供。",
            "discount": "ドリンク 1 杯無料",
            "store_url": "https://example.com/coffee",
            "valid_until": "2026-12-31",
            "active": true
        }
    ]
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `coupon_id` | string | 一意 ID（`"CPN" + 連番`）。配布履歴の相関キー |
| `store_name` | string | 店舗名（架空。「（架空）」を明記） |
| `title` | string | クーポン名（40 文字以内目安） |
| `summary` | string | 内容の補足（1〜2 文、120 文字以内目安）。空文字許容 |
| `discount` | string | 割引・特典の要約（bubble に強調表示） |
| `store_url` | string | 「お店で使う」URI ボタンの遷移先（架空 URL） |
| `valid_until` | string | 有効期限（`"YYYY-MM-DD"`。空文字許容） |
| `active` | bool | `true` のみ配布候補。停止は `false` に切り替える |

**配布ロジック**（`04_functional_spec.md §4.8`）: `active: true` のクーポンを seed の並び順で保持し、節目 `milestone = (count_all(user_id) // 3) * 3` ごとにバッチ `batch = (milestone // 3) - 1` を求め、`active_coupons[(batch * 3 + i) % len(active_coupons)]`（i=0,1,2）で 3 件を循環スライスする。マッチング（プロフィール合致）は行わず、全学生に同じローテーションを適用する。

### 4.16 coupon_distributions.json（ランタイム、配布履歴）

クーポン配布の実績と重複防止マーカーを学生ごとに記録する（FR-S10）。`last_awarded_milestone` の単調増加で同一節目の二重配布を防ぎ、`distributions` は発表での配布回数提示に用いる。トップレベルキーは生の `line_user_id`（`usage_stats.json` / `posts.json` と同一規約。`.gitignore` 除外必須）。

```json
{
    "U1234567890abcdef1234567890abcdef": {
        "last_awarded_milestone": 6,
        "distributions": [
            {
                "milestone": 3,
                "coupon_ids": ["CPN001", "CPN002", "CPN003"],
                "awarded_at": "2026-07-09T14:32:10+09:00"
            },
            {
                "milestone": 6,
                "coupon_ids": ["CPN004", "CPN005", "CPN006"],
                "awarded_at": "2026-07-09T15:01:44+09:00"
            }
        ]
    }
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `<line_user_id>` | object | 学生の LINE user_id（キー） |
| `<...>.last_awarded_milestone` | int | 直近で配布を完了した節目（3, 6, 9…）。0 は未配布。二重配布防止の判定に用いる |
| `<...>.distributions` | list[object] | 配布イベントの追記ログ |
| `<...>.distributions[].milestone` | int | 配布した節目 |
| `<...>.distributions[].coupon_ids` | list[str] | 配布した 3 種の `coupon_id` |
| `<...>.distributions[].awarded_at` | string | 配布時刻（ISO 8601 + tz） |

**初期化**: `scripts/init_data.py` が `{}` の空スケルトンを作成する。既存ファイルは上書きしない。読み書きは `storage.load_json` / `save_json`（fcntl ロック）経由。

### 4.17 prizes.json（seed、等級付き）

プレゼントくじ引き（FR-S11、`04_functional_spec.md §4.9`）の賞品を等級ごとに手動投入する（1〜3 等の 3 件）。実物の配布は行わない**デモ演出専用**だが、架空である旨は皆が理解している前提のため賞品名での「架空」明示は最小限とし、誤認防止は演出 Flex 側の小さな注記に委ねる。

```json
{
    "prizes": [
        {
            "prize_id": "PRZ001",
            "rank": 1,
            "name": "テーマパーク ペアチケット",
            "description": "人気テーマパークのペア入場チケット。",
            "emoji": "🎢",
            "valid_until": "2027-03-31",
            "note": "全国の対象パークでご利用いただけます",
            "active": true
        },
        {
            "prize_id": "PRZ002",
            "rank": 2,
            "name": "地元名店 ペアお食事券",
            "description": "地域の人気店で使えるペアお食事券。",
            "emoji": "🍽️",
            "valid_until": "2026-12-31",
            "note": "地域の提携飲食店でご利用いただけます",
            "active": true
        },
        {
            "prize_id": "PRZ003",
            "rank": 3,
            "name": "地域店舗クーポン",
            "description": "提携店で使える割引クーポン。",
            "emoji": "🎫",
            "valid_until": "2026-09-30",
            "note": "提携店舗でご利用いただけます",
            "active": true
        }
    ]
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `prize_id` | string | 一意 ID（`"PRZ" + 連番`）。抽選履歴の相関キー |
| `rank` | int | 等級（`1` = 1 等〜`3` = 3 等）。上位等ほど当選確率を低くする |
| `name` | string | 賞品名 |
| `description` | string | 賞品の補足（1 文程度）。空文字許容 |
| `emoji` | string | 演出 Flex に添える絵文字（任意、既定 `🎁`） |
| `valid_until` | string | 有効期限のダミー（`"YYYY-MM-DD"`。空文字許容）。当選演出の情報カードに「◯◯ まで」と表示する |
| `note` | string | 利用条件の補足（1 文程度）。空文字許容。情報カード下に小さく添える |
| `active` | bool | `true` のみ抽選対象。停止は `false` に切り替える |

各等の当選確率は `src/services/prizes.py` の確率テーブルで定義する（デモ演出用の既定値、上位等ほど低確率、残りははずれ）。

### 4.18 prize_draws.json（ランタイム、抽選履歴・PII 非収集）

プレゼント抽選の結果を学生ごとに記録する（FR-S11）。**当選者の氏名・住所・連絡先などの個人情報は一切保存しない**（`.codex/rules/project_rules.md` の個人情報方針）。抽選 `seed` を残して再現性・公正性の体裁を保つ。トップレベルキーは生の `line_user_id`（既存規約。`.gitignore` 除外必須）。

```json
{
    "U1234567890abcdef1234567890abcdef": {
        "draws": [
            {
                "rank": 1,
                "prize_id": "PRZ001",
                "result": "win",
                "seed": 8143201,
                "drawn_at": "2026-07-10T14:32:10+09:00"
            },
            {
                "rank": null,
                "prize_id": null,
                "result": "lose",
                "seed": 5540912,
                "drawn_at": "2026-07-10T15:02:44+09:00"
            }
        ]
    }
}
```

**フィールド**:

| フィールド | 型 | 説明 |
| --- | --- | --- |
| `<line_user_id>` | object | 学生の LINE user_id（キー） |
| `<...>.draws` | list[object] | 抽選イベントの追記ログ |
| `<...>.draws[].rank` | int \| null | 当選等級（`1`〜`3`）。はずれは `null` |
| `<...>.draws[].prize_id` | string \| null | 当選賞品の `prize_id`。はずれは `null` |
| `<...>.draws[].result` | string | `"win"` / `"lose"` |
| `<...>.draws[].seed` | int | 抽選に用いた乱数シード（再現性・公正性の体裁） |
| `<...>.draws[].drawn_at` | string | 抽選時刻（ISO 8601 + tz） |

**初期化**: `scripts/init_data.py` が `{}` の空スケルトンを作成する。既存ファイルは上書きしない。読み書きは `storage.load_json` / `save_json`（fcntl ロック）経由。**氏名・住所・連絡先を追加しないこと**（実配布は今後の展望であり、PII の収集/保存はスコープ外）。

## 5. デモ用学生プロフィール（架空）

デモ用に 3〜5 名分の**架空**学生プロフィールを `data/seed/demo_profiles.json` として用意（デモ以外では使わない）。実在人物の情報は使用しない。

```json
{
    "demo_profiles": [
        {
            "name_pseudonym": "山田 春樹",
            "line_user_id_placeholder": "STUDENT_DEMO_1",
            "university": "同志社大学",
            "faculty": "経済学部",
            "grade": "1",
            "interests": ["地域活動", "ものづくり", "食・カフェ巡り"],
            "recent_effort": "英語のTOEICスコアアップ",
            "want_to_do": "京都の伝統文化に触れる体験がしたい"
        }
    ]
}
```

**注意**: `line_user_id_placeholder` は初期セットアップ時に実際の LINE userId に置き換える。

## 6. データ更新パターン

パス引数はすべて `data/` 直下からの相対パスで指定する（`src/services/storage.py` の `DATA_DIR` を基準に解決される）。

### 6.1 プロフィール登録

```python
from src.services.storage import load_json, save_json

def save_profile(line_user_id: str, profile: dict) -> None:
    """Save student profile to profiles.json with fcntl lock."""
    data = load_json("profiles.json", default={"profiles": {}})
    data["profiles"][line_user_id] = profile
    save_json("profiles.json", data)
```

### 6.2 経験投稿

```python
def add_post(post: dict) -> str:
    """Add a new post and return the assigned post_id."""
    data = load_json("posts.json", default={"posts": []})
    next_id = _next_post_id(data["posts"])
    post["post_id"] = next_id
    data["posts"].append(post)
    save_json("posts.json", data)
    return next_id
```

### 6.3 招待コード発行

```python
def create_invitation(student_user_id: str) -> str:
    """Create a 6-char invitation code with 24h expiry."""
    code = _generate_code()  # 6 chars, exclude I/O/0/1
    data = load_json("invitations.json", default={"invitations": []})
    data["invitations"].append({
        "code": code,
        "student_user_id": student_user_id,
        "created_at": _now_iso(),
        "expires_at": _hours_later_iso(24),
        "used_at": None,
        "used_by_parent_id": None,
    })
    save_json("invitations.json", data)
    return code
```

### 6.4 招待コード使用

```python
def use_invitation(code: str, parent_user_id: str) -> str | None:
    """Consume an invitation code. Return student_user_id if success, None otherwise."""
    data = load_json("invitations.json", default={"invitations": []})
    for inv in data["invitations"]:
        if inv["code"] != code:
            continue
        if inv["used_at"] is not None:
            return None
        if _is_expired(inv["expires_at"]):
            return None
        inv["used_at"] = _now_iso()
        inv["used_by_parent_id"] = parent_user_id
        save_json("invitations.json", data)
        return inv["student_user_id"]
    return None
```

## 7. 月次サマリー生成

保護者向け「今月のレポート」を生成する際は、以下を行う。

1. `parent_links.json` から連携先学生を特定（`list_students_for_parent` / `list_all_active_pairs`）
2. `posts.json` から `share_with_parent=true` かつ対象月の投稿を抽出（`posts.list_month_shared`）
3. 対象月の**前月分の同フィルタ件数**を取得（先月比表示用）
4. `posts.json` 全期間で `share_with_parent=true` を数える（`posts.count_all_shared`、全期間通算表示用）
5. `usage_stats.json` から対象月のカウント辞書を取得（`usage_stats.get_month`）
6. Gemini で月次総括コメントを 1 本生成（`gemini.summarize_month`、入力は共有投稿タイトル＋利用回数のみ、空月・API 失敗・mock 時は定型文フォールバック）
7. 最大 5 件を **単一 Flex バブル**にリスト表示（カルーセルではない）
8. カテゴリごとに絵文字（🏛️ event / 🧹 volunteer / 🍜 store / 🏥 medical / 📋 tips / 🎓 study / 💰 money / 🤝 social / 💪 effort / ✨ other）を付ける

**Flex に渡す report dict**（`services/monthly_report.py`）:

| キー | 型 | 説明 |
| --- | --- | --- |
| `student_user_id` | string | 対象学生 |
| `student_display` | string | ヘッダー表示名（現状 `"あなたのお子さん"`） |
| `year_month` | string | `"YYYY-MM"` |
| `posts` | list[dict] | 対象月の投稿（最大 5 件、newest first） |
| `prev_count` | int | 前月の共有投稿件数（先月比表示に使用） |
| `total_count` | int | 全期間の共有投稿件数（通算表示に使用） |
| `usage` | dict[str, int] | 対象月の利用回数（`life` / `activity` / `post` / `profile`）。少回数フォールバック判定にも使用。 |
| `ai_summary` | string | 月次総括コメント（2〜3 文、フォールバック含む） |

### 7.1 月境界判定ヘルパー

`services/monthly_report.py` に以下のヘルパーを実装し、Pull（当月）と Push（前月）で共有する。JST 固定。

```python
JST = ZoneInfo("Asia/Tokyo")

def _first_of_this_month(now_jst: datetime) -> datetime:
    """当月 1 日 00:00 JST を返す。"""
    return now_jst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

def _first_of_prev_month(now_jst: datetime) -> datetime:
    """前月 1 日 00:00 JST を返す。"""
    first_this = _first_of_this_month(now_jst)
    # 前月末日を経由して前月 1 日を算出
    last_prev = first_this - timedelta(seconds=1)
    return last_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
```

- **Pull（当月）**: `start = _first_of_this_month(now_jst)`、`end = now_jst`。
- **Push（前月）**: `start = _first_of_prev_month(now_jst)`、`end = _first_of_this_month(now_jst)`（半開区間 `[start, end)`）。
- `target_year_month` オーバーライド指定時（`--month 2026-07` 等）は、そのまま `start = YYYY-MM-01 00:00 JST`、`end = 翌月 1 日 00:00 JST` を組み立てる。

### 7.2 `share_with_parent` フィルタの不変条件

`list_month_shared` は必ず `share_with_parent == True` を filter に含める。この 1 行が漏れると `false` 指定の投稿が保護者に露出する致命的なプライバシー事故になるため、実装・レビューで最重要不変条件として扱う（`04_functional_spec.md §4.5` 参照）。

## 8. 経験投稿の他学生への継承（SECI モデル）

Day 4 の T4.10 で、`data/posts.json` を「他の学生の生活相談 context」の情報源として組み込む。**保護者への月次サマリー用の `share_with_parent` フラグとは独立** に、全投稿がデフォルトで他学生の生活相談 Gemini プロンプトの参考情報となる。

### 8.1 匿名化ポリシー

外部（Gemini）に渡すのは以下 5 フィールドのみ:

| フィールド | 目的 |
| --- | --- |
| `title` | Gemini が話題との関連度を判断 |
| `body` | 本文の内容を引用元にする |
| `area` | 地名・店名の情報 |
| `category` | 引用時のトーン制御（tips なら「生活の知恵より」等） |
| `created_at` | 「最近」「先日」などの時制感を保つ（強調なし） |

**渡さないフィールド**:

- `line_user_id`（投稿者識別）
- `post_id`（内部識別）
- `share_with_parent`（保護者向けフラグは context 用途と無関係）

投稿者のプロフィール（大学名・学部・学年・興味など）も一切渡さない。

### 8.2 実装アクセサ

`src/services/posts.py::list_all_for_context()` が単一の入口となる:

```python
def list_all_for_context() -> list[dict[str, Any]]:
    """Return anonymized post payloads for the life-consultation Gemini prompt.

    Every stored post is projected to the 5-field allow-list
    (title, body, area, category, created_at). Callers must not
    reintroduce line_user_id / post_id / share_with_parent.
    """
```

呼び出し側は `context_search.find_relevant_context` のみで、他の場所からは呼び出さないこと。回帰リスクを減らすため、コードレビュー時に `posts.py` の他の list_* との差異を意識する。

### 8.3 Zero-context 判定への影響

`total_hits` が 4 要素（stores + areas + senior_posts + student_posts）の和になる。学生投稿が増えるほど Zero-context の発火頻度は下がる方向で、これは SECI モデルの継承サイクルによる自然な情報蓄積として期待する挙動である（詳細は `docs/06_ai_spec.md §5.3.2`）。

## 8. ロギング用会話ログ（任意）

`data/logs/conversations/YYYY-MM-DD.jsonl` に、以下形式で JSONL 追記（1 行 1 メッセージ）。

```json
{"ts":"2026-07-05T14:00:00+09:00","user_hash":"a1b2c3d4","role":"student","direction":"in","text":"..."}
{"ts":"2026-07-05T14:00:02+09:00","user_hash":"a1b2c3d4","role":"student","direction":"out","text":"..."}
```

- `user_hash`: SHA-256 の先頭 8 文字
- `.gitignore` で除外
- MVP 期間中はデバッグ用として活用、本番運用時は保持ポリシーを別途決める

## 9. 変更履歴

| 日付 | 変更内容 | 記入者 |
| --- | --- | --- |
| 2026-07-05 | 初版作成 | kmch4n |
| 2026-07-05 | ランタイム JSON を `.gitignore` 除外に統一、atomic write の実装例を追加、コード例のパス指定と import を実装と一致させた | kmch4n |
| 2026-07-06 | §4.10 session_activities.json スキーマと reference_type enum を追加、ファイル配置ツリーに session_activities.json / demo_profiles.json を反映 | kmch4n |
| 2026-07-06 | Day 3 家族ループ用: §2 ツリーに monthly_report_state.json、§4.3 に post_id 採番方式と並行性、§4.4 に衝突チェック 5 回リトライと再発行 invalidate の pseudo コード、§4.11 monthly_report_state.json スキーマ新設、§7 に月境界判定ヘルパーと share_with_parent 不変条件 | kmch4n |
| 2026-07-06 | T4.10 学生投稿継承の docs-first: §4.3 posts.json に匿名化継承ポリシーと 5-field allow-list、§8「経験投稿の他学生への継承」を新設（匿名化アクセサ list_all_for_context と Zero-context 影響） | kmch4n |
| 2026-07-07 | posts.json `category` enum と月次レポート絵文字マッピングに `study`/`money`/`social`/`effort` の 4 種を追加（Issue #14 の docs-first 更新） | anluck-m |
| 2026-07-08 | 企業スポンサードPR（FR-S9）の docs-first: §4.12 sponsored.json（seed、架空）と §4.13 sponsored_engagement.json（ランタイム、クリック計測）を新設、§4.10.1 reference_type enum に `sponsored`（注入型）を追加、§2 ツリー・gitignore・init 対象を 8 種に更新 | kmch4n |
| 2026-07-08 | FR-S9 実装整合: §4.12 `target.grades` を list[int]→list[str]（プロフィール `grade` は `"M1"`/`"M2"` を含む文字列）、`interest_tags` を `INTEREST_TAGS` 語彙に整合、マッチングにスコア計算式（faculty +1 / grade +1 / interest 重なり件数、スコア 0 は非表示）を明記 | kmch4n |
| 2026-07-09 | FR-P3 拡張の docs-first: §4.14 usage_stats.json を新設（学生の月次利用回数、加算タイミングと API を明記）、§2 ツリー・gitignore・init 対象を 9 種に更新、§7 月次サマリーに先月比・全期間通算・利用回数・AI 総括を折り込み Flex に渡す report dict のフィールド表を追加 | kmch4n |
| 2026-07-09 | クーポン配布（FR-S10）の docs-first: §4.15 coupons.json（seed、架空。鮮度注記でなく `valid_until` を持つ設計判断を明記）と §4.16 coupon_distributions.json（ランタイム、配布履歴・`last_awarded_milestone` 重複防止）を新設、§2 ツリー・gitignore・init 対象を 10 種に更新 | kmch4n |
| 2026-07-10 | プレゼントくじ引き（FR-S11）の docs-first: §4.17 prizes.json（seed、等級 `rank` 付き）と §4.18 prize_draws.json（ランタイム、抽選履歴・等級/はずれ・**PII 非収集**・抽選 seed 保持。応募口数 `entries` は廃止）を新設、§2 ツリー・gitignore・init 対象を 11 種に更新 | kmch4n |
| 2026-07-10 | §4.17 prizes.json に `valid_until`（有効期限ダミー）・`note`（利用条件）を追加、2 等を「地元名店 ペアお食事券」に変更（当落 Flex の情報カード表示に対応） | kmch4n |
