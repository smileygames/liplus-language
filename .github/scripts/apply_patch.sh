#!/bin/bash
set -e

PATCH_FILE="li+.patch"

if [ ! -f "$PATCH_FILE" ]; then
  echo "No patch file found. Exiting."
  exit 0
fi

TARGET=$(head -n 1 "$PATCH_FILE" | awk '{print $2}')

if [ ! -f "$TARGET" ]; then
  echo "Target file not found: $TARGET"
  exit 1
fi

awk '
BEGIN { apply=0 }
$0=="BEGIN" { apply=1; next }
$0=="END" { apply=0; next }
apply==0 { next }
apply==1 { print }
' "$PATCH_FILE" > "$TARGET.new"

mv "$TARGET.new" "$TARGET"

echo "Patch applied to $TARGET"
