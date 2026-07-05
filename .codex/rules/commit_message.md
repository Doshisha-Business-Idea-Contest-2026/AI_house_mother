# コミットメッセージ規約

このファイルは AI 寮母リポジトリで作業する全 AI エージェント・開発者が守るべきコミットメッセージ規約を定義する。

## 必須フォーマット

```
[✨] English commit message
```

- gitmoji を `[` と `]` で囲み、半角スペースを 1 つ挟んだあと英語の subject を書く。
- `[` と `]` は必須。省略不可。
- subject は現在形（例: "Add feature"、"Fix bug"）で書く。

## 基本ルール

- 1 行目は 72 文字以内。
- 複数の論理的変更が含まれる場合、本文に箇条書きで列挙する。
- 無関係な変更は 1 つのコミットに混ぜず、可能な限り分割する。
- gitmoji は必ず下記の公式一覧から選ぶ。
- コミット本文・タイトルに Claude、Codex、その他 AI エージェントへの言及を含めない。
- `Co-Authored-By` などの AI attribution は追加しない。

## Git 安全ポリシー

**ユーザーの明示的な指示がない限り、`git add`、`git commit`、`git push` を実行してはならない。**

- ユーザーがコミット依頼をした際は、このファイルと直近 10 件のコミット履歴を確認してからメッセージを起草する。
- Git 書き込み操作の前に、`git config user.name` / `user.email` がユーザー本人のものであることを確認する。Bot や AI エージェントの identity になっていた場合は作業を停止して報告する。
- `--no-verify` などフックをスキップするフラグは使わない。フックが失敗した場合は原因を調査して修正する。

## Gitmoji 完全一覧（同期日: 2026-04-04）

[gitmoji.dev](https://gitmoji.dev/) より転記。プロンプト内で外部参照が不要になるように保持している。gitmoji.dev の変更に追随して更新すること。

| Emoji | Code | Description |
| --- | --- | --- |
| 🎨 | `:art:` | Improve structure / format of the code. |
| ⚡️ | `:zap:` | Improve performance. |
| 🔥 | `:fire:` | Remove code or files. |
| 🐛 | `:bug:` | Fix a bug. |
| 🚑 | `:ambulance:` | Critical hotfix. |
| ✨ | `:sparkles:` | Introduce new features. |
| 📝 | `:memo:` | Add or update documentation. |
| 🚀 | `:rocket:` | Deploy stuff. |
| 💄 | `:lipstick:` | Add or update the UI and style files. |
| 🎉 | `:tada:` | Begin a project. |
| ✅ | `:white_check_mark:` | Add, update, or pass tests. |
| 🔒 | `:lock:` | Fix security or privacy issues. |
| 🔐 | `:closed_lock_with_key:` | Add or update secrets. |
| 🔖 | `:bookmark:` | Release / Version tags. |
| 🚨 | `:rotating_light:` | Fix compiler / linter warnings. |
| 🚧 | `:construction:` | Work in progress. |
| 💚 | `:green_heart:` | Fix CI build. |
| ⬇️ | `:arrow_down:` | Downgrade dependencies. |
| ⬆️ | `:arrow_up:` | Upgrade dependencies. |
| 📌 | `:pushpin:` | Pin dependencies to specific versions. |
| 👷 | `:construction_worker:` | Add or update CI build system. |
| 📈 | `:chart_with_upwards_trend:` | Add or update analytics or track code. |
| ♻️ | `:recycle:` | Refactor code. |
| ➕ | `:heavy_plus_sign:` | Add a dependency. |
| ➖ | `:heavy_minus_sign:` | Remove a dependency. |
| 🔧 | `:wrench:` | Add or update configuration files. |
| 🔨 | `:hammer:` | Add or update development scripts. |
| 🌐 | `:globe_with_meridians:` | Internationalization and localization. |
| ✏️ | `:pencil2:` | Fix typos. |
| 💩 | `:poop:` | Write bad code that needs to be improved. |
| ⏪️ | `:rewind:` | Revert changes. |
| 🔀 | `:twisted_rightwards_arrows:` | Merge branches. |
| 📦 | `:package:` | Add or update compiled files or packages. |
| 👽 | `:alien:` | Update code due to external API changes. |
| 🚚 | `:truck:` | Move or rename resources (files, paths, routes). |
| 📄 | `:page_facing_up:` | Add or update license. |
| 💥 | `:boom:` | Introduce breaking changes. |
| 🍱 | `:bento:` | Add or update assets. |
| ♿️ | `:wheelchair:` | Improve accessibility. |
| 💡 | `:bulb:` | Add or update comments in source code. |
| 🍻 | `:beers:` | Write code drunkenly. |
| 💬 | `:speech_balloon:` | Add or update text and literals. |
| 🗃️ | `:card_file_box:` | Perform database related changes. |
| 🔊 | `:loud_sound:` | Add or update logs. |
| 🔇 | `:mute:` | Remove logs. |
| 👥 | `:busts_in_silhouette:` | Add or update contributor(s). |
| 🚸 | `:children_crossing:` | Improve user experience / usability. |
| 🏗️ | `:building_construction:` | Make architectural changes. |
| 📱 | `:iphone:` | Work on responsive design. |
| 🤡 | `:clown_face:` | Mock things. |
| 🥚 | `:egg:` | Add or update an easter egg. |
| 🙈 | `:see_no_evil:` | Add or update a .gitignore file. |
| 📸 | `:camera_flash:` | Add or update snapshots. |
| ⚗️ | `:alembic:` | Perform experiments. |
| 🔍 | `:mag:` | Improve SEO. |
| 🏷️ | `:label:` | Add or update types. |
| 🌱 | `:seedling:` | Add or update seed files. |
| 🚩 | `:triangular_flag_on_post:` | Add, update, or remove feature flags. |
| 🥅 | `:goal_net:` | Catch errors. |
| 💫 | `:dizzy:` | Add or update animations and transitions. |
| 🗑️ | `:wastebasket:` | Deprecate code that needs to be cleaned up. |
| 🛂 | `:passport_control:` | Work on authorization, roles, or permissions. |
| 🩹 | `:adhesive_bandage:` | Simple fix for a non-critical issue. |
| 🧐 | `:monocle_face:` | Data exploration / inspection. |
| ⚰️ | `:coffin:` | Remove dead code. |
| 🧪 | `:test_tube:` | Add a failing test. |
| 👔 | `:necktie:` | Add or update business logic. |
| 🩺 | `:stethoscope:` | Add or update healthcheck. |
| 🧱 | `:bricks:` | Infrastructure related changes. |
| 🧑‍💻 | `:technologist:` | Improve developer experience. |
| 💸 | `:money_with_wings:` | Add sponsorships or money related infrastructure. |
| 🧵 | `:thread:` | Add or update multithreading / concurrency code. |
| 🦺 | `:safety_vest:` | Add or update validation code. |
| ✈️ | `:airplane:` | Improve offline support. |
| 🦖 | `:t-rex:` | Code that adds backwards compatibility. |

## 良い例

```
[✨] Add student profile registration flow
[🐛] Fix Flex Message rendering on Android LINE app
[📝] Add MVP scope document
[♻️] Extract Gemini client into services layer
[🔧] Configure systemd service for ai_house_mother
```

## 悪い例

```
add feature                    # gitmoji がない
[sparkles] Add feature         # gitmoji が絵文字でない
[✨]Add feature                # スペースがない
[✨] added feature             # 過去形になっている
[✨] Claude が新機能を追加した   # AI 言及・過去形・日本語
```
