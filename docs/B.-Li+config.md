## 概要

**Li+config.md** は、Li+をセッションで動作させるための設定ファイルです。

ワークスペース直下に配置し、ユーザーが直接編集します。セッション開始時にAIがこのファイルを読み込み、認証・バージョン取得・ペルソナ適用を自動的に実行します。

---

## 設定項目

### GH_TOKEN

GitHub Personal Access Token。Li+リポジトリへのアクセスと、作業リポジトリの操作に使用します。

### USER_REPOSITORY

作業対象のGitHubリポジトリを `owner/repository-name` 形式で指定します。

- `Liplus-Project/liplus-language` を指定した場合：liplus-languageディレクトリで `git checkout main` を実行
- 別リポジトリを指定した場合：そのリポジトリをワークスペースへ clone

### LI_PLUS_MODE

Li+リポジトリのLi+core.mdとLi+github.mdを取得する方法を指定します。

| 値 | 動作 |
|----|------|
| `api` | GitHub APIで直接Li+core.md・Li+github.mdを取得（軽量） |
| `clone` | リポジトリをローカルにclone/checkoutして取得（ローカルで動作） |

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

### ステップ1: ファイル削除許可の取得

`mcp__cowork__allow_cowork_file_delete` でワークスペース内ファイルの削除許可を取得します。以降の全ステップより先に実行します。

### ステップ2: gh CLIインストール

`~/.local/bin/gh` が存在しない場合のみインストールします。

- sudo不要、PATH変更不要
- `/tmp` は使用禁止（他セッションとの権限衝突のため）
- インストール先: `~/.local/bin/gh`（以降の全操作でフルパスを使用）

### ステップ3: 認証

`GH_TOKEN` を読み込んでgh CLIで認証します。認証情報はチャットに出力しません。

### ステップ4: Li+バージョン取得とLi+core.md/Li+github.md適用

`LI_PLUS_CHANNEL` で対象バージョンを決定し、`LI_PLUS_MODE` に従ってLi+core.mdとLi+github.mdを取得・適用します。

**cloneモードの場合：**

1. 対象リポジトリは Liplus-Project/liplus-language の対象バージョン
2. ワークスペース内に `liplus-language` ディレクトリが存在する場合 → `fetch --tags` → 対象タグへ checkout
3. 存在しない場合 → ワークスペースへ直接 clone
4. Li+core.md を読み込む
5. Li+github.md を読み込む

### ステップ5: USER_REPOSITORY の作業クローン準備

`USER_REPOSITORY` が `owner/repository-name`（デフォルト値）の場合はスキップします。

### ステップ6: 完了報告

起動完了を報告します。

---

## 注意事項

- `GH_TOKEN` はチャットに出力されません
- セッションを跨いでgh CLIのPATHは保持されないため、常にフルパス（`~/.local/bin/gh`）で実行されます
- `LI_PLUS_MODE=clone` の場合、初回セッションはcloneのため時間がかかります。2回目以降はfetch & checkoutのみです
