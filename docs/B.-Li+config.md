## 概要

**Li+config.md** は、Li+をセッションで動作させるための設定ファイルです。

ワークスペース直下に配置し、ユーザーが直接編集します。セッション開始時にAIがこのファイルを読み込み、環境検出・認証・バージョン取得・設定ファイル生成を自動的に実行します。

---

## 設定項目

### GH_TOKEN

GitHub Personal Access Token。Li+リポジトリへのアクセスと、作業リポジトリの操作に使用します。

### USER_REPOSITORY

作業対象のGitHubリポジトリを `owner/repository-name` 形式で指定します。

- `Liplus-Project/liplus-language` を指定した場合：liplus-languageディレクトリで `git checkout main` を実行
- 別リポジトリを指定した場合：そのリポジトリをワークスペースへ clone

### LI_PLUS_MODE

Li+リポジトリからLi+ファイルを取得する方法を指定します。

| 値 | 動作 |
|----|------|
| `api` | GitHub APIで直接Li+ファイルを取得（軽量。trigger-based re-readなどの継続機能は保証しない） |
| `clone` | リポジトリをローカルにclone/checkoutして取得（継続利用推奨） |

### LI_PLUS_CHANNEL

取得するLi+のバージョンチャンネルを指定します。

| 値 | 動作 |
|----|------|
| `latest` | Latestリリースのタグを使用（安定版） |
| `release` | Pre-release含む最新タグを使用（最新版） |

### LI_PLUS_EXECUTION_MODE

AIの自律度を切り替えます。未設定の場合、セッション開始時にAIが対話で設定します（手入力不要）。

| 値 | 動作 |
|----|------|
| `plan` | 人間主導。着手タイミングとPRレビューは人間が判断する（issue作成・クローズはAI）|
| `auto` | AI自律。issue選択・着手・PRレビューをAIが行う |

リリースはどちらのモードでも人間の確認が必要です。

---

## セッション起動フロー

セッション開始時にAIが自動実行するステップです。このセクションはユーザーが編集する必要はありません。

### ステップ1: 環境検出

ランタイム環境を自動判定します。

| 環境変数 | 判定結果 |
|---------|---------|
| `CODEX_HOME` or `CODEX_THREAD_ID` が存在 | runtime=codex |
| `CLAUDECODE` が存在 | runtime=claude |
| どちらもなし | ユーザーに1回確認 |

### ステップ2: gh CLIインストール

`~/.local/bin/gh` が存在しない場合のみインストールします。

- sudo不要、PATH変更不要
- `/tmp` は使用禁止（他セッションとの権限衝突のため）
- インストール先: `~/.local/bin/gh`（以降の全操作でフルパスを使用）

### ステップ3: 認証

`GH_TOKEN` を読み込んでgh CLIで認証します。認証情報はチャットに出力しません。

### ステップ4: Li+ファイル取得と適用

`LI_PLUS_CHANNEL` で対象バージョンを決定し、`LI_PLUS_MODE` に従ってLi+ファイルを取得・適用します。

取得対象: Li+core.md、Li+github.md、Li+agent.md

**cloneモードの場合：**

1. 対象リポジトリは Liplus-Project/liplus-language の対象バージョン
2. ワークスペース内に `liplus-language` ディレクトリが存在する場合 → `fetch --tags` → 対象タグへ checkout
3. 存在しない場合 → ワークスペースへ直接 clone
4. Li+core.md、Li+github.md、Li+agent.md を読み込む

### ステップ5: 設定ファイルの自動生成（Bootstrap）

Li+agent.md テンプレートから、ランタイムに応じた設定ファイルを生成します。

| ランタイム | 生成先 |
|-----------|--------|
| codex | `{workspace_root}/AGENTS.md`（Li+config.md と同じディレクトリ） |
| claude | `{workspace_root}/.claude/CLAUDE.md`（Li+config.md と同じディレクトリ直下） |

判定ロジック：

- ファイルが存在しない → Li+agent.md の内容で新規作成
- ファイルが存在し `Li+ BEGIN` sentinel を含む → スキップ（Li+適用済み）
- ファイルが存在するが sentinel なし → ユーザーに確認（Li+セクションを追記 or スキップ）

Bootstrap は次回セッションから有効になります。現セッションは Li+config.md の実行で継続します。

### ステップ6: USER_REPOSITORY の作業クローン準備

`USER_REPOSITORY` が `owner/repository-name`（デフォルト値）の場合はスキップします。

### ステップ7: 完了報告

起動完了を報告します。

---

## 注意事項

- `GH_TOKEN` はチャットに出力されません
- セッションを跨いでgh CLIのPATHは保持されないため、常にフルパス（`~/.local/bin/gh`）で実行されます
- `LI_PLUS_MODE=clone` の場合、初回セッションはcloneのため時間がかかります。2回目以降はfetch & checkoutのみです
- リポジトリで管理される Markdown ファイルと `LICENSE` は、Windows・WSL・Linux 間で差分がぶれないよう `.gitattributes` で LF に正規化します
