#!/bin/bash
# PostToolUse hook: issue comment polling
# Extracts issue number from branch name and checks for new comments

INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only for Bash tool + GitHub-related commands
[[ "$TOOL_NAME" == "Bash" ]] || exit 0
echo "$COMMAND" | grep -qE '(git push|gh pr|gh issue|gh api|gh run)' || exit 0

# Extract issue number from branch name
BRANCH=$(git -C "${CLAUDE_PROJECT_DIR:-.}" branch --show-current 2>/dev/null || echo "")
ISSUE=$(echo "$BRANCH" | grep -oE '^[0-9]+' | head -1)
[ -z "$ISSUE" ] && exit 0

# Determine repo from git remote
REPO=$(git -C "${CLAUDE_PROJECT_DIR:-.}" remote get-url origin 2>/dev/null \
  | grep -oE '[^/@]+/[^/]+$' | sed 's/\.git$//' 2>/dev/null || echo "")
[ -z "$REPO" ] && exit 0

# Read last check timestamp
TIMESTAMP_FILE="${CLAUDE_PROJECT_DIR:-$HOME}/.claude/liplus-last-check"
SINCE=$(cat "$TIMESTAMP_FILE" 2>/dev/null || echo "1970-01-01T00:00:00Z")

# Fetch new comments since last check
COMMENTS=$(gh api "repos/$REPO/issues/$ISSUE/comments" \
  -f since="$SINCE" 2>/dev/null) || exit 0
COUNT=$(printf '%s' "$COMMENTS" | jq 'length' 2>/dev/null || echo "0")

# Update timestamp
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$TIMESTAMP_FILE"

[ "$COUNT" -eq 0 ] && exit 0

echo ""
echo "━━━ issue #${ISSUE} 新着コメント ${COUNT}件 ━━━"
printf '%s' "$COMMENTS" | jq -r '.[] | "[@\(.user.login)] \(.body | split("\n")[0])"'
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"