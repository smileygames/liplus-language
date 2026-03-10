# .claude/hooks 要件仕様書

## 概要

`liplus-language/.claude/hooks/` には、Claude Code が特定のライフサイクルイベント時に自動実行するシェルスクリプトを格納する。これらのスクリプトは Li+ の行動ルールを強制し、セッション間で環境の一貫性を保つ。

## フックスクリプト

### session-start.sh

**トリガー:** `PreToolUse` — セッション開始時（最初のツール呼び出し前）に一度実行

**目的:** リモート実行環境で `gh` CLI が利用可能な状態を確保する。

**動作:**
- リモート Claude Code 環境でない場合（`CLAUDE_CODE_REMOTE != "true"`）は即時終了
- `~/.local/bin/gh` が存在しない場合: 最新の gh CLI tarball をダウンロードし `~/.local/bin/gh` に展開
- sudo および システムパッケージマネージャは使用しない
- `/tmp` は使用禁止（並行セッション間の権限競合を避けるため）。専用の一時ディレクトリを使用
- 成功時: インストール済みバージョンを出力

**依存:** `curl`、`tar`、`~/.local/bin/` ディレクトリ

---

### stop.sh

**トリガー:** `Stop` — Claude Code がレスポンスを終了するとき

**目的:** Li+core.md で定義された Always Character Layer のルールを AI に再通知する。

**動作:**
- `CLAUDE_PROJECT_DIR`（フォールバック: `.`）を起点として `Li+core.md` を探索
- `Always Character Layer` セクションを抽出して出力
- `Li+core.md` が見つからない場合: 何もせず終了（graceful skip）

**依存:** プロジェクトルートに `Li+core.md` が存在すること

---

### post-tool-use.sh

**トリガー:** `PostToolUse` — ツール呼び出し後に毎回実行

**目的:** `gh pr create` 実行後に Li+ ペルソナと GitHub 運用ルールを再適用し、PR body への子 issue 参照の漏れを自動補完する。

**動作:**
1. ツールが `Bash` でない、またはコマンドに `gh pr create` が含まれない場合は早期終了
2. **ペルソナ + ルール再適用:**
   - `CLAUDE_PROJECT_DIR` を起点として `Li+core.md` と `Li+github.md` を探索
   - 両ファイルを全文出力（リマインダーブロックとして表示）
   - ファイルが存在しない場合: そのファイルをスキップ
3. **子 issue 検証:**
   - `gh pr create` 出力 URL から PR 番号を抽出
   - `git remote get-url origin` からリポジトリを特定
   - GitHub API 経由で PR body を取得
   - PR body 最初の `#NNN` 参照から親 issue 番号を抽出
   - GitHub API 経由で親の子 issue を取得
   - PR body に記載のない子 issue の `Refs #NNN` を自動追記

**依存:** `jq`、`gh` CLI（認証済み）、`git`、`Li+core.md`、`Li+github.md`

## 環境変数

| 変数 | 使用スクリプト | 用途 |
|---|---|---|
| `CLAUDE_CODE_REMOTE` | session-start.sh | ローカル環境での gh インストールをスキップ |
| `CLAUDE_PROJECT_DIR` | stop.sh、post-tool-use.sh | Li+ ソースファイルの探索起点 |
| `GH_TOKEN` | post-tool-use.sh | GitHub API 認証 |

## ファイル構成

```
liplus-language/
└── .claude/
    └── hooks/
        ├── session-start.sh   # PreToolUse
        ├── stop.sh            # Stop
        └── post-tool-use.sh   # PostToolUse
```

## 関連ドキュメント

- `Li+core.md` — Always Character Layer 定義
- `Li+github.md` — GitHub 運用ルール
- `docs/B.-Li+config.md` — Li+ 設定リファレンス
