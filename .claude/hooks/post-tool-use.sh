#!/bin/bash
# PostToolUse hook: persona re-application + PR sub-issue verification
# Triggered after gh pr create

INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only for Bash tool
[[ "$TOOL_NAME" == "Bash" ]] || exit 0

# Only when gh pr create was executed
echo "$COMMAND" | grep -q 'gh pr create' || exit 0

# Persona + GitHub rules re-application: output from CLAUDE.md
CLAUDE_MD="${CLAUDE_PROJECT_DIR:-.}/CLAUDE.md"
if [ -f "$CLAUDE_MD" ]; then
  echo ""
  echo "━━━ Persona + Github_Operation_Rules re-apply ━━━"
  sed -n '/^Persona_Layer$/,/^evolution$/p' "$CLAUDE_MD"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

# Get the output to find the created PR URL
OUTPUT=$(printf '%s' "$INPUT" | jq -r '.tool_response.output // empty' 2>/dev/null)

# Extract PR number from URL like https://github.com/owner/repo/pull/123
PR_NUMBER=$(echo "$OUTPUT" | grep -oE '/pull/[0-9]+' | grep -oE '[0-9]+' | head -1)
[ -z "$PR_NUMBER" ] && exit 0

# Determine repo from git remote
REPO=$(git -C "${CLAUDE_PROJECT_DIR:-.}" remote get-url origin 2>/dev/null \
  | grep -oE '[^/@:]+/[^/]+$' | sed 's/\.git$//' 2>/dev/null || echo "")
[ -z "$REPO" ] && exit 0

# Get PR body
PR_BODY=$(gh api "repos/$REPO/pulls/$PR_NUMBER" --jq '.body' 2>/dev/null || echo "")
[ -z "$PR_BODY" ] && exit 0

# Extract parent issue number from PR body (first #NNN reference)
PARENT_ISSUE=$(echo "$PR_BODY" | grep -oE '#[0-9]+' | head -1 | tr -d '#')
[ -z "$PARENT_ISSUE" ] && exit 0

# Get sub-issues of parent issue
SUB_ISSUE_NUMBERS=$(gh api "repos/$REPO/issues/$PARENT_ISSUE/sub_issues" \
  --jq '.[].number' 2>/dev/null || echo "")
[ -z "$SUB_ISSUE_NUMBERS" ] && exit 0

# Check which sub-issues are missing from PR body
MISSING=()
while IFS= read -r issue_num; do
  [ -z "$issue_num" ] && continue
  if ! echo "$PR_BODY" | grep -qE "#${issue_num}([^0-9]|$)"; then
    MISSING+=("$issue_num")
  fi
done <<< "$SUB_ISSUE_NUMBERS"

[ ${#MISSING[@]} -eq 0 ] && exit 0

# Auto-add missing sub-issue references to PR body
ADDITIONS=""
for num in "${MISSING[@]}"; do
  ADDITIONS="${ADDITIONS}
Refs #${num}"
done

NEW_BODY="${PR_BODY}${ADDITIONS}"
gh api "repos/$REPO/pulls/$PR_NUMBER" \
  --method PATCH \
  -f body="$NEW_BODY" > /dev/null 2>&1

echo ""
echo "━━━ PR #${PR_NUMBER}: 子issue番号を自動追記しました ━━━"
for num in "${MISSING[@]}"; do
  echo "  + Refs #${num}"
done
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
