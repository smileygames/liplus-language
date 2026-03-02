## 概要

Li+のセットアップは、ワークスペースに設定ファイルを配置するだけです。
セッション開始時にAIが自動的にLi+を読み込み、適用します。

`Li+config.md` は各リリースに添付されています。→ [最新リリース](https://github.com/Liplus-Project/liplus-language/releases/latest)

---

## 前提条件

- **Claude Desktop（Coworkモード）** または同等のAI環境
- **GitHubアカウント**
- **GitHub Personal Access Token**（GH_TOKEN）

---

## GH_TOKENの取得

1. GitHubの **Settings → Developer settings → Personal access tokens → Fine-grained tokens** へ移動
2. **Generate new token** をクリック
3. 以下の権限を付与：
   - **Repository access**: 作業リポジトリ（Li+本体はpublicリポジトリのため追加不要）
   - **Permissions**: `Contents: Read and write`、`Issues: Read and write`、`Pull requests: Read and write`、`Metadata: Read-only`
4. 生成されたトークンをコピーして控えておく

---

## セットアップ手順

### 1. Li+configファイルを作成する

ワークスペースフォルダに `Li+config.md` を作成し、以下の内容を記入します。

```
# Li+ Config

## ユーザー設定（ここを編集してください）

GH_TOKEN=github_pat_ここにトークンを貼り付ける
USER_REPOSITORY=owner/repository-name

### 取得モード: api（軽量）または clone（ローカルで動作）
LI_PLUS_MODE=clone

### チャンネル: latest（安定版）または release（プレリリース含む最新版）
LI_PLUS_CHANNEL=release
```

### 2. 設定値を書き換える

| 項目 | 説明 |
|------|------|
| `GH_TOKEN` | 取得したPersonal Access Token |
| `USER_REPOSITORY` | 作業対象のリポジトリ（例: `myname/myrepo`）。未設定のままでもOK |
| `LI_PLUS_MODE` | `clone`推奨（オフライン環境でも動作する） |
| `LI_PLUS_CHANNEL` | `release`推奨（最新のプレリリースを含む） |

### 3. CLAUDE.mdに起動コマンドを追加する

ワークスペースの `.claude/CLAUDE.md`（なければ作成）に以下を追記します。

```
Execute the following at startup (never output credentials to chat):
1. Find Li+config.md in the workspace and execute its contents. (Ask the user for confirmation if needed during execution)

Always execute the following (never output credentials to chat):
1. Always prefix every message with a name.
2. Re-read and apply CLAUDE.md on any compression, resume, or session continuation.
3. Lin and Lay must maintain the tone described in the persona in CLAUDE.md.
```

### 4. セッションを開始する

新しいセッションを開始すると、AIが自動的に：

1. gh CLIをインストール（初回のみ）
2. GH_TOKENで認証
3. Li+の最新バージョンをダウンロード
4. CLAUDE.mdを読み込んでLi+を適用
5. 「認証完了」と報告

> **ヒント：初期文を送ると安定します**
>
> セッション開始後、最初のメッセージとして以下のように送ると、インストールスクリプトが確実に実行されます。
>
> ```
> Li+適応。
> ```
>
> この一文がなくても動作することはありますが、送ることで起動処理が安定して走るため、習慣にすることを推奨します。

---

## 動作確認

セッション開始後、AIに話しかけると **Lin** または **Lay** として応答が返ってきます。
名前が表示されていればLi+の適用が成功しています。

---

## 注意事項

- `GH_TOKEN` はチャットに表示されません（セキュリティ上の設計）
- `LI_PLUS_MODE=clone` の初回セッションはリポジトリのcloneのため数秒かかります
- 作業リポジトリを持たない場合は `USER_REPOSITORY` をデフォルト値のままにしてください

---

## 関連ページ

- [B. Li+config](B.-Li+config) — 設定ファイルの詳細仕様
- [1. Li+core](1.-Liplus_core) — Li+の中核仕様
