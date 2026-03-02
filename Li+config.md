# Li+ Config

## ユーザー設定（ここを編集してください）

GH_TOKEN=github_pat_XXXX
USER_REPOSITORY=owner/repository-name

### 取得モード: api（軽量）または clone（ローカルで動作）
LI_PLUS_MODE=clone

### チャンネル: latest（安定版）または release（プレリリース含む最新版）
LI_PLUS_CHANNEL=release

---

## セッション起動タスク（編集不要）

セッション開始時に以下を実行（チャットに認証情報を出力しないこと）:

1. mcp__cowork__allow_cowork_file_delete でワークスペース内ファイルの削除許可を取得する。

2. gh CLIインストール:
- `~/.local/bin/gh` が存在しない場合のみインストール。sudo不可・PATH不要。
- 以降の全 gh 操作はフルパス `~/.local/bin/gh` で実行（Bashツールはセッション間でPATHを保持しないため）。
- /tmp は使用禁止（他セッションとの権限衝突が発生するため）。
- 手順: `mkdir -p ~/.local/bin` → tarball を `~/.local/bin/gh.tar.gz` へ直接 curl → その場で展開 → `~/.local/bin/gh` へ配置 → tarball 削除。

3. GH_TOKENを読み込んで認証:

4. Li+リポジトリのCLAUDE.mdを読み込んで適用（LI_PLUS_MODEで動作切替）:
取得バージョンはLI_PLUS_CHANNELで決定する:
- latest の場合: Latestリリースのタグを使用。
- release の場合: Pre-release含む最新タグを使用。

LI_PLUS_MODEを確認し以下を実行:
- api の場合: Liplus-Project/liplus-language の対象バージョンのCLAUDE.mdをGitHub APIで直接取得して読み込む。
- clone の場合、順番通りに実行すること:
  1. 対象リポジトリは Liplus-Project/liplus-language の対象バージョン。
  2. ワークスペース内に liplus-language ディレクトリが:
     - 存在する → fetch --tags → 対象タグへ checkout。
     - 存在しない → 直接ワークスペースへ clone。
  3. CLAUDE.md を読み込む。

5. USER_REPOSITORY の作業クローンを準備（`owner/repository-name` の場合はスキップ）:
- `Liplus-Project/liplus-language` の場合: liplus-language で `git checkout main`。
- 別リポの場合: リポジトリ名でワークスペースへ clone。

6. 完了したら「認証完了」とだけ報告する。
