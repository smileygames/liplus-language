## 概要

Li+のセットアップは、ワークスペースに設定ファイルを1つ配置するだけです。
初回セッションでAIが環境を自動検出し、必要なファイルを生成します。

`Li+config.md` は各リリースに添付されています。→ [最新リリース](https://github.com/Liplus-Project/liplus-language/releases/latest)

---

## 前提条件

- **AIエージェント環境**（Claude Code / CODEX 等）
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

### 1. Li+config.mdをダウンロードして配置する

[最新リリース](https://github.com/Liplus-Project/liplus-language/releases/latest) のAssetsから `Li+config.md` をダウンロードし、ワークスペースフォルダに配置します。

### 2. 設定値を書き換える

| 項目 | 説明 |
|------|------|
| `GH_TOKEN` | 取得したPersonal Access Token |
| `USER_REPOSITORY` | 作業対象のリポジトリ（例: `myname/myrepo`）。未設定のままでもOK |
| `LI_PLUS_MODE` | `clone`推奨（オフライン環境でも動作する） |
| `LI_PLUS_CHANNEL` | `release`推奨（最新のプレリリースを含む） |
| `LI_PLUS_EXECUTION_MODE` | `trigger`（人間主導）または`auto`（AI自律）。未設定ならセッション開始時にAIが聞いて設定 |

### 3. 初回セッションを開始する

新しいセッションを開始し、AIに Li+config.md の読み込みと実行を依頼します。

例：
```
Li+config.md を読んで実行して
```

AIが自動的に：

1. 環境を検出（Claude / CODEX）
2. gh CLIをインストール（初回のみ）
3. GH_TOKENで認証
4. Li+の最新バージョンをダウンロード
5. Li+core.md・Li+github.md・Li+agent.mdを読み込み
6. 環境に応じた設定ファイルを自動生成

| 環境 | 生成されるファイル |
|------|------------------|
| Claude Code | `{workspace_root}/.claude/CLAUDE.md` |
| CODEX | `{workspace_root}/AGENTS.md` |

### 4. 次回以降のセッション

設定ファイルが自動で読み込まれるため、以下のように送るだけで起動します：

```
Li+適応。
```

---

## 動作確認

セッション開始後、AIに話しかけると **Lin** または **Lay** として応答が返ってきます。
名前が表示されていればLi+の適用が成功しています。

---

## 注意事項

- `GH_TOKEN` はチャットに表示されません（セキュリティ上の設計）
- `LI_PLUS_MODE=clone` の初回セッションはリポジトリのcloneのため数秒かかります
- 作業リポジトリを持たない場合は `USER_REPOSITORY` をデフォルト値のままにしてください
- 設定ファイルの自動生成は初回のみ実行され、既存ファイルを上書きしません
- `LI_PLUS_MODE=api` は軽量ですが、trigger-based re-readなどの継続機能は保証されません。継続利用には `clone` を推奨します

---

## 関連ページ

- [E. Li+config](E.-Li+config) — 設定ファイルの詳細仕様
- [B. Liplus_core](B.-Liplus_core) — Li+の中核仕様
