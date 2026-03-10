# .claude/hooks Requirements Spec

## Overview

`liplus-language/.claude/hooks/` contains shell scripts that Claude Code invokes automatically at specific lifecycle events. These scripts reinforce Li+ behavioral rules and maintain environment integrity across sessions.

## Hook Scripts

### session-start.sh

**Trigger:** `PreToolUse` — runs once at session start (before first tool call)

**Purpose:** Ensure `gh` CLI is available in the remote execution environment.

**Behavior:**
- Exits immediately if not running in a remote Claude Code environment (`CLAUDE_CODE_REMOTE != "true"`)
- If `~/.local/bin/gh` does not exist: downloads the latest gh CLI tarball, extracts it to `~/.local/bin/gh`
- Uses no sudo and no system package manager
- `/tmp` is forbidden (permission conflicts between concurrent sessions); use a dedicated temp directory instead
- On success: prints installed version

**Dependencies:** `curl`, `tar`, `~/.local/bin/` directory

---

### stop.sh

**Trigger:** `Stop` — runs when Claude Code ends a response

**Purpose:** Remind the AI of the Always Character Layer rules defined in Li+core.md.

**Behavior:**
- Locates `Li+core.md` relative to `CLAUDE_PROJECT_DIR` (falls back to `.`)
- Extracts and outputs the `Always Character Layer` section
- If `Li+core.md` is not found: exits silently (graceful skip)

**Dependencies:** `Li+core.md` present in the project root

---

### post-tool-use.sh

**Trigger:** `PostToolUse` — runs after each tool call

**Purpose:** On `gh pr create`, re-apply the Li+ persona and GitHub operation rules, then verify all sub-issues of the parent issue are referenced in the PR body.

**Behavior:**
1. Exits early if tool is not `Bash` or command does not contain `gh pr create`
2. **Persona + rules re-application:**
   - Locates `Li+core.md` and `Li+github.md` relative to `CLAUDE_PROJECT_DIR`
   - Outputs both files in full as a reminder block
   - If either file is missing: skips that file silently
3. **Sub-issue verification:**
   - Extracts the PR number from the `gh pr create` output URL
   - Determines the repository from `git remote get-url origin`
   - Reads the PR body via GitHub API
   - Extracts the parent issue number (first `#NNN` reference in PR body)
   - Fetches sub-issues of the parent via GitHub API
   - Appends missing `Refs #NNN` lines to the PR body automatically

**Dependencies:** `jq`, `gh` CLI (authenticated), `git`, `Li+core.md`, `Li+github.md`

## Environment Variables

| Variable | Used by | Purpose |
|---|---|---|
| `CLAUDE_CODE_REMOTE` | session-start.sh | Skip gh install on local machines |
| `CLAUDE_PROJECT_DIR` | stop.sh, post-tool-use.sh | Locate Li+ source files |
| `GH_TOKEN` | post-tool-use.sh | GitHub API authentication |

## File Location

```
liplus-language/
└── .claude/
    └── hooks/
        ├── session-start.sh   # PreToolUse
        ├── stop.sh            # Stop
        └── post-tool-use.sh   # PostToolUse
```

## Related Documents

- `Li+core.md` — Always Character Layer definitions
- `Li+github.md` — GitHub operation rules
- `docs/B.-Li+config.md` — Li+ configuration reference
