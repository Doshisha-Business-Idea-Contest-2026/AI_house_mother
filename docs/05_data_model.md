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
├── seed/                      # 手動投入する seed データ（同志社今出川周辺）
│   ├── areas.json             # 地域情報（実在: 公共施設・行政窓口等）
│   ├── stores.json            # 学生向け店舗（実在: 民間実名店舗、鮮度注記必須）
│   ├── events.json            # 地域イベント・ボランティア（実在: 大学公式・行政主催）
│   ├── senior_posts.json      # 先輩投稿（架空: プライバシー保護）
│   └── demo_profiles.json     # デモ用学生プロフィール（架空: プライバシー保護）
└── logs/
    └── conversations/         # 任意: 会話ログ（デバッグ用、本番運用時は要検討）
```

- **コミット対象**: `data/seed/*`（デモの再現性を確保）と `data/.gitkeep`/`data/seed/.gitkeep` のみ。
- **`.gitignore` 除外**: `data/logs/` および実行時に更新される JSON 7 種（`users.json`、`profiles.json`、`posts.json`、`invitations.json`、`parent_links.json`、`session_activities.json`、`monthly_report_state.json`）。
- **理由**: デモ直前のリセット容易性を優先する。ランタイム JSON をコミット対象にすると、審査員体験時に生成された LINE user_id が Git 履歴に残る懸念もある。
- **初期化**: `python scripts/init_data.py` を実行すると、ランタイム JSON 7 種が空スキーマで作成される（既存ファイルは上書きしない）。

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
            "body": "先週末、下鴨神社の月例清掃に参加。地域の方と話せて楽しかった。次は10月に開催予定。",
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
| `category` | string | `event` \| `volunteer` \| `store` \| `medical` \| `tips` \| `other` |
| `title` | string | タイトル（最大 40 文字） |
| `body` | string | 本文（最大 500 文字） |
| `area` | string \| null | 地名・店名等（自由入力、`なし`/`無し`/`skip`/空文字は null に正規化） |
| `share_with_parent` | boolean | 保護者への共有可否（月次サマリーの最重要フィルタ） |
| `created_at` | string | 投稿日時 |

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

新しい値を追加する場合は、`docs/06_ai_spec.md §4.1` のスキーマと `src/services/gemini.py::_ACTIVITY_JSON_SCHEMA` の enum も同時に更新すること。

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
3. 最大 5 件を **単一 Flex バブル**にリスト表示（カルーセルではない）
4. カテゴリごとに絵文字（🏛️ event / 🧹 volunteer / 🍜 store / 🏥 medical / 📋 tips / ✨ other）を付ける

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
