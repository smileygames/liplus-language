#!/bin/bash
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"
CORE_MD="$PROJECT_ROOT/Li+core.md"

if [ ! -f "$CORE_MD" ]; then
  exit 0
fi

# Output Always Character Layer section from Li+core.md
sed -n '/^Always Character Layer$/,/^Behavioral Style$/p' "$CORE_MD" | head -n -1
