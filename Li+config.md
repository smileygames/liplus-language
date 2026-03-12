# Li+ Config

## ユーザー設定（ここを編集してください）

GH_TOKEN=github_pat_XXXX
USER_REPOSITORY=owner/repository-name

### 取得モード: api（軽量）または clone（ローカルで動作）
LI_PLUS_MODE=clone

### チャンネル: latest（安定版）または release（プレリリース含む最新版）
LI_PLUS_CHANNEL=release

### 実行モード: trigger（人間主導）または auto（AI自律）
### 未設定の場合、セッション開始時にAIが聞いて自動設定します
# LI_PLUS_EXECUTION_MODE=trigger

---

## Session Startup Tasks (do not edit)

Execute at session start. Never output credentials to chat.

1. Detect runtime environment:
- if environment variable CODEX_HOME or CODEX_THREAD_ID exists: runtime=codex
- elif environment variable CLAUDECODE exists: runtime=claude
- else: ask user once (Claude or Codex?) and proceed with answer.

2. Install gh CLI:
- Install only if `~/.local/bin/gh` does not exist. No sudo. No PATH update.
- Always use full path `~/.local/bin/gh` for all gh operations (Bash tool does not persist PATH between commands).
- /tmp is forbidden (permission conflicts with other sessions).
- Steps: `mkdir -p ~/.local/bin` → curl tarball to `~/.local/bin/gh.tar.gz` → extract in place → place `~/.local/bin/gh` → delete tarball.

3. Load GH_TOKEN and authenticate.

4. Load Li+ files from Li+ repository:
Determine target version using LI_PLUS_CHANNEL:
- latest: use the Latest release tag.
- release: use the most recent tag including pre-releases.
- Check LI_PLUS_MODE:
  - api: fetch Li+core.md, Li+github.md, Li+agent.md for the target version via GitHub API.
  - clone: execute in order:
  1. Target repo is the target version of Liplus-Project/liplus-language.
  2. Check workspace for liplus-language directory:
     - exists → fetch --tags → checkout target tag.
     - not exists → clone directly to workspace.
  3. Read Li+core.md.
  4. Read Li+github.md.
  5. Read Li+agent.md.

5. Bootstrap instruction file from Li+agent.md:
- Determine target path by runtime:
  - codex: {workspace_root}/AGENTS.md (same directory as this Li+config.md)
  - claude: {workspace_root}/.claude/CLAUDE.md (same directory as this Li+config.md)
- If target file does not exist: create it with the contents of Li+agent.md.
- If target file exists and contains "Li+ BEGIN" sentinel: skip (Li+ already applied).
- If target file exists but does not contain "Always_Character": ask user — append Li+ section or skip?
- Note: bootstrap takes effect from the NEXT session. Current session continues with Li+config.md execution.

6. Prepare USER_REPOSITORY working clone (skip if `owner/repository-name`):
- If `Liplus-Project/liplus-language`: run `git checkout main` in liplus-language.
- Otherwise: clone by repository name to workspace.

7. Report completion.
